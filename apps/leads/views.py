"""Vistas del módulo Leads."""
from __future__ import annotations

import json
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.views.generic import TemplateView

from apps.core.mixins import BreadcrumbMixin, SEOContextMixin

from .forms import (
    CablingDetailsForm, ContactDetailsForm,
    InterestAreaForm, RentalDetailsForm, SoftwareDetailsForm,
)
from .services import LeadCreator, QuoteCalculator, send_whatsapp_quote_notification

logger = logging.getLogger(__name__)

WIZARD_SESSION_KEY = "quote_wizard_data"


class QuoteWizardView(SEOContextMixin, BreadcrumbMixin, TemplateView):
    template_name = "leads/wizard.html"
    meta_title_default = "Cotizador en Línea | Solution Copiers"
    meta_description_default = (
        "Cotiza fotocopiadoras, cableado o desarrollo de software en 60 segundos."
    )

    def get_breadcrumbs(self):
        return [
            ("Inicio", reverse_lazy("core:home")),
            ("Cotizador", ""),
        ]

    # Áreas válidas que puede recibir como ?servicio=
    _VALID_AREAS = {
        "rental", "sale", "consumables", "cabling",
        "software", "web", "mobile", "database", "full_office",
    }

    def get(self, request, *args, **kwargs):
        preset = request.GET.get("servicio", "").strip()
        if preset in self._VALID_AREAS:
            session_data = request.session.get(WIZARD_SESSION_KEY, {})
            # Solo pre-selecciona si no hay ya una sesión activa con el mismo servicio
            if session_data.get("interest_area") != preset:
                session_data = {
                    "interest_area": preset,
                    "step_1": {"interest_area": preset},
                }
                request.session[WIZARD_SESSION_KEY] = session_data
                request.session.modified = True
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from apps.catalog.models import Copier
        context = super().get_context_data(**kwargs)

        copiers_list = list(
            Copier.published.filter(available_for_rental=True)
            .values("id", "name", "model_number", "toner_type", "monthly_rental_price")
        )
        for c in copiers_list:
            if c.get("monthly_rental_price"):
                c["monthly_rental_price"] = float(c["monthly_rental_price"])

        context["available_copiers"] = json.dumps(copiers_list, ensure_ascii=False)
        context["wizard_session"] = json.dumps(
            self.request.session.get(WIZARD_SESSION_KEY, {}), ensure_ascii=False,
        )
        return context


@method_decorator(csrf_protect, name="dispatch")
class QuoteStepView(View):
    STEP_FORMS = {
        1: InterestAreaForm,
        2: {
            "rental": RentalDetailsForm,
            "sale": RentalDetailsForm,
            "consumables": SoftwareDetailsForm,  # reutilizamos: solo usa project_description
            "cabling": CablingDetailsForm,
            "software": SoftwareDetailsForm,
            "web": SoftwareDetailsForm,
            "mobile": SoftwareDetailsForm,
            "database": SoftwareDetailsForm,
            "full_office": SoftwareDetailsForm,
        },
        3: ContactDetailsForm,
    }

    def post(self, request, step):
        if step not in self.STEP_FORMS:
            return JsonResponse({"ok": False, "error": "Paso inválido"}, status=400)

        session_data = request.session.get(WIZARD_SESSION_KEY, {})

        form_class = self.STEP_FORMS[step]
        if step == 2:
            interest_area = session_data.get("interest_area")
            form_class = form_class.get(interest_area)
            if not form_class:
                return JsonResponse(
                    {"ok": False, "error": "Selecciona primero el área de interés"},
                    status=400,
                )

        form = form_class(request.POST)
        if not form.is_valid():
            return JsonResponse(
                {"ok": False, "errors": form.errors.get_json_data()}, status=400,
            )

        session_data[f"step_{step}"] = form.cleaned_data
        if step == 1:
            session_data["interest_area"] = form.cleaned_data["interest_area"]

        request.session[WIZARD_SESSION_KEY] = session_data
        request.session.modified = True

        return JsonResponse({"ok": True, "step": step})


@method_decorator(csrf_protect, name="dispatch")
class QuoteSubmitView(View):
    def post(self, request):
        session_data = request.session.get(WIZARD_SESSION_KEY, {})
        if not session_data:
            return JsonResponse(
                {"ok": False, "error": "Sesión vacía o expirada"}, status=400,
            )

        try:
            contact_data = session_data.get("step_3", {})
            quote_data = {
                "interest_area": session_data.get("interest_area"),
                "client_message": session_data.get("step_2", {}).get(
                    "project_description", ""
                ),
            }
            wizard_data = {
                **session_data.get("step_2", {}),
                "interest_area": session_data.get("interest_area"),
            }

            quote = LeadCreator.create_from_wizard(
                contact_data=contact_data,
                quote_data=quote_data,
                wizard_data=wizard_data,
            )

            self._notify_sales_team(quote)
            send_whatsapp_quote_notification(quote)  # WhatsApp automático
            request.session.pop(WIZARD_SESSION_KEY, None)

            return JsonResponse({
                "ok": True,
                "quote_id": str(quote.public_id),
                "redirect_url": str(reverse_lazy("leads:thank_you")),
            })

        except Exception as exc:
            logger.exception("Error en submit del wizard: %s", exc)
            return JsonResponse(
                {"ok": False, "error": "Error interno. Intenta de nuevo."},
                status=500,
            )

    @staticmethod
    def _notify_sales_team(quote):
        try:
            subject = f"[Nueva Cotización] {quote.lead.full_name} — {quote.get_interest_area_display()}"
            body = render_to_string("leads/emails/sales_notification.txt", {"quote": quote})
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.LEADS_NOTIFICATION_EMAIL],
                fail_silently=True,
            )
        except Exception as exc:
            logger.warning("No se pudo enviar email: %s", exc)


