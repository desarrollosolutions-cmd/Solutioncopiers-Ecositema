"""Vistas del módulo WhatsApp CRM."""
from __future__ import annotations

from functools import wraps

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.dashboard.views import da_decorator

from .models import ConversationLabel, WhatsAppConversation, WhatsAppMessage
from .webhook import _upsert_inbound_message, send_whatsapp_message

# ---------------------------------------------------------------------------
# Helpers de acceso
# ---------------------------------------------------------------------------

def _panel_ctx(request):
    """Contexto base del panel (reutiliza el helper del dashboard)."""
    try:
        from apps.dashboard.views import _panel_base_ctx
        return _panel_base_ctx(request)
    except Exception:
        return {}


def _da_ctx():
    return {}


def _wa_asesora_required(view_func):
    """
    Acceso al inbox/simulador de WhatsApp: solo asesoras (usuarios autenticados,
    sin permisos de staff, y sin perfil de campo). Un mensajero o técnico no
    debe poder leer ni responder conversaciones de clientes por acá — ellos
    tienen su propio portal en /campo/.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/panel/acceso/?next={request.path}")
        if request.user.is_staff:
            return redirect("wa:dash_overview")
        from apps.dashboard.models import FieldUser
        try:
            request.user.field_profile
        except FieldUser.DoesNotExist:
            return view_func(request, *args, **kwargs)
        return redirect("/campo/")
    return wrapper


# ---------------------------------------------------------------------------
# PANEL — Inbox
# ---------------------------------------------------------------------------

@method_decorator(_wa_asesora_required, name="dispatch")
class PanelWAInboxView(View):
    template_name = "whatsapp/panel_inbox.html"

    def get(self, request):
        status   = request.GET.get("status", "")
        label_id = request.GET.get("label", "")
        q        = request.GET.get("q", "").strip()
        mine     = request.GET.get("mine", "1")

        qs = (
            WhatsAppConversation.objects
            .prefetch_related("labels")
            .select_related("lead", "assigned_to")
            .order_by("-last_message_at")
        )

        if mine == "1":
            qs = qs.filter(assigned_to=request.user)
        if status:
            qs = qs.filter(status=status)
        if label_id:
            qs = qs.filter(labels__pk=label_id)
        if q:
            qs = qs.filter(contact_name__icontains=q) | qs.filter(phone__icontains=q)

        ctx = _panel_ctx(request)
        ctx.update({
            "conversations":     qs[:80],
            "labels":            ConversationLabel.objects.all(),
            "status_choices":    WhatsAppConversation.Status.choices,
            "current_status":    status,
            "current_label":     label_id,
            "current_q":         q,
            "mine":              mine,
            "total_unread":      WhatsAppConversation.objects.filter(
                                     assigned_to=request.user, unread_count__gt=0
                                 ).count(),
        })
        return render(request, self.template_name, ctx)


# ---------------------------------------------------------------------------
# PANEL — Detalle de conversación
# ---------------------------------------------------------------------------

@method_decorator(_wa_asesora_required, name="dispatch")
class PanelWAConversationView(View):
    template_name = "whatsapp/panel_conversation.html"

    def get(self, request, pk):
        conv = get_object_or_404(
            WhatsAppConversation.objects.select_related("lead", "assigned_to")
                                        .prefetch_related("labels", "messages__sent_by"),
            pk=pk,
        )
        conv.mark_read()

        from django.contrib.auth.models import User
        ctx = _panel_ctx(request)
        ctx.update({
            "conv":           conv,
            "messages":       conv.messages.order_by("created_at"),
            "labels":         ConversationLabel.objects.all(),
            "status_choices": WhatsAppConversation.Status.choices,
            "asesoras":       User.objects.filter(is_active=True, is_staff=True),
        })
        return render(request, self.template_name, ctx)

    def post(self, request, pk):
        conv   = get_object_or_404(WhatsAppConversation, pk=pk)
        action = request.POST.get("action", "reply")

        if action == "reply":
            body = request.POST.get("body", "").strip()
            if body:
                send_whatsapp_message(conv, body, sent_by=request.user)

        elif action == "set_status":
            new_status = request.POST.get("status", "")
            if new_status in dict(WhatsAppConversation.Status.choices):
                conv.status = new_status
                conv.save(update_fields=["status"])

        elif action == "assign":
            from django.contrib.auth.models import User
            uid = request.POST.get("assigned_to", "")
            conv.assigned_to = User.objects.filter(pk=uid).first() if uid else None
            conv.save(update_fields=["assigned_to"])

        elif action == "set_labels":
            label_ids = request.POST.getlist("labels")
            conv.labels.set(ConversationLabel.objects.filter(pk__in=label_ids))

        elif action == "link_lead":
            from apps.leads.models import Lead
            lead_id = request.POST.get("lead_id", "")
            conv.lead = Lead.objects.filter(pk=lead_id).first() if lead_id else None
            conv.save(update_fields=["lead"])

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": True})
        return redirect("wa:panel_conversation", pk=pk)


# ---------------------------------------------------------------------------
# SIMULADOR — Inyectar mensaje entrante de prueba (solo en DEBUG o sin keys)
# ---------------------------------------------------------------------------

@method_decorator(_wa_asesora_required, name="dispatch")
class WASimulatorView(View):
    """Permite simular un mensaje entrante para probar el flujo sin API de Meta.

    Solo disponible mientras el módulo esté en modo prototipo (sin WHATSAPP_TOKEN
    configurado) o con DEBUG activo — en producción con la API real conectada,
    inyectar mensajes "de cliente" falsos podría contaminar el CRM.
    """

    template_name = "whatsapp/simulator.html"

    def _is_available(self):
        from django.conf import settings
        return settings.DEBUG or not getattr(settings, "WHATSAPP_TOKEN", "")

    def get(self, request):
        from django.http import Http404
        if not self._is_available():
            raise Http404
        convs = WhatsAppConversation.objects.order_by("-last_message_at")[:20]
        return render(request, self.template_name, {
            "conversations": convs,
            **_panel_ctx(request),
        })

    def post(self, request):
        from django.http import Http404
        if not self._is_available():
            raise Http404
        phone        = request.POST.get("phone", "").strip()
        contact_name = request.POST.get("contact_name", "").strip()
        body         = request.POST.get("body", "").strip()
        if phone and body:
            conv = _upsert_inbound_message(
                phone=phone,
                contact_name=contact_name or phone,
                wa_message_id="",
                body=body,
                media_type="text",
            )
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"ok": True, "conv_pk": conv.pk})
            return redirect("wa:panel_conversation", pk=conv.pk)
        return redirect("wa:simulator")


# ---------------------------------------------------------------------------
# DASHADMIN — Vista global de conversaciones
# ---------------------------------------------------------------------------

@da_decorator
class DashWAOverviewView(View):
    template_name = "whatsapp/dash_overview.html"

    def get(self, request):
        from django.contrib.auth.models import User
        status   = request.GET.get("status", "")
        label_id = request.GET.get("label", "")
        asesora  = request.GET.get("asesora", "")
        q        = request.GET.get("q", "").strip()

        qs = (
            WhatsAppConversation.objects
            .select_related("lead", "assigned_to")
            .prefetch_related("labels")
            .order_by("-last_message_at")
        )
        if status:
            qs = qs.filter(status=status)
        if label_id:
            qs = qs.filter(labels__pk=label_id)
        if asesora:
            qs = qs.filter(assigned_to__pk=asesora)
        if q:
            qs = qs.filter(contact_name__icontains=q) | qs.filter(phone__icontains=q)

        # Métricas rápidas
        all_qs = WhatsAppConversation.objects
        metrics = {
            "total":    all_qs.count(),
            "new":      all_qs.filter(status="new").count(),
            "open":     all_qs.filter(status="open").count(),
            "pending":  all_qs.filter(status="pending").count(),
            "resolved": all_qs.filter(status="resolved").count(),
            "unread":   sum(c.unread_count for c in all_qs.only("unread_count")),
        }

        return render(request, self.template_name, {
            "conversations":  qs[:100],
            "metrics":        metrics,
            "labels":         ConversationLabel.objects.all(),
            "status_choices": WhatsAppConversation.Status.choices,
            "asesoras":       User.objects.filter(is_active=True, is_staff=True),
            "current_status": status,
            "current_label":  label_id,
            "current_asesora": asesora,
            "current_q":      q,
        })


# ---------------------------------------------------------------------------
# DASHADMIN — Gestión de etiquetas
# ---------------------------------------------------------------------------

@da_decorator
class DashWALabelsView(View):
    template_name = "whatsapp/dash_labels.html"

    def get(self, request):
        return render(request, self.template_name, {
            "labels":        ConversationLabel.objects.all(),
            "preset_colors": ["#25D366","#3B82F6","#F59E0B","#EF4444","#8B5CF6","#EC4899","#06B6D4","#10B981"],
        })

    def post(self, request):
        action = request.POST.get("action", "create")
        if action == "create":
            name  = request.POST.get("name", "").strip()
            color = request.POST.get("color", "#3B82F6")
            if name:
                ConversationLabel.objects.create(name=name, color=color, created_by=request.user)
        elif action == "delete":
            pk = request.POST.get("pk")
            ConversationLabel.objects.filter(pk=pk).delete()
        elif action == "edit":
            pk    = request.POST.get("pk")
            name  = request.POST.get("name", "").strip()
            color = request.POST.get("color", "#3B82F6")
            if pk and name:
                ConversationLabel.objects.filter(pk=pk).update(name=name, color=color)
        return redirect("wa:dash_labels")


# ---------------------------------------------------------------------------
# DASHADMIN — Asignar conversación a asesora (AJAX)
# ---------------------------------------------------------------------------

@da_decorator
class DashWAAssignView(View):
    def post(self, request, pk):
        from django.contrib.auth.models import User
        conv = get_object_or_404(WhatsAppConversation, pk=pk)
        uid  = request.POST.get("assigned_to", "")
        conv.assigned_to = User.objects.filter(pk=uid).first() if uid else None
        conv.save(update_fields=["assigned_to"])
        return JsonResponse({"ok": True})