class ThankYouView(SEOContextMixin, TemplateView):
    template_name = "leads/thank_you.html"
    meta_title_default = "¡Gracias! Hemos recibido tu cotización"
    noindex_default = True


@method_decorator(csrf_protect, name="dispatch")
class CalculateQuoteAPI(View):
    def post(self, request):
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

        interest_area = payload.get("interest_area")
        if not interest_area:
            return JsonResponse(
                {"ok": False, "error": "Falta interest_area"}, status=400,
            )

        estimated = QuoteCalculator.calculate(interest_area, payload)

        range_min = estimated * 0.8 if estimated else 0
        range_max = estimated * 1.2 if estimated else 0

        return JsonResponse({
            "ok": True,
            "estimated_total": float(estimated),
            "range_min": float(range_min),
            "range_max": float(range_max),
            "currency": "COP",
            "formatted": f"${estimated:,.0f} COP",
        })


class SearchConsumableAPI(View):
    """Búsqueda inteligente de insumos: tóner, tintas y repuestos."""

    # Mapa: palabras clave en la búsqueda → tipo de consumible
    KEYWORD_TYPES = {
        "toner":    ["toner_bn", "toner_color", "toner"],
        "toné":     ["toner_bn", "toner_color", "toner"],
        "tinta":    ["ink"],
        "ink":      ["ink"],
        "cartucho": ["ink"],
        "cilindro": ["drum"],
        "drum":     ["drum"],
        "tambor":   ["drum"],
        "rodillo":  ["roller"],
        "cuchilla": ["blade"],
        "banda":    ["fuser"],
        "fusor":    ["fuser"],
        "revelador":["developer"],
        "chip":     ["chip"],
        "kit":      ["kit"],
        "repuesto": ["roller", "blade", "fuser", "drum", "developer", "chip", "other"],
    }

    # Palabras genéricas a ignorar en la búsqueda multi-término
    STOPWORDS = {"de", "la", "el", "los", "las", "para", "con", "sin", "y", "o", "a",
                 "toner", "toné", "tinta", "repuesto", "insumo"}

    def get(self, request):
        query = request.GET.get("q", "").strip()
        if len(query) < 2:
            return JsonResponse({"ok": True, "results": [], "total": 0})

        from apps.catalog.models import Consumable
        from django.db.models import Q

        query_lower = query.lower()

        # Detectar tipo por palabras clave
        type_filter = []
        for kw, types in self.KEYWORD_TYPES.items():
            if kw in query_lower:
                type_filter.extend(types)
        type_filter = list(set(type_filter))

        # Términos significativos (excluir stopwords cortas)
        all_terms = [t for t in query.split() if len(t) >= 2]
        sig_terms = [t for t in all_terms if t.lower() not in self.STOPWORDS] or all_terms

        # Búsqueda: cada término significativo debe aparecer en nombre O código
        # Usar AND entre términos para resultados más precisos
        q_filter = Q()
        for term in sig_terms:
            q_filter &= (Q(name__icontains=term) | Q(part_number__icontains=term))

        qs = Consumable.objects.filter(status="published").filter(q_filter)

        # Si no hay resultados con AND, hacer fallback a OR
        if not qs.exists():
            q_or = Q()
            for term in sig_terms:
                q_or |= Q(name__icontains=term) | Q(part_number__icontains=term)
            qs = Consumable.objects.filter(status="published").filter(q_or)

        # Aplicar filtro de tipo si se detectó
        if type_filter:
            qs = qs.filter(consumable_type__in=type_filter)

        # Priorizar: exactos primero, luego en stock, luego con precio
        results = list(
            qs.order_by("-in_stock", "price")
            .values(
                "id", "name", "part_number", "consumable_type", "brand",
                "price", "price_business", "price_wholesale",
                "price_on_request", "in_stock",
            )[:12]
        )

        # Formatear precios para el frontend
        for r in results:
            r["price_fmt"] = f"${r['price']:,.0f}" if r["price"] else None
            r["price_business_fmt"] = f"${r['price_business']:,.0f}" if r["price_business"] else None
            r["price_wholesale_fmt"] = f"${r['price_wholesale']:,.0f}" if r["price_wholesale"] else None
            r["type_label"] = self._type_label(r["consumable_type"])
            # Convertir Decimal a float para JSON
            for field in ("price", "price_business", "price_wholesale"):
                if r[field] is not None:
                    r[field] = float(r[field])

        return JsonResponse({
            "ok": True,
            "results": results,
            "total": qs.count(),
            "detected_types": list(set(type_filter)) if type_filter else [],
        })

    @staticmethod
    def _type_label(t):
        labels = {
            "toner_bn": "Tóner B/N",
            "toner_color": "Tóner Color",
            "ink": "Tinta/Cartucho",
            "drum": "Cilindro",
            "fuser": "Banda/Fusor",
            "roller": "Rodillo",
            "blade": "Cuchilla",
            "developer": "Revelador",
            "chip": "Chip",
            "kit": "Kit mant.",
            "other": "Repuesto",
        }
        return labels.get(t, "Repuesto")
