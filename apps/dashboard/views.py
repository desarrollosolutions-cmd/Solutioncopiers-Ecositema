"""Panel de administración personalizado — /dashadmin/"""
from __future__ import annotations

import logging
from functools import wraps
from urllib.parse import urlparse

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Avg, Count, Max, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import (
    CreateView, DeleteView, DetailView,
    ListView, TemplateView, UpdateView,
)
from django.urls import reverse, reverse_lazy

_auth_logger = logging.getLogger("apps.auth")

# ---------------------------------------------------------------------------
# Helpers de seguridad
# ---------------------------------------------------------------------------

_MAX_LOGIN_ATTEMPTS = 5
_LOCKOUT_SECONDS    = 900  # 15 minutos


def _client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        # Tomar la primera IP de la cadena (IP del cliente original)
        ip = xff.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "unknown")
    return ip


def _login_cache_key(ip: str, username: str) -> str:
    return f"login_fail:{ip}:{username}"


def _is_locked_out(ip: str, username: str) -> bool:
    return cache.get(_login_cache_key(ip, username), 0) >= _MAX_LOGIN_ATTEMPTS


def _record_failed_login(ip: str, username: str) -> int:
    key   = _login_cache_key(ip, username)
    count = cache.get(key, 0) + 1
    cache.set(key, count, timeout=_LOCKOUT_SECONDS)
    return count


def _clear_failed_logins(ip: str, username: str):
    cache.delete(_login_cache_key(ip, username))


def _safe_next(request, fallback: str) -> str:
    """Valida que el parámetro 'next' sea una URL relativa interna."""
    next_url = request.GET.get("next", "").strip()
    if not next_url:
        return fallback
    parsed = urlparse(next_url)
    # Solo URLs relativas sin host (evita open redirect a dominios externos)
    if parsed.netloc or parsed.scheme or next_url.startswith("//"):
        _auth_logger.warning("Open redirect attempt blocked: %s from %s", next_url, _client_ip(request))
        return fallback
    return next_url

# ---------------------------------------------------------------------------
# Decorador de acceso — solo staff
# ---------------------------------------------------------------------------
def da_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return redirect(f"/dashadmin/acceso/?next={request.path}")
        return view_func(request, *args, **kwargs)
    return wrapper


da_decorator = method_decorator(da_required, name="dispatch")


def superuser_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return redirect(f"/dashadmin/acceso/?next={request.path}")
        return view_func(request, *args, **kwargs)
    return wrapper


su_decorator = method_decorator(superuser_required, name="dispatch")


# ---------------------------------------------------------------------------
# LOGIN / LOGOUT
# ---------------------------------------------------------------------------
class DashboardLoginView(View):
    template_name = "dashboard/login.html"

    def get(self, request):
        if request.user.is_authenticated and request.user.is_staff:
            return redirect("dashboard:home")
        return render(request, self.template_name)

    def post(self, request):
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        ip       = _client_ip(request)

        if _is_locked_out(ip, username):
            _auth_logger.warning("Login bloqueado (brute force) para %s desde %s", username, ip)
            return render(request, self.template_name, {
                "error": "Cuenta temporalmente bloqueada por múltiples intentos fallidos. Intenta de nuevo en 15 minutos."
            })

        user = authenticate(request, username=username, password=password)
        if user and user.is_staff:
            _clear_failed_logins(ip, username)
            login(request, user)
            _auth_logger.info("Login staff exitoso: %s desde %s", username, ip)
            return redirect(_safe_next(request, "dashboard:home"))

        attempts = _record_failed_login(ip, username)
        _auth_logger.warning("Login fallido para '%s' desde %s (intento %d)", username, ip, attempts)
        return render(request, self.template_name, {"error": "Credenciales inválidas o sin permisos de acceso."})


class DashboardLogoutView(View):
    def post(self, request):
        logout(request)
        return redirect("dashboard:login")

    def get(self, request):
        # GET no realiza logout (previene CSRF-via-GET). Solo redirige.
        return redirect("dashboard:login")


# ---------------------------------------------------------------------------
# REPORTES Y ANALYTICS
# ---------------------------------------------------------------------------
@da_decorator
class ReportsView(TemplateView):
    template_name = "dashboard/reports.html"

    def get_context_data(self, **kwargs):
        import json
        from django.db.models.functions import TruncMonth
        from apps.leads.models import Quote, Lead, RentalContract, ServiceTicket

        ctx = super().get_context_data(**kwargs)
        today = timezone.now()

        # ── Últimos 6 meses ────────────────────────────────────────
        months_labels = []
        for i in range(5, -1, -1):
            m = (today.replace(day=1) - timezone.timedelta(days=i * 30)).replace(day=1)
            months_labels.append(m.strftime("%b %Y"))

        def month_series(qs, date_field="created_at"):
            raw = (
                qs.annotate(m=TruncMonth(date_field))
                .values("m").annotate(n=Count("id"))
                .order_by("m")
            )
            by_month = {r["m"].strftime("%b %Y"): r["n"] for r in raw}
            return [by_month.get(lbl, 0) for lbl in months_labels]

        # ── Cotizaciones ───────────────────────────────────────────
        quotes_qs = Quote.objects.all()
        ctx["quotes_by_month"] = json.dumps(month_series(quotes_qs))
        ctx["months_labels"]   = json.dumps(months_labels)

        status_data = {s: 0 for s in ("new", "reviewing", "sent", "won", "lost")}
        for r in quotes_qs.values("status").annotate(n=Count("id")):
            status_data[r["status"]] = r["n"]
        ctx["quotes_by_status"] = json.dumps(list(status_data.values()))
        ctx["quotes_status_labels"] = json.dumps(["Nueva", "En revisión", "Enviada", "Ganada", "Perdida"])

        area_qs = (
            quotes_qs.values("interest_area").annotate(n=Count("id")).order_by("-n")[:6]
        )
        area_map = {k: str(v) for k, v in Quote.InterestArea.choices}
        ctx["quotes_by_area_labels"] = json.dumps([
            area_map.get(r["interest_area"], r["interest_area"]) for r in area_qs
        ])
        ctx["quotes_by_area_data"] = json.dumps([r["n"] for r in area_qs])

        total_q = quotes_qs.count()
        won_q   = quotes_qs.filter(status="won").count()
        ctx["conversion_rate"] = round((won_q / total_q * 100) if total_q else 0, 1)
        ctx["total_quotes"]    = total_q
        ctx["won_quotes"]      = won_q

        ctx["total_quote_value"] = quotes_qs.filter(status="won").aggregate(
            t=Sum("estimated_total")
        )["t"] or 0

        # ── Clientes ───────────────────────────────────────────────
        ctx["clients_by_month"] = json.dumps(month_series(Lead.objects.all()))
        ctx["total_clients"]    = Lead.objects.count()

        source_data = {s: 0 for s, _ in Lead.Source.choices}
        for r in Lead.objects.values("source").annotate(n=Count("id")):
            source_data[r["source"]] = r["n"]
        source_map = {k: str(v) for k, v in Lead.Source.choices}
        ctx["clients_by_source_labels"] = json.dumps(
            [source_map.get(s, s) for s in source_data]
        )
        ctx["clients_by_source_data"] = json.dumps(list(source_data.values()))

        # ── Contratos ──────────────────────────────────────────────
        contracts_qs = RentalContract.objects.all()
        ctx["contracts_active"]   = contracts_qs.filter(status="active").count()
        ctx["contracts_revenue"]  = contracts_qs.filter(status="active").aggregate(
            t=Sum("monthly_rate")
        )["t"] or 0

        cont_status = {s: 0 for s, _ in RentalContract.Status.choices}
        for r in contracts_qs.values("status").annotate(n=Count("id")):
            cont_status[r["status"]] = r["n"]
        cont_map = {k: str(v) for k, v in RentalContract.Status.choices}
        ctx["contracts_by_status_labels"] = json.dumps(
            [cont_map.get(s, s) for s in cont_status]
        )
        ctx["contracts_by_status_data"] = json.dumps(list(cont_status.values()))

        # ── Servicio técnico ───────────────────────────────────────
        tickets_qs = ServiceTicket.objects.all()
        ctx["tickets_total"]    = tickets_qs.count()
        ctx["tickets_open"]     = tickets_qs.filter(status__in=["open", "in_progress", "waiting_parts"]).count()
        ctx["tickets_by_month"] = json.dumps(month_series(tickets_qs))

        tkt_status = {s: 0 for s, _ in ServiceTicket.Status.choices}
        for r in tickets_qs.values("status").annotate(n=Count("id")):
            tkt_status[r["status"]] = r["n"]
        tkt_map  = {k: str(v) for k, v in ServiceTicket.Status.choices}
        ctx["tickets_by_status_labels"] = json.dumps(
            [tkt_map.get(s, s) for s in tkt_status]
        )
        ctx["tickets_by_status_data"] = json.dumps(list(tkt_status.values()))

        issue_map = {k: str(v) for k, v in ServiceTicket.IssueType.choices}
        issue_qs  = tickets_qs.values("issue_type").annotate(n=Count("id")).order_by("-n")
        ctx["tickets_by_type_labels"] = json.dumps(
            [issue_map.get(r["issue_type"], r["issue_type"]) for r in issue_qs]
        )
        ctx["tickets_by_type_data"] = json.dumps([r["n"] for r in issue_qs])

        resolved = tickets_qs.exclude(resolved_at=None).values_list(
            "created_at", "resolved_at"
        )
        if resolved:
            avg_hours = sum(
                (r - c).total_seconds() / 3600 for c, r in resolved
            ) / len(resolved)
            ctx["avg_resolution_hours"] = round(avg_hours, 1)
        else:
            ctx["avg_resolution_hours"] = None

        # ── Razones de pérdida ─────────────────────────────────────────
        lost_quotes = quotes_qs.filter(status="lost")
        ctx["lost_total"] = lost_quotes.count()

        # Por categoría
        cat_map = {k: str(v) for k, v in Quote.LostCategory.choices}
        cat_qs = (
            lost_quotes.exclude(lost_category="")
            .values("lost_category").annotate(n=Count("id")).order_by("-n")
        )
        ctx["lost_by_category_labels"] = json.dumps(
            [cat_map.get(r["lost_category"], r["lost_category"]) for r in cat_qs]
        )
        ctx["lost_by_category_data"] = json.dumps([r["n"] for r in cat_qs])

        # Las últimas cotizaciones perdidas con razón
        ctx["recent_lost"] = (
            lost_quotes.exclude(lost_reason="")
            .select_related("lead")
            .order_by("-closed_at", "-created_at")[:8]
        )

        # Tasa de conversión real: won / (won + lost)
        closed = won_q + ctx["lost_total"]
        ctx["win_rate_closed"] = round((won_q / closed * 100) if closed else 0, 1)

        # Área con más pérdidas
        lost_by_area = (
            lost_quotes.values("interest_area").annotate(n=Count("id")).order_by("-n")[:5]
        )
        ctx["lost_by_area_labels"] = json.dumps(
            [area_map.get(r["interest_area"], r["interest_area"]) for r in lost_by_area]
        )
        ctx["lost_by_area_data"] = json.dumps([r["n"] for r in lost_by_area])

        return ctx


# ---------------------------------------------------------------------------
# DASHBOARD HOME — Estadísticas
# ---------------------------------------------------------------------------
@da_decorator
class DashboardHomeView(TemplateView):
    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        from apps.leads.models import Quote, Lead
        from apps.catalog.models import Consumable, Copier
        from apps.blog.models import Post
        from apps.encuestas.models import Encuesta

        ctx = super().get_context_data(**kwargs)
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # ── Cotizaciones ──
        quotes_qs = Quote.objects.all()
        ctx["quotes_total"]    = quotes_qs.count()
        ctx["quotes_today"]    = quotes_qs.filter(created_at__gte=today_start).count()
        ctx["quotes_month"]    = quotes_qs.filter(created_at__gte=month_start).count()
        ctx["quotes_new"]      = quotes_qs.filter(status="new").count()
        ctx["quotes_won"]      = quotes_qs.filter(status="won").count()

        ctx["quotes_by_status"] = list(
            quotes_qs.values("status").annotate(n=Count("id")).order_by("-n")
        )
        ctx["quotes_by_area"] = list(
            quotes_qs.values("interest_area").annotate(n=Count("id")).order_by("-n")[:6]
        )
        ctx["recent_quotes"] = (
            quotes_qs.select_related("lead")
            .order_by("-created_at")[:8]
        )

        # ── Catálogo ──
        ctx["copiers_total"]     = Copier.objects.count()
        ctx["copiers_published"] = Copier.objects.filter(status="published").count()
        ctx["consumables_total"] = Consumable.objects.count()
        ctx["consumables_stock"] = Consumable.objects.filter(in_stock=True).count()

        # ── Blog ──
        ctx["posts_total"]     = Post.objects.count()
        ctx["posts_published"] = Post.objects.filter(status="published").count()

        # ── Encuestas ──
        ctx["surveys_total"] = Encuesta.objects.count()
        avg = Encuesta.objects.aggregate(
            avg=Avg("calificacion_atencion") + Avg("calificacion_servicio") +
                Avg("calificacion_tiempo")   + Avg("calificacion_precio")
        )
        ctx["surveys_avg"] = round((avg["avg"] or 0) / 4, 1)

        # ── Leads ──
        ctx["leads_total"] = Lead.objects.count()
        ctx["leads_month"] = Lead.objects.filter(created_at__gte=month_start).count()

        # ── Contratos ──
        from apps.leads.models import RentalContract, ServiceTicket
        from datetime import timedelta
        today = timezone.now().date()
        ctx["contracts_active"]   = RentalContract.objects.filter(status="active").count()
        ctx["contracts_expiring"] = RentalContract.objects.filter(
            status="active",
            end_date__range=(today, today + timedelta(days=30))
        ).select_related("lead").order_by("end_date")[:5]

        # ── Tickets abiertos ──
        ctx["tickets_open"] = ServiceTicket.objects.filter(
            status__in=("open","in_progress","waiting_parts")
        ).count()

        # ── Badge campana: cotizaciones sin atender + contratos por vencer ──
        cutoff = timezone.now() - timedelta(days=3)
        ctx["pending_notify_count"] = (
            Quote.objects.filter(status="new", created_at__lte=cutoff).count() +
            RentalContract.objects.filter(
                status="active",
                end_date__range=(today, today + timedelta(days=30))
            ).count()
        )

        # ── Mi Día ──────────────────────────────────────────────────────────
        from apps.leads.models import FollowUpTask
        ctx["tasks_today"]    = FollowUpTask.objects.filter(due_date=today, is_done=False).select_related("lead")[:10]
        ctx["tasks_overdue"]  = FollowUpTask.objects.filter(due_date__lt=today, is_done=False).select_related("lead").order_by("due_date")[:8]
        ctx["quotes_pending"] = (
            Quote.objects.filter(status="new")
            .select_related("lead")
            .order_by("created_at")[:8]
        )
        ctx["today"]          = today

        # ── CRM Notificaciones sin leer ──────────────────────────────────────
        from apps.dashboard.models import Notification
        ctx["unread_notifications"] = Notification.objects.filter(
            user=self.request.user, is_read=False
        ).count()

        # ── Pedidos online y contabilidad del mes ─────────────────────────
        try:
            from apps.payments.models import Order, Invoice, Payment
            ctx["orders_pending"]  = Order.objects.filter(status="pending").count()
            ctx["orders_paid_month"] = Order.objects.filter(
                status="paid", created_at__gte=month_start
            ).aggregate(n=Count("id"), total=Sum("total"))
            ctx["recent_orders"] = (
                Order.objects.filter(status="paid")
                .order_by("-created_at")[:5]
            )
            ctx["invoices_por_cobrar"] = Invoice.objects.filter(
                status__in=["issued", "sent"]
            ).aggregate(n=Count("id"), total=Sum("total"))
            ctx["invoices_vencidas"] = Invoice.objects.filter(
                status__in=["issued", "sent"],
                due_date__lt=today,
            ).count()
        except Exception:
            pass

        return ctx


# ---------------------------------------------------------------------------
# CONTRATOS DE ALQUILER
# ---------------------------------------------------------------------------
def _next_contract_number():
    from apps.leads.models import RentalContract
    from datetime import date as _date
    prefix = f"CTR-{_date.today().strftime('%Y%m')}-"
    last = (
        RentalContract.objects
        .filter(contract_number__startswith=prefix)
        .order_by("contract_number")
        .last()
    )
    if last:
        try:
            seq = int(last.contract_number.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


@da_decorator
class ContractListView(ListView):
    template_name = "dashboard/contracts/list.html"
    context_object_name = "contracts"
    paginate_by = 20

    def get_queryset(self):
        from apps.leads.models import RentalContract
        from datetime import date
        qs = RentalContract.objects.select_related("lead", "copier").order_by("-created_at")
        status = self.request.GET.get("status", "")
        q      = self.request.GET.get("q", "").strip()
        alert  = self.request.GET.get("alert", "")
        if status:
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(
                Q(lead__full_name__icontains=q) |
                Q(lead__company_name__icontains=q) |
                Q(contract_number__icontains=q) |
                Q(equipment_description__icontains=q)
            )
        if alert == "expiring":
            today = date.today()
            from datetime import timedelta
            qs = qs.filter(
                status="active",
                end_date__range=(today, today + timedelta(days=30))
            )
        return qs

    def get_context_data(self, **kwargs):
        from apps.leads.models import RentalContract
        from datetime import date, timedelta
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"]    = RentalContract.Status.choices
        ctx["current_status"]    = self.request.GET.get("status", "")
        ctx["current_q"]         = self.request.GET.get("q", "")
        ctx["current_alert"]     = self.request.GET.get("alert", "")
        today = date.today()
        ctx["total_active"]      = RentalContract.objects.filter(status="active").count()
        ctx["total_expiring"]    = RentalContract.objects.filter(
            status="active", end_date__range=(today, today + timedelta(days=30))
        ).count()
        ctx["total_expired"]     = RentalContract.objects.filter(status="expired").count()
        return ctx


@da_decorator
class ContractCreateView(View):
    template_name = "dashboard/contracts/form.html"

    def _get_context(self, data=None):
        from apps.leads.models import Lead, RentalContract
        from apps.catalog.models import Copier
        return {
            "lead_list":   Lead.objects.order_by("full_name"),
            "copier_list": Copier.objects.filter(status="published").order_by("name"),
            "status_choices": RentalContract.Status.choices,
            "next_number": _next_contract_number(),
            "is_edit": False,
        }

    def get(self, request):
        return render(request, self.template_name, self._get_context())

    def post(self, request):
        from apps.leads.models import Lead, RentalContract
        from apps.catalog.models import Copier
        try:
            lead   = Lead.objects.get(pk=request.POST["lead"])
            copier = None
            if request.POST.get("copier"):
                copier = Copier.objects.get(pk=request.POST["copier"])
            contract = RentalContract.objects.create(
                lead=lead,
                copier=copier,
                equipment_description=request.POST.get("equipment_description", ""),
                contract_number=request.POST.get("contract_number") or _next_contract_number(),
                status=request.POST.get("status", "active"),
                start_date=request.POST["start_date"],
                end_date=request.POST.get("end_date") or None,
                monthly_rate=request.POST["monthly_rate"],
                copies_included=request.POST.get("copies_included") or 0,
                copy_overage_rate=request.POST.get("copy_overage_rate") or None,
                notes=request.POST.get("notes", ""),
            )
            from django.contrib import messages
            messages.success(request, f"Contrato {contract.contract_number} creado correctamente.")
            return redirect("dashboard:contract_detail", pk=contract.pk)
        except Exception as e:
            ctx = self._get_context()
            ctx["error"] = str(e)
            ctx["post_data"] = request.POST
            return render(request, self.template_name, ctx)


@da_decorator
class ContractDetailView(View):
    template_name = "dashboard/contracts/form.html"

    def _get_contract(self, pk):
        from apps.leads.models import RentalContract
        return get_object_or_404(
            RentalContract.objects.select_related("lead", "copier"), pk=pk
        )

    def _get_context(self, contract):
        from apps.leads.models import Lead, RentalContract, MeterReading
        from apps.catalog.models import Copier
        import json

        readings = list(MeterReading.objects.filter(contract=contract).order_by("-reading_date")[:24])
        included = contract.copies_included or 0

        # Métricas calculadas
        pages_list = [r.pages_printed for r in readings if r.pages_printed > 0]
        avg_pages  = round(sum(pages_list) / len(pages_list)) if pages_list else 0

        trend_pct = None
        if len(readings) >= 2:
            curr_p, prev_p = readings[0].pages_printed, readings[1].pages_printed
            if prev_p > 0:
                trend_pct = round((curr_p - prev_p) / prev_p * 100)

        total_overage = float(sum(r.overage_charge for r in readings))

        # Barra de cuota por lectura (para la tabla)
        for r in readings:
            r.quota_pct = min(round(r.pages_printed / included * 100), 100) if included else 0

        # Datos para la gráfica de barras (últimas 6 lecturas, orden cronológico)
        chart_src  = list(reversed(readings[:6]))
        max_pages  = max((r.pages_printed for r in chart_src), default=1) or 1
        chart_json = json.dumps([{
            "label":  r.reading_date.strftime("%b %y"),
            "pages":  r.pages_printed,
            "pct":    round(r.pages_printed / max_pages * 100),
            "over":   r.overage_pages > 0,
            "charge": float(r.overage_charge) if r.overage_charge else 0,
            "included": included,
        } for r in chart_src])

        return {
            "contract":       contract,
            "lead_list":      Lead.objects.order_by("full_name"),
            "copier_list":    Copier.objects.filter(status="published").order_by("name"),
            "status_choices": RentalContract.Status.choices,
            "meter_readings": readings,
            "is_edit":        True,
            # Analytics de medidor
            "avg_pages":      avg_pages,
            "trend_pct":      trend_pct,
            "total_overage":  total_overage,
            "last_reading":   readings[0] if readings else None,
            "chart_json":     chart_json,
            "copies_included": included,
        }

    def get(self, request, pk):
        contract = self._get_contract(pk)
        return render(request, self.template_name, self._get_context(contract))

    def post(self, request, pk):
        from apps.leads.models import Lead, RentalContract
        from apps.catalog.models import Copier
        contract = self._get_contract(pk)
        try:
            contract.lead   = Lead.objects.get(pk=request.POST["lead"])
            contract.copier = None
            if request.POST.get("copier"):
                contract.copier = Copier.objects.get(pk=request.POST["copier"])
            contract.equipment_description = request.POST.get("equipment_description", "")
            contract.contract_number       = request.POST.get("contract_number", contract.contract_number)
            contract.status      = request.POST.get("status", contract.status)
            contract.start_date  = request.POST["start_date"]
            contract.end_date    = request.POST.get("end_date") or None
            contract.monthly_rate     = request.POST["monthly_rate"]
            contract.copies_included  = request.POST.get("copies_included") or 0
            contract.copy_overage_rate = request.POST.get("copy_overage_rate") or None
            contract.notes = request.POST.get("notes", "")
            contract.save()
            from django.contrib import messages
            messages.success(request, "Contrato actualizado correctamente.")
            return redirect("dashboard:contract_detail", pk=pk)
        except Exception as e:
            ctx = self._get_context(contract)
            ctx["error"] = str(e)
            return render(request, self.template_name, ctx)


# ---------------------------------------------------------------------------
# TICKETS DE SERVICIO TÉCNICO
# ---------------------------------------------------------------------------
def _next_ticket_number():
    from apps.leads.models import ServiceTicket
    from datetime import date as _date
    prefix = f"TKT-{_date.today().strftime('%Y%m')}-"
    last = (
        ServiceTicket.objects
        .filter(ticket_number__startswith=prefix)
        .order_by("ticket_number").last()
    )
    seq = 1
    if last:
        try:
            seq = int(last.ticket_number.split("-")[-1]) + 1
        except ValueError:
            pass
    return f"{prefix}{seq:04d}"


def _create_delivery_task_for_ticket(ticket, created_by):
    """Genera un DeliveryTask en la ruta del técnico al asignarle un ticket."""
    from apps.dashboard.models import DeliveryTask
    if not ticket.assigned_to:
        return
    try:
        field_user = ticket.assigned_to.field_profile
    except Exception:
        return  # El técnico no tiene perfil de campo activo
    due_date = ticket.scheduled_for.date() if ticket.scheduled_for else None
    DeliveryTask.objects.create(
        field_user=field_user,
        title=f"{ticket.get_issue_type_display()} — {ticket.ticket_number}",
        description=(
            f"Cliente: {ticket.lead.full_name}\n"
            f"Equipo: {ticket.equipment_description}\n\n"
            f"{ticket.description}"
        ).strip(),
        address=ticket.lead.city or "",
        client_name=ticket.lead.full_name,
        due_date=due_date,
        created_by=created_by,
    )


@da_decorator
class TicketListView(ListView):
    template_name = "dashboard/tickets/list.html"
    context_object_name = "tickets"
    paginate_by = 25

    def get_queryset(self):
        from apps.leads.models import ServiceTicket
        qs = ServiceTicket.objects.select_related("lead", "assigned_to", "contract").order_by("-created_at")
        status   = self.request.GET.get("status", "")
        priority = self.request.GET.get("priority", "")
        q        = self.request.GET.get("q", "").strip()
        if status:
            qs = qs.filter(status=status)
        if priority:
            qs = qs.filter(priority=priority)
        if q:
            qs = qs.filter(
                Q(lead__full_name__icontains=q) |
                Q(lead__company_name__icontains=q) |
                Q(ticket_number__icontains=q) |
                Q(description__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        from apps.leads.models import ServiceTicket
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"]   = ServiceTicket.Status.choices
        ctx["priority_choices"] = ServiceTicket.Priority.choices
        ctx["current_status"]   = self.request.GET.get("status", "")
        ctx["current_priority"] = self.request.GET.get("priority", "")
        ctx["current_q"]        = self.request.GET.get("q", "")
        ctx["count_open"]       = ServiceTicket.objects.filter(status="open").count()
        ctx["count_progress"]   = ServiceTicket.objects.filter(status="in_progress").count()
        ctx["count_waiting"]    = ServiceTicket.objects.filter(status="waiting_parts").count()
        ctx["count_resolved"]   = ServiceTicket.objects.filter(status="resolved").count()
        from django.contrib.auth.models import User
        ctx["technicians"] = User.objects.filter(field_profile__role="tecnico")
        return ctx


@da_decorator
class TicketCreateView(View):
    template_name = "dashboard/tickets/form.html"

    def _get_context(self):
        from apps.leads.models import Lead, ServiceTicket, RentalContract
        from django.contrib.auth.models import User
        return {
            "lead_list":        Lead.objects.order_by("full_name"),
            "contract_list":    RentalContract.objects.filter(status="active").select_related("lead").order_by("-created_at"),
            "technician_list":  User.objects.filter(field_profile__role="tecnico"),
            "issue_choices":    ServiceTicket.IssueType.choices,
            "priority_choices": ServiceTicket.Priority.choices,
            "status_choices":   ServiceTicket.Status.choices,
            "next_number":      _next_ticket_number(),
            "is_edit":          False,
        }

    def get(self, request):
        return render(request, self.template_name, self._get_context())

    def post(self, request):
        from apps.leads.models import Lead, ServiceTicket, RentalContract
        from django.contrib.auth.models import User
        try:
            lead     = Lead.objects.get(pk=request.POST["lead"])
            contract = None
            if request.POST.get("contract"):
                contract = RentalContract.objects.get(pk=request.POST["contract"])
            assigned = None
            if request.user.is_superuser and request.POST.get("assigned_to"):
                assigned = User.objects.get(pk=request.POST["assigned_to"])
            ticket = ServiceTicket.objects.create(
                ticket_number       = request.POST.get("ticket_number") or _next_ticket_number(),
                lead                = lead,
                contract            = contract,
                equipment_description = request.POST.get("equipment_description", ""),
                issue_type          = request.POST.get("issue_type", "repair"),
                priority            = request.POST.get("priority", "medium"),
                status              = request.POST.get("status", "open"),
                description         = request.POST.get("description", ""),
                resolution_notes    = request.POST.get("resolution_notes", ""),
                assigned_to         = assigned,
                scheduled_for       = request.POST.get("scheduled_for") or None,
            )
            _create_delivery_task_for_ticket(ticket, request.user)
            from django.contrib import messages
            messages.success(request, f"Ticket {ticket.ticket_number} creado.")
            return redirect("dashboard:ticket_detail", pk=ticket.pk)
        except Exception as e:
            ctx = self._get_context()
            ctx["error"] = str(e)
            return render(request, self.template_name, ctx)


@da_decorator
class TicketDetailView(View):
    template_name = "dashboard/tickets/form.html"

    def _get_ticket(self, pk):
        from apps.leads.models import ServiceTicket
        return get_object_or_404(
            ServiceTicket.objects.select_related("lead", "assigned_to", "contract"), pk=pk
        )

    def _get_context(self, ticket):
        from apps.leads.models import Lead, ServiceTicket, RentalContract
        from django.contrib.auth.models import User
        return {
            "ticket":           ticket,
            "lead_list":        Lead.objects.order_by("full_name"),
            "contract_list":    RentalContract.objects.filter(
                Q(status="active") | Q(lead=ticket.lead)
            ).select_related("lead").order_by("-created_at"),
            "technician_list":  User.objects.filter(field_profile__role="tecnico"),
            "issue_choices":    ServiceTicket.IssueType.choices,
            "priority_choices": ServiceTicket.Priority.choices,
            "status_choices":   ServiceTicket.Status.choices,
            "is_edit":          True,
        }

    def get(self, request, pk):
        ticket = self._get_ticket(pk)
        return render(request, self.template_name, self._get_context(ticket))

    def post(self, request, pk):
        from apps.leads.models import Lead, ServiceTicket, RentalContract
        from django.contrib.auth.models import User
        from django.utils import timezone as tz
        ticket = self._get_ticket(pk)
        try:
            ticket.lead     = Lead.objects.get(pk=request.POST["lead"])
            ticket.contract = None
            if request.POST.get("contract"):
                ticket.contract = RentalContract.objects.get(pk=request.POST["contract"])
            prev_assigned = ticket.assigned_to
            if request.user.is_superuser:
                ticket.assigned_to = None
                if request.POST.get("assigned_to"):
                    ticket.assigned_to = User.objects.get(pk=request.POST["assigned_to"])
            old_status = ticket.status
            ticket.equipment_description = request.POST.get("equipment_description", "")
            ticket.issue_type         = request.POST.get("issue_type", ticket.issue_type)
            ticket.priority           = request.POST.get("priority", ticket.priority)
            ticket.status             = request.POST.get("status", ticket.status)
            ticket.description        = request.POST.get("description", "")
            ticket.resolution_notes   = request.POST.get("resolution_notes", "")
            ticket.scheduled_for      = request.POST.get("scheduled_for") or None
            if ticket.status == "resolved" and old_status != "resolved":
                ticket.resolved_at = tz.now()
            ticket.save()
            # Si se asignó técnico por primera vez o cambió, crear tarea en su ruta
            if ticket.assigned_to and ticket.assigned_to != prev_assigned:
                _create_delivery_task_for_ticket(ticket, request.user)
            from django.contrib import messages
            messages.success(request, "Ticket actualizado.")
            return redirect("dashboard:ticket_detail", pk=pk)
        except Exception as e:
            ctx = self._get_context(ticket)
            ctx["error"] = str(e)
            return render(request, self.template_name, ctx)


# ---------------------------------------------------------------------------
# CLIENTES (CRM)
# ---------------------------------------------------------------------------
@da_decorator
class ClientListView(ListView):
    template_name = "dashboard/clients/list.html"
    context_object_name = "clients"
    paginate_by = 25

    def get_queryset(self):
        from apps.leads.models import Lead
        sort = self.request.GET.get("sort", "-created_at")
        allowed_sorts = {
            "name": "full_name", "-name": "-full_name",
            "score": "score", "-score": "-score",
            "activity": "last_activity", "-activity": "-last_activity",
            "created": "created_at", "-created": "-created_at",
        }
        order = allowed_sorts.get(sort, "-created_at")
        qs = Lead.objects.annotate(
            quotes_count=Count("quotes", distinct=True),
            last_quote_date=Max("quotes__created_at"),
            last_activity=Max("activities__created_at"),
        ).order_by(order)
        q      = self.request.GET.get("q", "").strip()
        source = self.request.GET.get("source", "")
        score_min = self.request.GET.get("score_min", "")
        if q:
            qs = qs.filter(
                Q(full_name__icontains=q) |
                Q(email__icontains=q) |
                Q(company_name__icontains=q) |
                Q(phone__icontains=q) |
                Q(nit__icontains=q)
            )
        if source:
            qs = qs.filter(source=source)
        if score_min:
            try:
                qs = qs.filter(score__gte=int(score_min))
            except ValueError:
                pass
        return qs

    def get_context_data(self, **kwargs):
        from apps.leads.models import Lead
        ctx = super().get_context_data(**kwargs)
        ctx["source_choices"]  = Lead.Source.choices
        ctx["current_q"]       = self.request.GET.get("q", "")
        ctx["current_source"]  = self.request.GET.get("source", "")
        ctx["current_sort"]    = self.request.GET.get("sort", "-created_at")
        ctx["current_score_min"] = self.request.GET.get("score_min", "")
        ctx["total_clients"]  = Lead.objects.count()
        from django.utils import timezone
        ctx["new_this_month"] = Lead.objects.filter(
            created_at__gte=timezone.now().replace(day=1, hour=0, minute=0, second=0)
        ).count()
        return ctx


@da_decorator
class ClientAutocompleteView(View):
    """GET /clientes/autocomplete/?q=… → JSON para el buscador inteligente."""
    def get(self, request):
        from apps.leads.models import Lead
        q = request.GET.get("q", "").strip()
        if len(q) < 2:
            return JsonResponse({"results": []})
        qs = Lead.objects.filter(
            Q(full_name__icontains=q) |
            Q(company_name__icontains=q) |
            Q(email__icontains=q) |
            Q(phone__icontains=q) |
            Q(nit__icontains=q)
        ).order_by("-created_at")[:8]
        results = [
            {
                "id":           lead.pk,
                "full_name":    lead.full_name,
                "company_name": lead.company_name or "",
                "email":        lead.email or "",
                "phone":        lead.phone or "",
                "initial":      lead.full_name[0].upper() if lead.full_name else "?",
                "url":          f"/dashadmin/clientes/{lead.pk}/",
            }
            for lead in qs
        ]
        return JsonResponse({"results": results})


@da_decorator
class ClientDetailView(View):
    template_name = "dashboard/clients/detail.html"

    def get(self, request, pk):
        from apps.leads.models import Lead, Quote, LeadActivity, FollowUpTask, EmailLog, RentalContract, ServiceTicket
        lead   = get_object_or_404(Lead, pk=pk)
        quotes = Quote.objects.filter(lead=lead).order_by("-created_at")
        return render(request, self.template_name, {
            "lead":          lead,
            "quotes":        quotes,
            "quotes_count":  quotes.count(),
            "won_count":     quotes.filter(status="won").count(),
            "total_value":   quotes.filter(status="won").aggregate(t=Sum("estimated_total"))["t"] or 0,
            "activities":    LeadActivity.objects.filter(lead=lead).select_related("created_by").order_by("-created_at")[:30],
            "tasks":         FollowUpTask.objects.filter(lead=lead).order_by("is_done", "due_date"),
            "email_logs":    EmailLog.objects.filter(lead=lead).order_by("-created_at")[:20],
            "contracts":     RentalContract.objects.filter(lead=lead).order_by("-created_at"),
            "tickets":       ServiceTicket.objects.filter(lead=lead).order_by("-created_at")[:10],
            "activity_types": LeadActivity.ActivityType.choices,
        })

    def post(self, request, pk):
        from apps.leads.models import Lead
        lead = get_object_or_404(Lead, pk=pk)
        lead.notes_internal = request.POST.get("notes_internal", "")
        lead.full_name    = request.POST.get("full_name", lead.full_name)
        lead.phone        = request.POST.get("phone", lead.phone)
        lead.company_name = request.POST.get("company_name", lead.company_name)
        lead.job_title    = request.POST.get("job_title", lead.job_title)
        lead.city         = request.POST.get("city", lead.city)
        lead.save(update_fields=[
            "notes_internal", "full_name", "phone", "company_name", "job_title", "city"
        ])
        from django.contrib import messages
        messages.success(request, "Cliente actualizado correctamente.")
        return redirect("dashboard:client_detail", pk=pk)


@da_decorator
class ActivityCreateView(View):
    """POST: crea una LeadActivity para el lead indicado."""
    def post(self, request, pk):
        from apps.leads.models import Lead, LeadActivity
        lead = get_object_or_404(Lead, pk=pk)
        notes = request.POST.get("notes", "").strip()
        if notes:
            LeadActivity.objects.create(
                lead=lead,
                activity_type=request.POST.get("activity_type", "note"),
                notes=notes,
                outcome=request.POST.get("outcome", ""),
                created_by=request.user,
            )
            from django.contrib import messages
            messages.success(request, "Actividad registrada.")
        return redirect("dashboard:client_detail", pk=pk)


@da_decorator
class TaskCreateView(View):
    """POST: crea un FollowUpTask para el lead indicado."""
    def post(self, request, pk):
        from apps.leads.models import Lead, FollowUpTask
        from django.contrib.auth.models import User
        lead = get_object_or_404(Lead, pk=pk)
        description = request.POST.get("description", "").strip()
        due_date    = request.POST.get("due_date", "")
        if description and due_date:
            assigned_id = request.POST.get("assigned_to", "")
            assigned = User.objects.filter(pk=assigned_id).first() if assigned_id else request.user
            FollowUpTask.objects.create(
                lead=lead,
                description=description,
                due_date=due_date,
                assigned_to=assigned,
            )
            from django.contrib import messages
            messages.success(request, "Tarea creada.")
        return redirect("dashboard:client_detail", pk=pk)


@da_decorator
class TaskToggleView(View):
    """POST: marca/desmarca una tarea como completada."""
    def post(self, request, pk):
        from apps.leads.models import FollowUpTask
        task = get_object_or_404(FollowUpTask, pk=pk)
        task.is_done = not task.is_done
        task.done_at = timezone.now() if task.is_done else None
        task.save(update_fields=["is_done", "done_at"])
        # Redirect back to client detail
        return redirect("dashboard:client_detail", pk=task.lead_id)


# ---------------------------------------------------------------------------
# EXPORT CSV
# ---------------------------------------------------------------------------
def _csv_response(filename):
    resp = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@da_decorator
class ExportLeadsCSVView(View):
    def get(self, request):
        from apps.leads.models import Lead
        import csv as csv_mod
        resp   = _csv_response("leads.csv")
        writer = csv_mod.writer(resp)
        writer.writerow(["Nombre", "Empresa", "Email", "Teléfono", "Ciudad", "Tamaño", "Cargo", "Fuente", "Creado"])
        for lead in Lead.objects.order_by("-created_at"):
            writer.writerow([
                lead.full_name, lead.company_name, lead.email, lead.phone,
                lead.city, lead.company_size, lead.job_title, lead.source,
                lead.created_at.strftime("%Y-%m-%d"),
            ])
        return resp


@da_decorator
class ExportQuotesCSVView(View):
    def get(self, request):
        from apps.leads.models import Quote
        import csv as csv_mod
        resp   = _csv_response("cotizaciones.csv")
        writer = csv_mod.writer(resp)
        writer.writerow(["ID", "Cliente", "Empresa", "Email", "Área", "Estado", "Total", "Motivo pérdida", "Creado", "Cerrado"])
        for q in Quote.objects.select_related("lead").order_by("-created_at"):
            writer.writerow([
                str(q.public_id)[:8], q.lead.full_name, q.lead.company_name,
                q.lead.email, q.interest_area, q.status,
                str(q.estimated_total or ""), q.lost_reason,
                q.created_at.strftime("%Y-%m-%d"),
                q.closed_at.strftime("%Y-%m-%d") if q.closed_at else "",
            ])
        return resp


@da_decorator
class ExportContractsCSVView(View):
    def get(self, request):
        from apps.leads.models import RentalContract
        import csv as csv_mod
        resp   = _csv_response("contratos.csv")
        writer = csv_mod.writer(resp)
        writer.writerow(["Contrato", "Cliente", "Empresa", "Equipo", "Estado", "Cuota", "Inicio", "Vencimiento"])
        for c in RentalContract.objects.select_related("lead").order_by("-created_at"):
            writer.writerow([
                c.contract_number, c.lead.full_name, c.lead.company_name,
                c.equipment_description, c.status, str(c.monthly_rate),
                str(c.start_date), str(c.end_date) if c.end_date else "",
            ])
        return resp


# ---------------------------------------------------------------------------
# COTIZACIONES
# ---------------------------------------------------------------------------
@da_decorator
class QuoteListView(ListView):
    template_name = "dashboard/quotes/list.html"
    context_object_name = "quotes"
    paginate_by = 20

    def get_queryset(self):
        from apps.leads.models import Quote
        qs = Quote.objects.select_related("lead").order_by("-created_at")
        status = self.request.GET.get("status")
        area   = self.request.GET.get("area")
        q      = self.request.GET.get("q", "").strip()
        if status:
            qs = qs.filter(status=status)
        if area:
            qs = qs.filter(interest_area=area)
        if q:
            qs = qs.filter(
                Q(lead__full_name__icontains=q) |
                Q(lead__email__icontains=q) |
                Q(lead__phone__icontains=q) |
                Q(lead__company_name__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        from apps.leads.models import Quote
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = Quote.Status.choices
        ctx["area_choices"]   = Quote.InterestArea.choices
        ctx["current_status"] = self.request.GET.get("status", "")
        ctx["current_area"]   = self.request.GET.get("area", "")
        ctx["current_q"]      = self.request.GET.get("q", "")
        return ctx


@da_decorator
class QuoteDetailView(DetailView):
    template_name = "dashboard/quotes/detail.html"
    context_object_name = "quote"

    def get_queryset(self):
        from apps.leads.models import Quote
        return Quote.objects.select_related("lead", "assigned_to").prefetch_related("items")


class QuoteStatusUpdateView(View):
    @method_decorator(da_required)
    def post(self, request, pk):
        from apps.leads.models import Quote
        quote = get_object_or_404(Quote, pk=pk)
        new_status = request.POST.get("status")
        if new_status in dict(Quote.Status.choices):
            quote.status = new_status
            update_fields = ["status"]
            if new_status in ("won", "lost"):
                quote.closed_at = timezone.now()
                update_fields.append("closed_at")
            if new_status == "lost":
                lost_reason = request.POST.get("lost_reason", "").strip()
                lost_category = request.POST.get("lost_category", "")
                if lost_reason:
                    quote.lost_reason = lost_reason
                    update_fields.append("lost_reason")
                if lost_category in dict(Quote.LostCategory.choices):
                    quote.lost_category = lost_category
                    update_fields.append("lost_category")
            quote.save(update_fields=update_fields)
        return redirect("dashboard:quote_detail", pk=pk)


@da_decorator
class QuoteProposalView(View):
    """Vista de propuesta profesional print-optimized para una cotización."""
    template_name = "dashboard/quotes/proposal.html"

    def get(self, request, pk):
        from apps.leads.models import Quote, QuoteItem
        quote = get_object_or_404(
            Quote.objects.select_related("lead", "assigned_to"), pk=pk
        )
        items = QuoteItem.objects.filter(quote=quote)
        return render(request, self.template_name, {
            "quote": quote,
            "items": items,
            "today": timezone.now().date(),
        })


class QuoteNotesUpdateView(View):
    @method_decorator(da_required)
    def post(self, request, pk):
        from apps.leads.models import Quote
        quote = get_object_or_404(Quote, pk=pk)
        quote.lead.notes_internal = request.POST.get("notes", "")
        quote.lead.save(update_fields=["notes_internal"])
        return redirect("dashboard:quote_detail", pk=pk)


@da_decorator
class PipelineView(TemplateView):
    template_name = "dashboard/quotes/pipeline.html"

    def get_context_data(self, **kwargs):
        from apps.leads.models import Quote
        ctx = super().get_context_data(**kwargs)

        # Probabilidades por etapa (estándar de industria)
        STAGE_PROB = {
            "new": 10, "reviewing": 25, "sent": 50, "won": 100, "lost": 0,
        }

        stages = [
            {"key": "new",       "label": "Nuevas",             "css_color": "var(--color-primary)", "prob": 10},
            {"key": "reviewing", "label": "En revisión",         "css_color": "#D97706",              "prob": 25},
            {"key": "sent",      "label": "Enviada al cliente",  "css_color": "#2563EB",              "prob": 50},
            {"key": "won",       "label": "Ganadas",             "css_color": "var(--color-success)", "prob": 100},
            {"key": "lost",      "label": "Perdidas",            "css_color": "var(--color-danger)",  "prob": 0},
        ]
        all_quotes = list(
            Quote.objects.select_related("lead", "assigned_to").order_by("-created_at")
        )
        for stage in stages:
            qs = [q for q in all_quotes if q.status == stage["key"]]
            stage["quotes"] = qs
            stage["count"]  = len(qs)
            stage["value"]  = sum(q.estimated_total for q in qs if q.estimated_total) or 0
            # Weighted forecast: value × stage probability
            stage["forecast"] = sum(
                float(q.estimated_total or 0) * (q.close_probability or stage["prob"]) / 100
                for q in qs
            )
        ctx["stages"] = stages
        ctx["total"]  = len(all_quotes)
        ctx["total_value"] = sum(
            float(q.estimated_total or 0) for q in all_quotes
            if q.estimated_total and q.status not in ("lost",)
        )
        # Forecast total: sum of all weighted stages (excluding lost/won)
        ctx["total_forecast"] = sum(
            s["forecast"] for s in stages if s["key"] not in ("lost", "won")
        )
        ctx["won_value"] = sum(
            float(q.estimated_total or 0) for q in all_quotes
            if q.estimated_total and q.status == "won"
        )
        return ctx


class QuotePipelineMoveView(View):
    @method_decorator(da_required)
    def post(self, request, pk):
        import json
        from apps.leads.models import Quote
        try:
            data = json.loads(request.body)
            new_status = data.get("status", "")
        except Exception:
            new_status = request.POST.get("status", "")
        if not new_status:
            return JsonResponse({"ok": False, "error": "status requerido"}, status=400)
        quote = get_object_or_404(Quote, pk=pk)
        valid = dict(Quote.Status.choices)
        if new_status not in valid:
            return JsonResponse({"ok": False, "error": "estado inválido"}, status=400)
        STAGE_PROB = {"new": 10, "reviewing": 25, "sent": 50, "won": 100, "lost": 0}
        old_status = quote.status
        quote.status = new_status
        # Update default probability only if still at default or 0
        if quote.close_probability == STAGE_PROB.get(old_status, 0) or quote.close_probability == 0:
            quote.close_probability = STAGE_PROB.get(new_status, 0)
        if new_status in ("won", "lost"):
            quote.closed_at = timezone.now()
        quote.save(update_fields=["status", "close_probability", "closed_at", "updated_at"])
        return JsonResponse({
            "ok": True, "pk": pk,
            "status": new_status,
            "label": valid[new_status],
            "old_status": old_status,
            "probability": quote.close_probability,
        })


# ---------------------------------------------------------------------------
# CONSUMIBLES
# ---------------------------------------------------------------------------
@da_decorator
class ConsumableListView(ListView):
    template_name = "dashboard/consumables/list.html"
    context_object_name = "consumables"
    paginate_by = 30

    def get_queryset(self):
        from apps.catalog.models import Consumable
        qs = Consumable.objects.order_by("-created_at")
        q    = self.request.GET.get("q", "").strip()
        tipo = self.request.GET.get("tipo", "")
        stk  = self.request.GET.get("stock", "")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(part_number__icontains=q))
        if tipo:
            qs = qs.filter(consumable_type=tipo)
        if stk == "1":
            qs = qs.filter(in_stock=True)
        elif stk == "0":
            qs = qs.filter(in_stock=False)
        return qs

    def get_context_data(self, **kwargs):
        from apps.catalog.models import Consumable
        ctx = super().get_context_data(**kwargs)
        ctx["type_choices"] = Consumable.ConsumableType.choices
        ctx["current_q"]    = self.request.GET.get("q", "")
        ctx["current_tipo"] = self.request.GET.get("tipo", "")
        ctx["current_stk"]  = self.request.GET.get("stock", "")
        return ctx


@da_decorator
class ConsumableCreateView(CreateView):
    from apps.catalog.models import Consumable
    template_name = "dashboard/consumables/form.html"

    def get_form_class(self):
        from .forms import ConsumableForm
        return ConsumableForm

    def get_queryset(self):
        from apps.catalog.models import Consumable
        return Consumable.objects.all()

    def form_valid(self, form):
        form.save()
        return redirect("dashboard:consumables")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["action"] = "Nuevo consumible"
        return ctx


@da_decorator
class ConsumableUpdateView(UpdateView):
    template_name = "dashboard/consumables/form.html"

    def get_form_class(self):
        from .forms import ConsumableForm
        return ConsumableForm

    def get_object(self):
        from apps.catalog.models import Consumable
        return get_object_or_404(Consumable, pk=self.kwargs["pk"])

    def form_valid(self, form):
        form.save()
        return redirect("dashboard:consumables")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["action"] = "Editar consumible"
        ctx["object"] = self.get_object()
        return ctx


@da_decorator
class ConsumableDeleteView(View):
    def post(self, request, pk):
        from apps.catalog.models import Consumable
        consumable = get_object_or_404(Consumable, pk=pk)
        consumable.delete()
        return redirect("dashboard:consumables")

    def get(self, request, pk):
        from apps.catalog.models import Consumable
        consumable = get_object_or_404(Consumable, pk=pk)
        return render(request, "dashboard/consumables/confirm_delete.html", {"object": consumable})


# ---------------------------------------------------------------------------
# FOTOCOPIADORAS
# ---------------------------------------------------------------------------
@da_decorator
class CopierListView(ListView):
    template_name = "dashboard/copiers/list.html"
    context_object_name = "copiers"
    paginate_by = 20

    def get_queryset(self):
        from apps.catalog.models import Copier
        qs = Copier.objects.select_related("category").order_by("-created_at")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(model_number__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["current_q"] = self.request.GET.get("q", "")
        return ctx


@da_decorator
class CopierCreateView(CreateView):
    template_name = "dashboard/copiers/form.html"

    def get_form_class(self):
        from .forms import CopierForm
        return CopierForm

    def form_valid(self, form):
        form.save()
        return redirect("dashboard:copiers")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["action"] = "Nueva fotocopiadora"
        return ctx


@da_decorator
class CopierUpdateView(UpdateView):
    template_name = "dashboard/copiers/form.html"

    def get_form_class(self):
        from .forms import CopierForm
        return CopierForm

    def get_object(self):
        from apps.catalog.models import Copier
        return get_object_or_404(Copier, pk=self.kwargs["pk"])

    def form_valid(self, form):
        form.save()
        return redirect("dashboard:copiers")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["action"] = "Editar fotocopiadora"
        ctx["object"] = self.get_object()
        return ctx


@da_decorator
class CopierDeleteView(View):
    def post(self, request, pk):
        from apps.catalog.models import Copier
        get_object_or_404(Copier, pk=pk).delete()
        return redirect("dashboard:copiers")

    def get(self, request, pk):
        from apps.catalog.models import Copier
        obj = get_object_or_404(Copier, pk=pk)
        return render(request, "dashboard/copiers/confirm_delete.html", {"object": obj})


# ---------------------------------------------------------------------------
# BLOG
# ---------------------------------------------------------------------------
@da_decorator
class BlogPostListView(ListView):
    template_name = "dashboard/blog/list.html"
    context_object_name = "posts"
    paginate_by = 20

    def get_queryset(self):
        from apps.blog.models import Post
        qs = Post.objects.select_related("category", "author").order_by("-created_at")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(title__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["current_q"] = self.request.GET.get("q", "")
        return ctx


@da_decorator
class BlogPostEditView(UpdateView):
    template_name = "dashboard/blog/form.html"

    def get_form_class(self):
        from .forms import BlogPostForm
        return BlogPostForm

    def get_object(self):
        from apps.blog.models import Post
        return get_object_or_404(Post, pk=self.kwargs["pk"])

    def form_valid(self, form):
        form.save()
        return redirect("dashboard:blog")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object"] = self.get_object()
        return ctx


# ---------------------------------------------------------------------------
# ENCUESTAS STATS
# ---------------------------------------------------------------------------
@da_decorator
class SurveysStatsView(TemplateView):
    template_name = "dashboard/surveys/stats.html"

    def get_context_data(self, **kwargs):
        from apps.encuestas.models import Encuesta
        from django.db.models import Avg

        ctx = super().get_context_data(**kwargs)
        qs = Encuesta.objects.all()
        ctx["total"] = qs.count()
        ctx["avg_atencion"]  = round(qs.aggregate(a=Avg("calificacion_atencion"))["a"] or 0, 2)
        ctx["avg_servicio"]  = round(qs.aggregate(a=Avg("calificacion_servicio"))["a"] or 0, 2)
        ctx["avg_tiempo"]    = round(qs.aggregate(a=Avg("calificacion_tiempo"))["a"] or 0, 2)
        ctx["avg_precio"]    = round(qs.aggregate(a=Avg("calificacion_precio"))["a"] or 0, 2)
        ctx["recomendaria"]  = qs.filter(recomendaria=True).count()
        ctx["by_service"]    = list(qs.values("tipo_servicio").annotate(n=Count("id")).order_by("-n"))
        ctx["recent"]        = qs.order_by("-fecha")[:15]
        return ctx


# ---------------------------------------------------------------------------
# CONFIGURACIÓN DEL SITIO
# ---------------------------------------------------------------------------
@da_decorator
# ---------------------------------------------------------------------------
# NOTIFICACIONES — estado y prueba de emails automáticos
# ---------------------------------------------------------------------------
@da_decorator
class NotificationsView(View):
    template_name = "dashboard/notifications.html"

    def get(self, request):
        from datetime import timedelta, date
        from django.conf import settings as dj_settings
        from apps.leads.models import Quote, RentalContract

        today = timezone.now()
        cutoff = today - timedelta(days=3)

        pending_quotes = Quote.objects.filter(
            status="new", created_at__lte=cutoff
        ).select_related("lead").order_by("created_at")[:20]

        expiring_contracts = RentalContract.objects.filter(
            status="active",
            end_date__range=(date.today(), date.today() + timedelta(days=30))
        ).select_related("lead").order_by("end_date")[:20]

        return render(request, self.template_name, {
            "pending_quotes": pending_quotes,
            "pending_quotes_count": Quote.objects.filter(status="new", created_at__lte=cutoff).count(),
            "expiring_contracts": expiring_contracts,
            "expiring_count": RentalContract.objects.filter(
                status="active",
                end_date__range=(date.today(), date.today() + timedelta(days=30))
            ).count(),
            "notify_email": getattr(dj_settings, "LEADS_NOTIFICATION_EMAIL", ""),
            "from_email": getattr(dj_settings, "DEFAULT_FROM_EMAIL", ""),
            "email_backend": getattr(dj_settings, "EMAIL_BACKEND", ""),
        })

    def post(self, request):
        action = request.POST.get("action", "")
        msg = ""
        msg_type = "success"

        if action == "test_email":
            try:
                from django.core.mail import send_mail
                from django.conf import settings as dj_settings
                to = getattr(dj_settings, "LEADS_NOTIFICATION_EMAIL", "")
                if to:
                    send_mail(
                        subject="[Solution Copiers CRM] Email de prueba",
                        message="Este es un email de prueba del sistema CRM de Solution Copiers. Si lo recibes, la configuración de email funciona correctamente.",
                        from_email=getattr(dj_settings, "DEFAULT_FROM_EMAIL", None),
                        recipient_list=[to],
                        fail_silently=False,
                    )
                    msg = f"Email de prueba enviado a {to}"
                else:
                    msg = "No hay LEADS_NOTIFICATION_EMAIL configurado en .env"
                    msg_type = "warning"
            except Exception as exc:
                msg = f"Error enviando email: {exc}"
                msg_type = "error"

        elif action == "run_followups":
            from datetime import timedelta
            from apps.leads.models import Quote, RentalContract
            from apps.leads.services import send_followup_email, send_contract_expiry_email
            import datetime

            sent = 0
            cutoff = timezone.now() - timedelta(days=3)
            for quote in Quote.objects.filter(status="new", created_at__lte=cutoff).select_related("lead"):
                days = (timezone.now() - quote.created_at).days
                send_followup_email(quote, days)
                sent += 1

            today = datetime.date.today()
            for threshold in [30, 7]:
                target = today + timedelta(days=threshold)
                for contract in RentalContract.objects.filter(status="active", end_date=target).select_related("lead"):
                    send_contract_expiry_email(contract, threshold)
                    sent += 1

            msg = f"Se enviaron {sent} notificaciones de seguimiento."

        from datetime import timedelta, date
        from django.conf import settings as dj_settings
        from apps.leads.models import Quote, RentalContract

        today_dt = timezone.now()
        cutoff = today_dt - timedelta(days=3)
        today = date.today()

        return render(request, self.template_name, {
            "pending_quotes": Quote.objects.filter(status="new", created_at__lte=cutoff).select_related("lead").order_by("created_at")[:20],
            "pending_quotes_count": Quote.objects.filter(status="new", created_at__lte=cutoff).count(),
            "expiring_contracts": RentalContract.objects.filter(status="active", end_date__range=(today, today + timedelta(days=30))).select_related("lead").order_by("end_date")[:20],
            "expiring_count": RentalContract.objects.filter(status="active", end_date__range=(today, today + timedelta(days=30))).count(),
            "notify_email": getattr(dj_settings, "LEADS_NOTIFICATION_EMAIL", ""),
            "from_email": getattr(dj_settings, "DEFAULT_FROM_EMAIL", ""),
            "email_backend": getattr(dj_settings, "EMAIL_BACKEND", ""),
            "flash_msg": msg,
            "flash_type": msg_type,
        })


class SettingsView(View):
    template_name = "dashboard/settings.html"

    def get(self, request):
        from apps.core.models import SiteSettings
        from apps.seo.models import DesignTokens
        from .forms import SiteSettingsForm
        site = SiteSettings.objects.first()
        tokens = DesignTokens.objects.first()
        form = SiteSettingsForm(instance=site)
        return render(request, self.template_name, {
            "form": form, "site": site, "tokens": tokens,
        })

    def post(self, request):
        from apps.core.models import SiteSettings
        from apps.seo.models import DesignTokens
        from .forms import SiteSettingsForm
        site = SiteSettings.objects.first()
        form = SiteSettingsForm(request.POST, instance=site)
        if form.is_valid():
            form.save()
            return redirect("dashboard:settings")
        tokens = DesignTokens.objects.first()
        return render(request, self.template_name, {
            "form": form, "site": site, "tokens": tokens, "error": True,
        })


# ===========================================================================
# GESTIÓN DE EMPLEADOS — solo accesible desde dashadmin (staff)
# ===========================================================================

def _get_panel_perms():
    """Devuelve permisos del panel indexados por codename."""
    from django.contrib.auth.models import Permission
    from apps.dashboard.models import PANEL_PERM_LABELS, PANEL_PERM_DESCRIPTIONS
    perms = Permission.objects.filter(content_type__app_label="dashboard")
    result = []
    for p in perms:
        if p.codename in PANEL_PERM_LABELS:
            result.append({
                "perm": p,
                "codename": p.codename,
                "label": PANEL_PERM_LABELS[p.codename],
                "description": PANEL_PERM_DESCRIPTIONS.get(p.codename, ""),
            })
    return result


def _get_panel_context():
    """Contexto completo para el formulario de empleado: perms + grupos + roles."""
    from apps.dashboard.models import PANEL_PERM_GROUPS, PANEL_ROLES
    perms_by_code = {p["codename"]: p for p in _get_panel_perms()}
    groups = []
    for g in PANEL_PERM_GROUPS:
        groups.append({
            **g,
            "items": [perms_by_code[c] for c in g["perms"] if c in perms_by_code],
        })
    return {
        "panel_perms":  list(perms_by_code.values()),
        "panel_groups": groups,
        "panel_roles":  PANEL_ROLES,
    }


class EmployeeListView(View):
    template_name = "dashboard/employees/list.html"

    def get(self, request):
        from django.contrib.auth.models import User
        employees = User.objects.filter(is_staff=False).prefetch_related(
            "user_permissions"
        ).order_by("first_name", "username")
        return render(request, self.template_name, {"employees": employees})


@da_decorator
class EmployeeCreateView(View):
    template_name = "dashboard/employees/form.html"

    def get(self, request):
        return render(request, self.template_name, {
            "is_edit": False,
            **_get_panel_context(),
        })

    def post(self, request):
        from django.contrib.auth.models import User
        username   = request.POST.get("username", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name  = request.POST.get("last_name", "").strip()
        email      = request.POST.get("email", "").strip()
        password   = request.POST.get("password", "").strip()
        campo_role = request.POST.get("campo_role", "").strip()

        if not username or not password:
            return render(request, self.template_name, {
                "is_edit": False, "error": "Usuario y contraseña son obligatorios.",
                "data": request.POST,
                "employee_perm_codes": set(request.POST.getlist("panel_perms")),
                **_get_panel_context(),
            })
        if User.objects.filter(username=username).exists():
            return render(request, self.template_name, {
                "is_edit": False, "error": f"El usuario '{username}' ya existe.",
                "data": request.POST,
                "employee_perm_codes": set(request.POST.getlist("panel_perms")),
                **_get_panel_context(),
            })

        user = User.objects.create_user(
            username=username, password=password,
            first_name=first_name, last_name=last_name, email=email,
            is_staff=False, is_active=True,
        )
        if campo_role in ("mensajero", "tecnico"):
            from apps.dashboard.models import FieldUser
            FieldUser.objects.get_or_create(user=user, defaults={"role": campo_role})
        if campo_role != "mensajero":
            # tecnico puede tener panel_perms; usuarios sin rol campo también
            _sync_employee_perms(user, request.POST.getlist("panel_perms"))
        return redirect("dashboard:employees")


@da_decorator
class EmployeeDetailView(View):
    template_name = "dashboard/employees/form.html"

    def get(self, request, pk):
        from django.contrib.auth.models import User
        from apps.dashboard.models import FieldUser
        employee = get_object_or_404(User, pk=pk, is_staff=False)
        employee_perm_codes = set(
            employee.user_permissions.values_list("codename", flat=True)
        )
        try:
            field_user = employee.field_profile
        except FieldUser.DoesNotExist:
            field_user = None
        return render(request, self.template_name, {
            "is_edit": True,
            "employee": employee,
            "employee_perm_codes": employee_perm_codes,
            "field_user": field_user,
            **_get_panel_context(),
        })

    def post(self, request, pk):
        from django.contrib.auth.models import User
        from apps.dashboard.models import FieldUser
        employee = get_object_or_404(User, pk=pk, is_staff=False)

        action = request.POST.get("action", "")
        if action == "toggle_active":
            employee.is_active = not employee.is_active
            employee.save(update_fields=["is_active"])
            return redirect("dashboard:employee_detail", pk=pk)

        employee.first_name = request.POST.get("first_name", employee.first_name).strip()
        employee.last_name  = request.POST.get("last_name",  employee.last_name).strip()
        employee.email      = request.POST.get("email",      employee.email).strip()
        new_password = request.POST.get("password", "").strip()
        if new_password:
            employee.set_password(new_password)
        employee.save()

        campo_role = request.POST.get("campo_role", "").strip()
        if campo_role in ("mensajero", "tecnico"):
            FieldUser.objects.update_or_create(user=employee, defaults={"role": campo_role})
        if campo_role == "mensajero":
            _sync_employee_perms(employee, [])
        elif campo_role == "tecnico":
            # técnico mantiene permisos de panel (panel_tickets, etc.)
            _sync_employee_perms(employee, request.POST.getlist("panel_perms"))
        else:
            _sync_employee_perms(employee, request.POST.getlist("panel_perms"))
            # Si tenía FieldUser y ahora se le asigna rol de panel puro, se elimina
            try:
                employee.field_profile.delete()
            except FieldUser.DoesNotExist:
                pass
        return redirect("dashboard:employees")


def _sync_employee_perms(user, selected_codenames: list):
    """Ajusta user_permissions para que coincidan con selected_codenames."""
    from django.contrib.auth.models import Permission
    panel_perms = Permission.objects.filter(content_type__app_label="dashboard")
    selected = set(selected_codenames)
    for p in panel_perms:
        if p.codename in selected:
            user.user_permissions.add(p)
        else:
            user.user_permissions.remove(p)


# ===========================================================================
# GESTIÓN DE ADMINISTRADORES — solo superusuarios
# ===========================================================================

@su_decorator
class AdminUserListView(View):
    template_name = "dashboard/admins/list.html"

    def get(self, request):
        from django.contrib.auth.models import User
        admins = User.objects.filter(is_staff=True).order_by("-is_superuser", "username")
        return render(request, self.template_name, {"admins": admins})


@su_decorator
class AdminUserCreateView(View):
    template_name = "dashboard/admins/form.html"

    def get(self, request):
        return render(request, self.template_name, {"is_edit": False})

    def post(self, request):
        from django.contrib.auth.models import User
        username    = request.POST.get("username", "").strip()
        first_name  = request.POST.get("first_name", "").strip()
        last_name   = request.POST.get("last_name", "").strip()
        email       = request.POST.get("email", "").strip()
        password    = request.POST.get("password", "").strip()
        is_superuser = request.POST.get("is_superuser") == "1"

        if not username or not password:
            return render(request, self.template_name, {
                "is_edit": False,
                "error": "Usuario y contraseña son obligatorios.",
                "data": request.POST,
            })
        if User.objects.filter(username=username).exists():
            return render(request, self.template_name, {
                "is_edit": False,
                "error": f"El usuario '{username}' ya existe.",
                "data": request.POST,
            })

        User.objects.create_user(
            username=username, password=password,
            first_name=first_name, last_name=last_name, email=email,
            is_staff=True, is_superuser=is_superuser, is_active=True,
        )
        from django.contrib import messages
        messages.success(request, f"Administrador '{username}' creado correctamente.")
        return redirect("dashboard:admins")


@su_decorator
class AdminUserEditView(View):
    template_name = "dashboard/admins/form.html"

    def get(self, request, pk):
        from django.contrib.auth.models import User
        admin = get_object_or_404(User, pk=pk, is_staff=True)
        return render(request, self.template_name, {"is_edit": True, "admin": admin})

    def post(self, request, pk):
        from django.contrib.auth.models import User
        from django.contrib import messages
        admin = get_object_or_404(User, pk=pk, is_staff=True)

        action = request.POST.get("action", "")

        if action == "toggle_active":
            if admin.pk == request.user.pk:
                messages.error(request, "No puedes desactivar tu propia cuenta.")
            else:
                admin.is_active = not admin.is_active
                admin.save(update_fields=["is_active"])
            return redirect("dashboard:admin_detail", pk=pk)

        if action == "toggle_superuser":
            if admin.pk == request.user.pk:
                messages.error(request, "No puedes cambiar tu propio nivel de acceso.")
            else:
                admin.is_superuser = not admin.is_superuser
                admin.save(update_fields=["is_superuser"])
            return redirect("dashboard:admin_detail", pk=pk)

        admin.first_name = request.POST.get("first_name", admin.first_name).strip()
        admin.last_name  = request.POST.get("last_name",  admin.last_name).strip()
        admin.email      = request.POST.get("email",      admin.email).strip()
        new_password = request.POST.get("password", "").strip()
        if new_password:
            admin.set_password(new_password)
        admin.save()
        messages.success(request, "Cambios guardados correctamente.")
        return redirect("dashboard:admins")


# ===========================================================================
# PANEL DE ASESORAS — /panel/
# ===========================================================================

def panel_required(view_func):
    """Permite acceso a usuarios autenticados que NO son staff."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/panel/acceso/?next={request.path}")
        if request.user.is_staff:
            return redirect("/dashadmin/")
        if not request.user.is_active:
            return redirect("/panel/acceso/")
        return view_func(request, *args, **kwargs)
    return wrapper


panel_decorator = method_decorator(panel_required, name="dispatch")


def _panel_base_ctx(request):
    """Contexto mínimo compartido por todas las vistas del panel."""
    from apps.leads.models import Quote, ServiceTicket
    return {
        "my_new_quotes": Quote.objects.filter(
            Q(assigned_to=request.user) | Q(assigned_to__isnull=True),
            status="new"
        ).count(),
        "my_open_tickets": ServiceTicket.objects.filter(
            assigned_to=request.user,
            status__in=("open", "in_progress", "waiting_parts")
        ).count(),
    }


def _log_activity(request, action: str, description: str = "", related_pk=None):
    """Registra una acción del asesora en EmployeeActivity (silencioso ante errores)."""
    try:
        from apps.dashboard.models import EmployeeActivity
        ip = (
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR")
        ) or None
        EmployeeActivity.objects.create(
            user=request.user,
            action=action,
            description=description[:500],
            related_pk=related_pk,
            ip_address=ip,
        )
    except Exception:
        pass


class PanelLoginView(View):
    """Redirige al home si ya está autenticado; si no, muestra formulario de login."""
    template_name = "panel/login.html"

    def get(self, request):
        if request.user.is_authenticated and not request.user.is_staff:
            return redirect("panel:home")
        return render(request, self.template_name)

    def post(self, request):
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        ip       = _client_ip(request)

        if _is_locked_out(ip, username):
            _auth_logger.warning("Panel login bloqueado para %s desde %s", username, ip)
            return render(request, self.template_name, {
                "error": "Acceso bloqueado temporalmente por múltiples intentos fallidos. Intenta en 15 minutos."
            })

        user = authenticate(request, username=username, password=password)
        if user and user.is_active and not user.is_staff:
            _clear_failed_logins(ip, username)
            login(request, user)
            _log_activity(request, "login", f"Inicio de sesión de {user.username}")
            _auth_logger.info("Login panel exitoso: %s desde %s", username, ip)
            return redirect(_safe_next(request, "panel:home"))

        attempts = _record_failed_login(ip, username)
        _auth_logger.warning("Login panel fallido para '%s' desde %s (intento %d)", username, ip, attempts)
        return render(request, self.template_name, {"error": "Credenciales inválidas."})


class PanelLogoutView(View):
    def post(self, request):
        if request.user.is_authenticated:
            _log_activity(request, "logout", f"Cierre de sesión de {request.user.username}")
        logout(request)
        return redirect("panel:login")

    def get(self, request):
        # GET no realiza logout (previene CSRF-via-GET). Solo redirige.
        return redirect("panel:login")


# Reemplazamos el decorator para PanelLoginView — no requiere auth
panel_decorator_login_exempt = method_decorator(
    lambda f: f,  # no-op para login view
    name="dispatch",
)


@panel_decorator
class PanelHomeView(TemplateView):
    template_name = "panel/home.html"

    def get(self, request, *args, **kwargs):
        from apps.dashboard.models import FieldUser
        try:
            fp = request.user.field_profile
            # Técnicos y mensajeros van directo a turno — no al home CRM
            if fp.role in (FieldUser.Role.TECNICO, FieldUser.Role.MENSAJERO):
                return redirect("panel:turno")
        except FieldUser.DoesNotExist:
            pass
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from datetime import timedelta
        from apps.leads.models import Quote, Lead, RentalContract, ServiceTicket, FollowUpTask, LeadActivity
        from apps.dashboard.models import Notification, FieldUser, FieldUserLocation

        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        # Campo: añadir contexto de turno/GPS si tiene field_profile
        try:
            ctx["field_user"] = user.field_profile
            try:
                ctx["field_location"] = user.field_location
            except FieldUserLocation.DoesNotExist:
                ctx["field_location"] = None
        except FieldUser.DoesNotExist:
            ctx["field_user"] = None
            ctx["field_location"] = None
        now  = timezone.now()
        today = now.date()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        ctx.update(_panel_base_ctx(self.request))

        # ── Cotizaciones del asesor o sin asignar ────────────────────────
        my_quotes = Quote.objects.filter(
            Q(assigned_to=user) | Q(assigned_to__isnull=True)
        ).select_related("lead")

        ctx["quotes_new"]       = my_quotes.filter(status="new").count()
        ctx["quotes_reviewing"] = my_quotes.filter(status="reviewing").count()
        ctx["quotes_won"]       = my_quotes.filter(status="won").count()
        ctx["quotes_month"]     = my_quotes.filter(created_at__gte=month_start).count()
        ctx["recent_quotes"]    = my_quotes.order_by("-created_at")[:6]

        # ── Tickets abiertos asignados a la asesora ──────────────────────
        open_tickets = ServiceTicket.objects.filter(
            assigned_to=user,
            status__in=("open", "in_progress", "waiting_parts")
        ).select_related("lead").order_by("priority", "created_at")
        ctx["tickets_open"]     = open_tickets[:5]
        ctx["my_open_tickets"]  = open_tickets.count()

        # ── Contratos por vencer — 3 niveles de urgencia (60 días) ───────
        contracts_base = RentalContract.objects.filter(
            status="active", end_date__isnull=False
        ).select_related("lead").order_by("end_date")

        ctx["contracts_critical"] = contracts_base.filter(
            end_date__range=(today, today + timedelta(days=15))
        )  # 🔴 ≤ 15 días
        ctx["contracts_warning"] = contracts_base.filter(
            end_date__range=(today + timedelta(days=16), today + timedelta(days=30))
        )  # 🟡 16-30 días
        ctx["contracts_upcoming"] = contracts_base.filter(
            end_date__range=(today + timedelta(days=31), today + timedelta(days=60))
        )  # 🔵 31-60 días
        # Compatibilidad con el template anterior
        ctx["contracts_expiring"] = contracts_base.filter(
            end_date__range=(today, today + timedelta(days=30))
        )[:4]

        # ── Mi Día — tareas filtradas por asesora ────────────────────────
        my_tasks = FollowUpTask.objects.filter(
            Q(assigned_to=user) | Q(assigned_to__isnull=True)
        ).select_related("lead")

        ctx["tasks_today"]    = my_tasks.filter(due_date=today,     is_done=False).order_by("pk")[:15]
        ctx["tasks_overdue"]  = my_tasks.filter(due_date__lt=today,  is_done=False).order_by("due_date")[:10]
        ctx["tasks_tomorrow"] = my_tasks.filter(due_date=today + timedelta(days=1), is_done=False).order_by("pk")[:5]
        ctx["quotes_pending"] = my_quotes.filter(status="new").select_related("lead").order_by("created_at")[:8]
        ctx["today"]          = today

        # ── Leads fríos — cotizaciones abiertas sin actividad en +3 días ─
        cold_threshold = now - timedelta(days=3)
        # IDs de leads con cotizaciones abiertas asignadas a esta asesora
        hot_lead_ids = set(
            LeadActivity.objects.filter(
                created_at__gte=cold_threshold
            ).values_list("lead_id", flat=True)
        )
        cold_leads_qs = Lead.objects.filter(
            quotes__assigned_to=user,
            quotes__status__in=("new", "reviewing", "sent"),
        ).exclude(pk__in=hot_lead_ids).distinct().order_by("updated_at")
        ctx["leads_cold"]       = cold_leads_qs[:8]
        ctx["leads_cold_count"] = cold_leads_qs.count()

        # ── Notificaciones sin leer ──────────────────────────────────────
        ctx["unread_notifications"] = Notification.objects.filter(
            user=user, is_read=False
        ).count()

        return ctx


def _panel_no_perm(request, perm_label: str):
    """Renderiza aviso de acceso denegado en el panel."""
    ctx = _panel_base_ctx(request)
    ctx["perm_label"] = perm_label
    return render(request, "panel/no_permission.html", ctx, status=403)


@panel_decorator
class PanelQuoteListView(TemplateView):
    template_name = "panel/quotes.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm("dashboard.panel_cotizaciones"):
            return _panel_no_perm(request, "Cotizaciones")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from apps.leads.models import Quote
        ctx = super().get_context_data(**kwargs)
        ctx.update(_panel_base_ctx(self.request))
        user = self.request.user

        qs = Quote.objects.select_related("lead", "assigned_to").order_by("-created_at")

        # Filtros
        status = self.request.GET.get("status", "")
        mine   = self.request.GET.get("mine", "")
        search = self.request.GET.get("q", "").strip()

        if status:
            qs = qs.filter(status=status)
        if mine == "1":
            qs = qs.filter(assigned_to=user)
        elif mine == "0":
            qs = qs.filter(assigned_to__isnull=True)
        if search:
            qs = qs.filter(
                Q(lead__full_name__icontains=search) |
                Q(lead__company_name__icontains=search) |
                Q(lead__phone__icontains=search)
            )

        ctx["quotes"]   = qs[:60]
        ctx["total"]    = qs.count()
        ctx["status"]   = status
        ctx["mine"]     = mine
        ctx["q"]        = search
        ctx["status_choices"] = Quote.Status.choices
        return ctx


@panel_decorator
class PanelQuoteDetailView(View):
    template_name = "panel/quote_detail.html"

    def get(self, request, pk):
        if not request.user.has_perm("dashboard.panel_cotizaciones"):
            return _panel_no_perm(request, "Cotizaciones")
        from apps.leads.models import Quote, ServiceTicket
        quote = get_object_or_404(Quote, pk=pk)
        _log_activity(request, "view_quote", f"Ver cotización #{quote.pk} — {quote.lead.full_name}", related_pk=pk)
        ctx = {
            "quote": quote,
            "tickets": quote.lead.tickets.order_by("-created_at")[:5],
            "status_choices": Quote.Status.choices,
        }
        ctx.update(_panel_base_ctx(request))
        return render(request, self.template_name, ctx)

    def post(self, request, pk):
        if not request.user.has_perm("dashboard.panel_cotizaciones"):
            return _panel_no_perm(request, "Cotizaciones")
        from apps.leads.models import Quote
        quote = get_object_or_404(Quote, pk=pk)
        action = request.POST.get("action", "")

        if action == "change_status":
            new_status = request.POST.get("status", "")
            if new_status in dict(Quote.Status.choices):
                quote.status = new_status
                quote.save(update_fields=["status"])
                _log_activity(request, "update_quote", f"Cambió estado de cotización #{pk} a {new_status}", related_pk=pk)

        elif action == "assign_me":
            quote.assigned_to = request.user
            quote.save(update_fields=["assigned_to"])
            _log_activity(request, "assign_quote", f"Se asignó cotización #{pk} — {quote.lead.full_name}", related_pk=pk)

        elif action == "add_note":
            note = request.POST.get("note", "").strip()
            if note:
                from django.utils import timezone as tz
                ts = tz.now().strftime("%d/%m/%Y %H:%i")
                quote.lead.notes_internal = (
                    f"[{ts} — {request.user.get_full_name() or request.user.username}] {note}\n\n"
                    + (quote.lead.notes_internal or "")
                )
                quote.lead.save(update_fields=["notes_internal"])
                _log_activity(request, "update_quote", f"Añadió nota en cotización #{pk}", related_pk=pk)

        return redirect("panel:quote_detail", pk=pk)


@panel_decorator
class PanelClientListView(TemplateView):
    template_name = "panel/clients.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm("dashboard.panel_clientes"):
            return _panel_no_perm(request, "Clientes")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from apps.leads.models import Lead
        ctx = super().get_context_data(**kwargs)
        ctx.update(_panel_base_ctx(self.request))

        qs = Lead.objects.annotate(
            quote_count=Count("quotes"),
            ticket_count=Count("tickets"),
        ).order_by("-created_at")

        search = self.request.GET.get("q", "").strip()
        if search:
            qs = qs.filter(
                Q(full_name__icontains=search) |
                Q(company_name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search)
            )

        ctx["clients"] = qs[:80]
        ctx["total"]   = qs.count()
        ctx["q"]       = search
        return ctx


@panel_decorator
class PanelClientDetailView(View):
    template_name = "panel/client_detail.html"

    def get(self, request, pk):
        if not request.user.has_perm("dashboard.panel_clientes"):
            return _panel_no_perm(request, "Clientes")
        from apps.leads.models import Lead, Quote, ServiceTicket, RentalContract, LeadActivity, FollowUpTask, EmailLog
        lead = get_object_or_404(Lead, pk=pk)
        _log_activity(request, "view_client", f"Ver cliente #{pk} — {lead.full_name}", related_pk=pk)
        ctx = {
            "lead":       lead,
            "quotes":     lead.quotes.order_by("-created_at"),
            "tickets":    lead.tickets.select_related("assigned_to").order_by("-created_at"),
            "contracts":  lead.contracts.order_by("-created_at"),
            "activities": LeadActivity.objects.filter(lead=lead).select_related("created_by").order_by("-created_at")[:30],
            "tasks":      FollowUpTask.objects.filter(lead=lead).order_by("is_done", "due_date"),
            "email_logs": EmailLog.objects.filter(lead=lead).order_by("-created_at")[:15],
            "status_choices":    Quote.Status.choices,
            "activity_types":    LeadActivity.ActivityType.choices,
        }
        ctx.update(_panel_base_ctx(request))
        return render(request, self.template_name, ctx)

    def post(self, request, pk):
        """Actualizar datos básicos del lead desde el panel de asesoras."""
        if not request.user.has_perm("dashboard.panel_clientes"):
            return _panel_no_perm(request, "Clientes")
        from apps.leads.models import Lead
        from django.contrib import messages as dj_messages
        lead = get_object_or_404(Lead, pk=pk)
        lead.notes_internal = request.POST.get("notes_internal", "")
        lead.full_name    = request.POST.get("full_name", lead.full_name)
        lead.phone        = request.POST.get("phone", lead.phone)
        lead.company_name = request.POST.get("company_name", lead.company_name)
        lead.job_title    = request.POST.get("job_title", lead.job_title)
        lead.city         = request.POST.get("city", lead.city)
        lead.save(update_fields=["notes_internal", "full_name", "phone", "company_name", "job_title", "city"])
        dj_messages.success(request, "Cliente actualizado.")
        return redirect("panel:client_detail", pk=pk)


@panel_decorator
class PanelActivityCreateView(View):
    def post(self, request, pk):
        if not request.user.has_perm("dashboard.panel_clientes"):
            return _panel_no_perm(request, "Clientes")
        from apps.leads.models import Lead, LeadActivity
        from django.contrib import messages as dj_messages
        lead  = get_object_or_404(Lead, pk=pk)
        notes = request.POST.get("notes", "").strip()
        if notes:
            LeadActivity.objects.create(
                lead=lead,
                activity_type=request.POST.get("activity_type", "note"),
                notes=notes,
                outcome=request.POST.get("outcome", ""),
                created_by=request.user,
            )
            dj_messages.success(request, "Actividad registrada.")
        return redirect("panel:client_detail", pk=pk)


@panel_decorator
class PanelTaskCreateView(View):
    def post(self, request, pk):
        if not request.user.has_perm("dashboard.panel_clientes"):
            return _panel_no_perm(request, "Clientes")
        from apps.leads.models import Lead, FollowUpTask
        from django.contrib import messages as dj_messages
        lead        = get_object_or_404(Lead, pk=pk)
        description = request.POST.get("description", "").strip()
        due_date    = request.POST.get("due_date", "")
        if description and due_date:
            FollowUpTask.objects.create(
                lead=lead,
                description=description,
                due_date=due_date,
                assigned_to=request.user,
            )
            dj_messages.success(request, "Tarea creada.")
        return redirect("panel:client_detail", pk=pk)


@panel_decorator
class PanelTaskToggleView(View):
    def post(self, request, pk):
        from apps.leads.models import FollowUpTask
        task = get_object_or_404(FollowUpTask, pk=pk)
        task.is_done = not task.is_done
        task.done_at = timezone.now() if task.is_done else None
        task.save(update_fields=["is_done", "done_at"])
        return redirect("panel:client_detail", pk=task.lead_id)


@panel_decorator
class PanelTicketListView(TemplateView):
    template_name = "panel/tickets.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm("dashboard.panel_tickets"):
            return _panel_no_perm(request, "Tickets de servicio")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from apps.leads.models import ServiceTicket
        ctx = super().get_context_data(**kwargs)
        ctx.update(_panel_base_ctx(self.request))
        user = self.request.user

        qs = ServiceTicket.objects.select_related("lead", "assigned_to", "contract").order_by(
            "-priority", "-created_at"
        )

        from apps.dashboard.models import FieldUser
        is_tecnico = False
        try:
            is_tecnico = user.field_profile.role == FieldUser.Role.TECNICO
        except FieldUser.DoesNotExist:
            pass

        status = self.request.GET.get("status", "")
        # Técnicos solo ven sus tickets — no se puede quitar el filtro
        mine = "1" if is_tecnico else self.request.GET.get("mine", "1")
        search = self.request.GET.get("q", "").strip()

        if mine == "1":
            qs = qs.filter(assigned_to=user)
        if status:
            qs = qs.filter(status=status)
        if search:
            qs = qs.filter(
                Q(lead__full_name__icontains=search) |
                Q(ticket_number__icontains=search) |
                Q(description__icontains=search)
            )

        ctx["tickets"]          = qs[:60]
        ctx["total"]            = qs.count()
        ctx["status"]           = status
        ctx["mine"]             = mine
        ctx["q"]                = search
        ctx["status_choices"]   = ServiceTicket.Status.choices
        ctx["priority_choices"] = ServiceTicket.Priority.choices
        ctx["is_tecnico"]       = is_tecnico
        return ctx


@panel_decorator
class PanelTicketDetailView(View):
    template_name = "panel/ticket_detail.html"

    def _can_assign(self, request):
        """Solo asesoras (sin field_profile) y superusuarios pueden asignar."""
        from apps.dashboard.models import FieldUser
        if request.user.is_superuser:
            return True
        try:
            request.user.field_profile
            return False  # técnicos y mensajeros no pueden asignar
        except FieldUser.DoesNotExist:
            return True  # asesoras/supervisores sí pueden

    def get(self, request, pk):
        if not request.user.has_perm("dashboard.panel_tickets"):
            return _panel_no_perm(request, "Tickets de servicio")
        from apps.leads.models import ServiceTicket, RentalContract
        from django.contrib.auth.models import User
        ticket = get_object_or_404(ServiceTicket, pk=pk)
        _log_activity(request, "view_ticket", f"Ver ticket #{ticket.ticket_number} — {ticket.lead.full_name}", related_pk=pk)
        ctx = {
            "ticket":           ticket,
            "status_choices":   ServiceTicket.Status.choices,
            "priority_choices": ServiceTicket.Priority.choices,
            "technicians":      User.objects.filter(field_profile__role="tecnico"),
            "contracts":        RentalContract.objects.filter(lead=ticket.lead, status="active"),
            "can_assign":       self._can_assign(request),
        }
        ctx.update(_panel_base_ctx(request))
        return render(request, self.template_name, ctx)

    def post(self, request, pk):
        if not request.user.has_perm("dashboard.panel_tickets"):
            return _panel_no_perm(request, "Tickets de servicio")
        from apps.leads.models import ServiceTicket
        from django.contrib.auth.models import User
        ticket = get_object_or_404(ServiceTicket, pk=pk)

        # Todos con panel_tickets pueden cambiar estado y notas
        ticket.status           = request.POST.get("status", ticket.status)
        ticket.resolution_notes = request.POST.get("resolution_notes", ticket.resolution_notes)

        if ticket.status in ("resolved", "closed") and not ticket.resolved_at:
            ticket.resolved_at = timezone.now()

        # Solo asesoras y superusuarios pueden asignar, cambiar prioridad y agendar
        if self._can_assign(request):
            ticket.priority = request.POST.get("priority", ticket.priority)
            scheduled_str = request.POST.get("scheduled_for", "")
            if scheduled_str:
                from django.utils.dateparse import parse_datetime
                ticket.scheduled_for = parse_datetime(scheduled_str)
            assigned_id = request.POST.get("assigned_to", "")
            if assigned_id:
                try:
                    ticket.assigned_to = User.objects.get(pk=int(assigned_id))
                except (User.DoesNotExist, ValueError):
                    pass
            elif "assigned_to" in request.POST and not assigned_id:
                ticket.assigned_to = None

        ticket.save()
        _log_activity(request, "update_ticket", f"Actualizo ticket #{ticket.ticket_number} estado: {ticket.status}", related_pk=pk)
        return redirect("panel:ticket_detail", pk=pk)


@panel_decorator
class PanelTicketCreateView(View):
    template_name = "panel/ticket_create.html"

    def _can_create(self, request):
        from apps.dashboard.models import FieldUser
        if request.user.is_superuser:
            return True
        try:
            request.user.field_profile
            return False  # técnicos y mensajeros no crean tickets
        except FieldUser.DoesNotExist:
            return True

    def get(self, request):
        if not request.user.has_perm("dashboard.panel_tickets"):
            return _panel_no_perm(request, "Tickets de servicio")
        if not self._can_create(request):
            return _panel_no_perm(request, "Crear tickets (solo asesoras y superadmins)")
        from apps.leads.models import Lead, ServiceTicket, RentalContract
        from django.contrib.auth.models import User
        ctx = {
            "lead_list":        Lead.objects.order_by("full_name"),
            "contract_list":    RentalContract.objects.filter(status="active").select_related("lead"),
            "issue_choices":    ServiceTicket.IssueType.choices,
            "priority_choices": ServiceTicket.Priority.choices,
            "next_number":      _next_ticket_number(),
            "technician_list":  User.objects.filter(field_profile__role="tecnico"),
        }
        ctx.update(_panel_base_ctx(request))
        return render(request, self.template_name, ctx)

    def post(self, request):
        if not request.user.has_perm("dashboard.panel_tickets"):
            return _panel_no_perm(request, "Tickets de servicio")
        if not self._can_create(request):
            return _panel_no_perm(request, "Crear tickets (solo asesoras y superadmins)")
        from apps.leads.models import Lead, ServiceTicket, RentalContract
        from django.utils.dateparse import parse_datetime
        from django.contrib.auth.models import User
        try:
            lead = Lead.objects.get(pk=int(request.POST.get("lead", 0)))
        except (Lead.DoesNotExist, ValueError, TypeError):
            return redirect("panel:tickets")

        contract = None
        if request.POST.get("contract"):
            try:
                contract = RentalContract.objects.get(pk=int(request.POST["contract"]))
            except Exception:
                pass

        assigned_to = None
        if request.POST.get("assigned_to"):
            try:
                assigned_to = User.objects.get(
                    pk=int(request.POST["assigned_to"]),
                    field_profile__role="tecnico",
                )
            except (User.DoesNotExist, ValueError):
                pass

        scheduled_for = None
        if request.POST.get("scheduled_for"):
            scheduled_for = parse_datetime(request.POST["scheduled_for"])

        ticket = ServiceTicket.objects.create(
            ticket_number=request.POST.get("ticket_number") or _next_ticket_number(),
            lead=lead,
            contract=contract,
            equipment_description=request.POST.get("equipment_description", ""),
            issue_type=request.POST.get("issue_type", "repair"),
            priority=request.POST.get("priority", "medium"),
            status="open",
            description=request.POST.get("description", ""),
            assigned_to=assigned_to,
            scheduled_for=scheduled_for,
        )
        _create_delivery_task_for_ticket(ticket, request.user)
        _log_activity(request, "create_ticket", f"Creo ticket #{ticket.ticket_number} para {lead.full_name}", related_pk=ticket.pk)
        return redirect("panel:ticket_detail", pk=ticket.pk)


@panel_decorator
class PanelContractListView(TemplateView):
    template_name = "panel/contracts.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm("dashboard.panel_contratos"):
            return _panel_no_perm(request, "Contratos de alquiler")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from apps.leads.models import RentalContract
        ctx = super().get_context_data(**kwargs)
        ctx.update(_panel_base_ctx(self.request))

        qs = RentalContract.objects.select_related("lead").order_by("-created_at")
        status = self.request.GET.get("status", "active")
        search = self.request.GET.get("q", "").strip()

        if status:
            qs = qs.filter(status=status)
        if search:
            qs = qs.filter(
                Q(lead__full_name__icontains=search) |
                Q(contract_number__icontains=search) |
                Q(lead__company_name__icontains=search)
            )

        ctx["contracts"]       = qs[:60]
        ctx["total"]           = qs.count()
        ctx["status"]          = status
        ctx["q"]               = search
        ctx["status_choices"]  = RentalContract.Status.choices
        _log_activity(self.request, "view_contract", "Consultó lista de contratos")
        return ctx


@panel_decorator
class PanelConsumableListView(TemplateView):
    template_name = "panel/consumables.html"

    # Orden y etiquetas canónicas de tipos
    TYPE_ORDER = [
        ("toner_bn",   "Tóner B/N"),
        ("toner_color","Tóner Color"),
        ("toner",      "Tóner"),
        ("ink",        "Tinta / Botella"),
        ("drum",       "Tambor / Cilindro"),
        ("fuser",      "Banda fusora / Fusor"),
        ("developer",  "Revelador"),
        ("roller",     "Rodillo"),
        ("blade",      "Cuchilla"),
        ("chip",       "Chip"),
        ("kit",        "Kit de mantenimiento"),
        ("other",      "Otro repuesto"),
    ]

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm("dashboard.panel_insumos"):
            return _panel_no_perm(request, "Insumos y consumibles")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from apps.catalog.models import Consumable
        ctx = super().get_context_data(**kwargs)
        ctx.update(_panel_base_ctx(self.request))

        search     = self.request.GET.get("q", "").strip()
        cat_filter = self.request.GET.get("cat", "").strip()

        base_qs = Consumable.objects.prefetch_related("compatible_models").order_by("name")

        if search:
            # Búsqueda: resultados planos con highlight
            qs = base_qs.filter(
                Q(name__icontains=search) |
                Q(brand__icontains=search) |
                Q(part_number__icontains=search) |
                Q(compatible_models__name__icontains=search) |
                Q(compatible_models__model_number__icontains=search)
            ).distinct()
            _log_activity(request, "search_consumables", f"Búsqueda de insumos: \"{search}\"")
            ctx["consumables"]  = qs[:80]
            ctx["total"]        = qs.count()
            ctx["in_stock"]     = qs.filter(in_stock=True).count()
            ctx["search_mode"]  = True
        else:
            # Vista por categorías
            type_labels = dict(self.TYPE_ORDER)
            categories = []
            for code, label in self.TYPE_ORDER:
                qs = base_qs.filter(consumable_type=code)
                count = qs.count()
                if count == 0:
                    continue
                # Si hay filtro de categoría activo, cargamos items; si no, solo conteo
                items = list(qs) if cat_filter == code else []
                categories.append({
                    "code":     code,
                    "label":    label,
                    "count":    count,
                    "in_stock": qs.filter(in_stock=True).count(),
                    "items":    items,
                    "open":     cat_filter == code,
                })
            ctx["categories"]  = categories
            ctx["search_mode"] = False
            ctx["cat_filter"]  = cat_filter
            ctx["total"]       = base_qs.count()
            ctx["in_stock"]    = base_qs.filter(in_stock=True).count()

        ctx["q"] = search
        return ctx


@panel_decorator
class PanelConsumableAutocompleteView(View):
    """Endpoint JSON para autocomplete del buscador de insumos."""

    def get(self, request):
        if not request.user.has_perm("dashboard.panel_insumos"):
            return JsonResponse([], safe=False)

        from apps.catalog.models import Consumable
        q = request.GET.get("q", "").strip()
        if len(q) < 2:
            return JsonResponse([], safe=False)

        qs = Consumable.objects.filter(
            Q(name__icontains=q) |
            Q(brand__icontains=q) |
            Q(part_number__icontains=q)
        ).values("id", "name", "brand", "part_number", "price", "consumable_type", "in_stock", "stock_quantity")[:12]

        results = [
            {
                "id":             r["id"],
                "name":           r["name"],
                "brand":          r["brand"],
                "part_number":    r["part_number"] or "",
                "price":          str(r["price"]) if r["price"] else "0",
                "type":           r["consumable_type"],
                "in_stock":       r["in_stock"],
                "stock_quantity": r["stock_quantity"],
            }
            for r in qs
        ]
        return JsonResponse(results, safe=False)


# ===========================================================================
# PANEL ASESORAS — Facturación
# ===========================================================================

@panel_decorator
class PanelInvoiceListView(TemplateView):
    template_name = "panel/invoices.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm("dashboard.panel_facturacion"):
            return _panel_no_perm(request, "Facturación")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from apps.payments.models import Invoice
        ctx = super().get_context_data(**kwargs)
        ctx.update(_panel_base_ctx(self.request))

        qs = Invoice.objects.filter(
            created_by=self.request.user
        ).select_related("lead").order_by("-created_at")

        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(client_name__icontains=q) |
                Q(client_nit__icontains=q) |
                Q(invoice_number__icontains=q)
            )

        status_filter = self.request.GET.get("estado", "")
        if status_filter:
            qs = qs.filter(status=status_filter)

        ctx["invoices"]        = qs[:50]
        ctx["total"]           = qs.count()
        ctx["status_choices"]  = Invoice.Status.choices
        ctx["estado_actual"]   = status_filter
        ctx["q"]               = q
        return ctx


@panel_decorator
class PanelInvoiceCreateView(View):
    template_name = "panel/invoice_form.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm("dashboard.panel_facturacion"):
            return _panel_no_perm(request, "Facturación")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        from apps.payments.models import Invoice
        from apps.leads.models import Lead
        ctx = _panel_base_ctx(request)
        ctx["payment_methods"] = Invoice.PaymentMethod.choices
        ctx["leads"] = Lead.objects.order_by("full_name").values("pk", "full_name", "company_name", "nit", "email")[:200]
        ctx["action"] = "Crear"
        return render(request, self.template_name, ctx)

    def post(self, request):
        from apps.payments.views import InvoiceCreateView
        from django.contrib import messages as dj_messages
        try:
            invoice = InvoiceCreateView._create_from_post(request)
            dj_messages.success(request, f"Factura {invoice.invoice_number} creada exitosamente.")
            return redirect("panel:invoice_detail", pk=invoice.pk)
        except Exception as exc:
            from django.contrib import messages as dj_messages
            dj_messages.error(request, f"Error al crear la factura: {exc}")
            return redirect("panel:invoice_create")


@panel_decorator
class PanelInvoiceDetailView(View):
    template_name = "panel/invoice_detail.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm("dashboard.panel_facturacion"):
            return _panel_no_perm(request, "Facturación")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk: int):
        from apps.payments.models import Invoice
        invoice = get_object_or_404(
            Invoice.objects.prefetch_related("items").select_related("lead", "order"),
            pk=pk, created_by=request.user
        )
        ctx = _panel_base_ctx(request)
        ctx["invoice"]  = invoice
        ctx["payments"] = invoice.payments.all()
        ctx["status_choices"] = Invoice.Status.choices
        return render(request, self.template_name, ctx)


@panel_decorator
class PanelInvoiceStatusUpdateView(View):
    """POST /panel/facturas/<pk>/estado/ — cambia estado de una factura propia."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm("dashboard.panel_facturacion"):
            return _panel_no_perm(request, "Facturación")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk: int):
        from apps.payments.models import Invoice
        from apps.payments.views import _reduce_stock_for_invoice
        from django.contrib import messages as dj_messages
        invoice = get_object_or_404(Invoice, pk=pk, created_by=request.user)
        new_status = request.POST.get("status")
        if new_status in dict(Invoice.Status.choices):
            invoice.status = new_status
            if new_status == Invoice.Status.PAID and not invoice.paid_date:
                invoice.paid_date = timezone.localdate()
            invoice.save(update_fields=["status", "paid_date"])
            if new_status in (Invoice.Status.ISSUED, Invoice.Status.PAID):
                _reduce_stock_for_invoice(invoice, user=request.user)
            dj_messages.success(request, "Estado de factura actualizado.")
        return redirect("panel:invoice_detail", pk=pk)


# ===========================================================================
# GESTIÓN DE STOCK — /dashadmin/consumibles/stock/
# ===========================================================================

TYPE_ORDER_STOCK = [
    ("toner_bn",    "Tóner B/N"),
    ("toner_color", "Tóner Color"),
    ("ink",         "Tinta / Botella"),
    ("drum",        "Tambor / Cilindro"),
    ("fuser",       "Banda fusora / Fusor"),
    ("developer",   "Revelador"),
    ("roller",      "Rodillo"),
    ("blade",       "Cuchilla"),
    ("chip",        "Chip"),
    ("kit",         "Kit de mantenimiento"),
    ("other",       "Otro repuesto"),
]


@da_decorator
class StockManageView(View):
    """Lista de consumibles agrupada por categoría con ajuste de stock."""
    template_name = "dashboard/stock/list.html"

    def get(self, request):
        from apps.catalog.models import Consumable
        search     = request.GET.get("q", "").strip()
        cat_filter = request.GET.get("cat", "").strip()
        low_only   = request.GET.get("low", "")

        base_qs = Consumable.objects.order_by("name")

        if low_only == "1":
            base_qs = base_qs.filter(stock_quantity__lte=5)

        if search:
            qs = base_qs.filter(
                Q(name__icontains=search) |
                Q(brand__icontains=search) |
                Q(part_number__icontains=search) |
                Q(compatible_models__name__icontains=search)
            ).prefetch_related("compatible_models").distinct()
            return render(request, self.template_name, {
                "consumables": qs[:100],
                "total":       qs.count(),
                "search_mode": True,
                "q":           search,
                "low_only":    low_only,
                "type_choices": TYPE_ORDER_STOCK,
            })

        # Vista por categorías
        categories = []
        total_all  = 0
        for code, label in TYPE_ORDER_STOCK:
            qs = base_qs.filter(consumable_type=code)
            count = qs.count()
            if count == 0:
                continue
            total_all += count
            low_count  = qs.filter(stock_quantity__lte=5).count()
            zero_count = qs.filter(stock_quantity=0).count()
            items = list(qs.prefetch_related("compatible_models")) if cat_filter == code else []
            categories.append({
                "code":       code,
                "label":      label,
                "count":      count,
                "low_count":  low_count,
                "zero_count": zero_count,
                "items":      items,
                "open":       cat_filter == code,
            })

        return render(request, self.template_name, {
            "categories":   categories,
            "total":        total_all,
            "search_mode":  False,
            "q":            search,
            "cat_filter":   cat_filter,
            "low_only":     low_only,
            "type_choices": TYPE_ORDER_STOCK,
        })


@da_decorator
class StockAutocompleteView(View):
    """JSON autocomplete para el buscador de stock (admin)."""

    def get(self, request):
        from apps.catalog.models import Consumable
        q = request.GET.get("q", "").strip()
        if len(q) < 2:
            return JsonResponse([], safe=False)

        qs = Consumable.objects.filter(
            Q(name__icontains=q) |
            Q(brand__icontains=q) |
            Q(part_number__icontains=q)
        ).values("pk", "name", "brand", "consumable_type", "in_stock", "stock_quantity", "part_number")[:14]

        type_labels = dict(TYPE_ORDER_STOCK)
        results = [
            {
                "pk":             r["pk"],
                "name":           r["name"],
                "brand":          r["brand"] or "",
                "part_number":    r["part_number"] or "",
                "type_label":     type_labels.get(r["consumable_type"], r["consumable_type"]),
                "in_stock":       r["in_stock"],
                "stock_quantity": r["stock_quantity"],
            }
            for r in qs
        ]
        return JsonResponse(results, safe=False)


@da_decorator
class StockAdjustView(View):
    """POST: registra movimiento de stock y actualiza Consumable.stock_quantity."""

    def post(self, request, pk):
        from apps.catalog.models import Consumable, StockMovement
        consumable    = get_object_or_404(Consumable, pk=pk)
        mov_type      = request.POST.get("movement_type", "in")
        try:
            qty = int(request.POST.get("quantity", 0))
        except (ValueError, TypeError):
            qty = 0
        notes = request.POST.get("notes", "").strip()

        if qty == 0:
            return redirect(request.META.get("HTTP_REFERER", "dashboard:stock"))

        # Ajusta la cantidad según tipo
        if mov_type == "out":
            delta = -abs(qty)
        elif mov_type == "adjustment":
            delta = qty  # puede ser positivo o negativo
        else:  # in
            delta = abs(qty)

        consumable.stock_quantity = max(0, consumable.stock_quantity + delta)
        consumable.in_stock       = consumable.stock_quantity > 0
        consumable.save(update_fields=["stock_quantity", "in_stock"])

        StockMovement.objects.create(
            consumable=consumable,
            movement_type=mov_type,
            quantity=delta,
            notes=notes,
            created_by=request.user,
        )

        next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "dashboard:stock"
        return redirect(next_url)


@da_decorator
class StockHistoryView(View):
    """Historial de movimientos de un consumible."""
    template_name = "dashboard/stock/history.html"

    def get(self, request, pk):
        from apps.catalog.models import Consumable, StockMovement
        consumable = get_object_or_404(Consumable, pk=pk)
        movements  = StockMovement.objects.filter(consumable=consumable).select_related("created_by")
        return render(request, self.template_name, {
            "consumable": consumable,
            "movements":  movements[:100],
        })


# ===========================================================================
# HISTORIAL DE ACTIVIDAD — /dashadmin/actividad/
# ===========================================================================

@da_decorator
class EmployeeActivityView(View):
    """Historial de acciones de los asesores en el panel."""
    template_name = "dashboard/activity.html"

    def get(self, request):
        from apps.dashboard.models import EmployeeActivity
        from django.contrib.auth.models import User

        qs = EmployeeActivity.objects.select_related("user").order_by("-created_at")

        # Filtros
        user_id = request.GET.get("user", "").strip()
        action  = request.GET.get("action", "").strip()
        search  = request.GET.get("q", "").strip()

        if user_id:
            qs = qs.filter(user_id=user_id)
        if action:
            qs = qs.filter(action=action)
        if search:
            qs = qs.filter(
                Q(description__icontains=search) | Q(user__username__icontains=search)
            )

        employees = User.objects.filter(is_staff=False, is_active=True).order_by("first_name")

        return render(request, self.template_name, {
            "activities":      qs[:200],
            "total":           qs.count(),
            "employees":       employees,
            "action_choices":  EmployeeActivity.Action.choices,
            "filter_user":     user_id,
            "filter_action":   action,
            "q":               search,
        })


# ===========================================================================
# ASISTENTE VIRTUAL — powered by Groq (gratis) / Anthropic (fallback)
# ===========================================================================

_SYSTEM_ADMIN = """Eres Nexa, la asistente virtual inteligente de Solution Copiers, \
una empresa colombiana líder en alquiler y venta de fotocopiadoras e insumos. \
Respondes ÚNICAMENTE en español. Tienes una personalidad cálida, profesional y proactiva.

Tu misión es guiar al administrador paso a paso para sacar el máximo provecho del sistema. \
No te limitas a responder preguntas: anticipas necesidades, sugieres siguientes pasos \
y explicas el "por qué" detrás de cada acción. Cuando alguien termina una tarea, \
sugiere qué hacer después. Usa ejemplos concretos del negocio cuando sea útil. \
Sé concisa pero completa — nunca dejes al usuario sin un paso claro a seguir.

Estás integrada en el panel de administración (/dashadmin/) y dominas todas las secciones del sistema.

=== SECCIONES DEL PANEL ADMIN (/dashadmin/) ===

1. HOME — Dashboard con KPIs: leads del mes, cotizaciones activas, contratos, \
tickets abiertos, tendencias de ventas.

2. PIPELINE — Vista Kanban de cotizaciones. Las columnas son los estados: \
Nuevo → En revisión → Cotizado → Negociación → Ganado / Perdido / Descartado. \
Se arrastran tarjetas entre columnas. Cada tarjeta muestra el nombre del cliente, \
empresa y valor estimado.

3. COTIZACIONES (/dashadmin/cotizaciones/) — Lista completa de todas las solicitudes \
de cotización recibidas desde el formulario del sitio web. Se pueden filtrar por estado, \
asignar a un asesor, cambiar estado y agregar notas internas. Detalle incluye datos \
completos del cliente, historial de notas y tickets relacionados.

4. CLIENTES (/dashadmin/clientes/) — Perfiles de todos los leads/clientes. \
Cada perfil muestra sus cotizaciones, tickets y contratos asociados.

5. CONTRATOS (/dashadmin/contratos/) — Contratos de alquiler de equipos. \
Estados: Borrador, Activo, Vencido, Cancelado. Incluye fecha de inicio/fin, \
valor mensual, equipo alquilado y cliente.

6. TICKETS (/dashadmin/tickets/) — Tickets de servicio técnico. \
Tipos de problema: Reparación, Mantenimiento preventivo, Instalación, Suministros, Otro. \
Prioridades: Baja, Media, Alta, Urgente. Estados: Abierto → En progreso → \
Esperando repuestos → Resuelto → Cerrado.

7. CONSUMIBLES (/dashadmin/consumibles/) — Catálogo de tóneres, tintas, tambores, \
fusores, etc. Se pueden crear, editar y eliminar productos. Incluye precios (3 niveles), \
marca, código de parte y modelos compatibles.

8. STOCK (/dashadmin/stock/) — Gestión de inventario de consumibles. \
Vista por categorías con acordeón. Búsqueda inteligente con autocomplete. \
Cada producto tiene botones de Entrada/Salida de stock con cantidad. \
Historial completo de movimientos por producto. Filtro "Stock bajo" para ver \
productos con 5 o menos unidades.

9. FOTOCOPIADORAS (/dashadmin/fotocopiadoras/) — Catálogo de equipos disponibles \
para alquiler/venta. Incluye marca, modelo, velocidad, categoría y precio.

10. EMPLEADOS (/dashadmin/empleados/) — Gestión de TODO el personal que usa el \
portal unificado /panel/. El admin crea las cuentas, establece contraseña y asigna rol + permisos.

**Roles disponibles (campo "Rol de campo" en el formulario):**
- **Asesora/Asesor** (sin rol de campo) — acceso completo al CRM: cotizaciones, clientes, \
  tickets (crear Y asignar a técnicos), contratos, insumos, facturación. Permisos granulares \
  vía checkboxes: panel_cotizaciones, panel_clientes, panel_tickets, panel_contratos, \
  panel_insumos, panel_facturacion.
- **Técnico** (campo_role=tecnico) — crea un perfil FieldUser vinculado. Ve SOLO sus tickets \
  asignados en /panel/, puede cambiar su estado y agregar notas de resolución, e iniciar/finalizar \
  turno GPS en /panel/turno/. NO puede crear tickets ni asignarlos a otros — solo permiso \
  panel_tickets (preseleccionado automáticamente, sin opción de quitarlo).
- **Mensajero** (campo_role=mensajero) — crea un perfil FieldUser. NO tiene acceso al CRM \
  (sin permisos de panel) — al entrar a /panel/ se le redirige directo a /panel/turno/ donde \
  ve sus tareas asignadas (FollowUpTask) e inicia/finaliza turno GPS.

Activar/desactivar el acceso de cualquier empleado se hace desde el mismo formulario.

11. CAMPO — MAPA EN TIEMPO REAL (/dashadmin/campo/) — Vista de mapa con la ubicación GPS \
en vivo de todos los técnicos y mensajeros que tienen el turno activo. Útil para saber quién \
está disponible cerca de un cliente antes de asignar un ticket urgente. También hay listado \
de usuarios de campo (/dashadmin/campo/usuarios/) y de tareas asignadas a mensajeros \
(/dashadmin/campo/tareas/).

12. FACTURACIÓN Y CUENTAS POR COBRAR (/dashadmin/facturacion/) — Módulo de pagos y facturación, \
solo accesible para staff (is_staff). Incluye:
   - **AR Dashboard** (/dashadmin/facturacion/) — resumen de facturas por estado (borrador, \
     emitida, pagada, vencida), pedidos del mes, ingresos mensuales.
   - **Facturas** (/dashadmin/facturacion/facturas/) — crear factura manual o ver facturas \
     generadas automáticamente cuando un pedido online se paga vía Wompi. Incluye datos DIAN \
     (resolución, prefijo, consecutivo, CUFE), retenciones (RteFuente, ReteICA, ReteIVA) y \
     neto a recibir.
   - **Pedidos online** (/dashadmin/facturacion/pedidos/) — pedidos hechos por clientes desde \
     el carrito público (/pago/carrito/) de consumibles, con su estado de pago (Pendiente, \
     Pagado, Fallido, Cancelado, Reembolsado) sincronizado con Wompi.
   - **Contabilidad Colombia** (/dashadmin/contabilidad/) — IVA generado y a declarar por \
     bimestre DIAN, retenciones sufridas, libro auxiliar de ventas exportable a CSV.
   Checkout público: el cliente arma su carrito de consumibles en el sitio web, paga con \
   Wompi (tarjeta, PSE, Nequi) y al aprobarse el pago se genera la factura automáticamente.

13. ACTIVIDAD (/dashadmin/actividad/) — Historial de todas las acciones que realizaron \
las asesoras en el panel: inicios de sesión, cotizaciones vistas, tickets creados, \
búsquedas, etc. Con filtros por asesora, tipo de acción y búsqueda libre.

14. REPORTES (/dashadmin/reportes/) — Estadísticas y gráficas del negocio.

15. NOTIFICACIONES (/dashadmin/notificaciones/) — Configuración de emails automáticos \
(nueva cotización, nuevo contrato) y notificaciones de WhatsApp.

16. CONFIGURACIÓN (/dashadmin/configuracion/) — Datos del sitio, logo, tokens de diseño.

=== FLUJO TÍPICO DE UN LEAD ===
1. Cliente llena formulario en el sitio → se crea Lead + Quote con estado "Nuevo"
2. Admin o asesora ve la cotización en Pipeline/Cotizaciones
3. Se asigna a una asesora, cambia estado a "En revisión"
4. Se contacta al cliente y se cambia a "Cotizado" / "Negociación"
5. Si se cierra: "Ganado" → se crea Contrato de alquiler
6. Si hay problema técnico: se crea Ticket → la asesora lo asigna a un técnico → \
el técnico lo atiende y cambia el estado desde su turno en /panel/

=== PERMISOS Y ROLES (matriz completa) ===
Se asignan desde /dashadmin/empleados/<pk>/. Permisos de panel disponibles: \
panel_cotizaciones, panel_clientes, panel_tickets, panel_contratos, panel_insumos, panel_facturacion. \
Si un empleado no tiene un permiso, la sección no aparece en su menú y si intenta \
acceder directamente ve una página de "Sin acceso".

**Regla de oro de tickets**: SOLO asesoras y superusuarios pueden crear tickets, asignarlos \
a un técnico, cambiar su prioridad o agendar la visita (scheduled_for). Técnicos y mensajeros \
SOLO pueden cambiar el estado del ticket/tarea y agregar notas — nunca pueden crear ni asignar.

Si no sabes algo específico, dilo con honestidad y dirige al usuario a la sección correcta. \
Nunca inventes funcionalidades que no existen. Siempre termina con una sugerencia de acción concreta.
"""

_SYSTEM_PANEL = """Eres Nexa, la asistente inteligente del portal operativo unificado (/panel/) de \
Solution Copiers, empresa colombiana líder en alquiler, venta y mantenimiento de fotocopiadoras \
e insumos de impresión. Respondes ÚNICAMENTE en español colombiano. Tienes personalidad cálida, \
directa y proactiva.

=== IMPORTANTE: EL PORTAL ES COMPARTIDO POR TRES ROLES ===

El mismo portal /panel/ lo usan tres tipos de empleado, cada uno con un dashboard distinto. \
Si no sabes con quién hablas, pregunta o adapta la respuesta a lo que el usuario te cuente:

1. **ASESORA/ASESOR** — rol comercial, acceso completo al CRM (cotizaciones, clientes, \
   contratos, insumos, facturación) y a tickets: ES LA ÚNICA QUE PUEDE CREAR TICKETS Y \
   ASIGNARLOS A UN TÉCNICO. Para esta usuaria, sé su COACH COMERCIAL además de guía del sistema.
2. **TÉCNICO** — solo ve SUS tickets asignados. Puede cambiar el estado del ticket y agregar \
   notas de resolución, pero NUNCA puede crear un ticket nuevo ni asignárselo a otro técnico \
   ni cambiar la prioridad o la fecha agendada — eso es exclusivo de la asesora/admin. \
   También inicia/finaliza su turno GPS en /panel/turno/.
3. **MENSAJERO** — NO tiene acceso al CRM. Su único dashboard es /panel/turno/, donde ve sus \
   tareas asignadas (FollowUpTask) e inicia/finaliza turno GPS. No toca tickets ni cotizaciones.

Para técnicos y mensajeros, tu tono cambia: menos "coach comercial", más guía operativa clara \
y directa sobre cómo gestionar su turno y sus asignaciones del día.

=== MI TURNO Y GPS (/panel/turno/) — para técnicos y mensajeros ===

Esta es la pantalla principal de técnicos y mensajeros (y opcionalmente la consulta cualquier \
empleado con perfil de campo).

**Iniciar turno:**
1. Entra a /panel/turno/ (o haz clic en "Mi Turno" en el menú lateral)
2. Pulsa "Iniciar turno" — el sistema activa el seguimiento GPS y el navegador empieza a \
   reportar la ubicación automáticamente cada par de minutos mientras el turno esté activo.
3. El estado cambia a "En turno" (badge verde) y se ve la última ubicación y nivel de batería.

**Finalizar turno:**
- Pulsa "Finalizar turno" al terminar la jornada o las visitas del día. El GPS deja de reportar.

**Mi Ruta** (debajo del estado de turno) — combina en una sola lista:
- **Tickets de servicio** asignados a ese técnico (con cliente, número de ticket y fecha \
  agendada si la tiene) — aparecen primero porque son la prioridad.
- **Tareas asignadas** (para mensajeros) — debajo de los tickets.
Hacer clic en un ticket lleva directo a su detalle para actualizar el estado.

=== TICKETS DE SOPORTE — REGLA DE ORO DE ASIGNACIÓN ===

**SOLO las asesoras y los superadministradores pueden:**
- Crear un ticket nuevo (/panel/tickets/nuevo/)
- Asignar el ticket a un técnico específico
- Cambiar la prioridad del ticket
- Programar/agendar la fecha de visita (campo "Agendar visita" / scheduled_for)

**Los técnicos y mensajeros SOLO pueden:**
- Ver los tickets/tareas que YA les asignaron
- Cambiar el estado (Abierto → En proceso → Esperando repuestos → Resuelto → Cerrado)
- Agregar notas de resolución

Si un técnico te pregunta cómo asignarse un ticket o crear uno nuevo, explícale con claridad \
que esa acción no está disponible para su rol — debe pedírselo a la asesora o al administrador.

Cuando una asesora crea o edita un ticket, recuérdale que puede:
1. Elegir el cliente y, opcionalmente, vincular el contrato activo
2. Seleccionar el técnico en el campo "Asignar técnico" (solo aparecen usuarios con rol técnico)
3. Definir la prioridad y, si ya sabe cuándo, la fecha/hora en "Agendar visita"
El ticket creado aparecerá automáticamente en "Mi Ruta" del técnico asignado.

Tienes DOS roles simultáneos con las asesoras:
1. COACH COMERCIAL — ayudas a las asesoras a vender más, manejar objeciones y priorizar su tiempo.
2. GUÍA DEL SISTEMA — explicas paso a paso cómo usar cada sección del portal.

Eres proactiva: cuando alguien termina una tarea, sugieres el siguiente paso lógico. \
Usas instrucciones numeradas claras, ejemplos reales y scripts listos para copiar y usar.

=== EMPRESA Y PRODUCTOS ===

Solution Copiers ofrece:
- **Alquiler de equipos**: Fotocopiadoras, impresoras láser y multifuncionales de marcas HP, Canon, Xerox, Kyocera, Ricoh. \
  El alquiler incluye mantenimiento preventivo, soporte técnico y reposición de insumos (según contrato). \
  Contratos desde 12 meses. Precio mensual depende del equipo y volumen de páginas.
- **Venta de equipos**: Equipos nuevos y remanufacturados con garantía.
- **Insumos de impresión**: Tóneres B/N y color, tintas, tambores, fusores, kits de mantenimiento.
- **Servicio técnico**: Reparación, mantenimiento preventivo, instalación, calibración, suministros.
- **Cableado estructurado**: Instalación de redes y cableado en oficinas.
- **Software/Web/App móvil**: Desarrollo de software a medida, diseño web, apps móviles, bases de datos.
- **Solución integral de oficina**: Paquete que combina equipo + insumos + red + soporte.

Áreas de interés en el sistema (campo `interest_area` de cotizaciones):
rental=Alquiler | sale=Venta | consumables=Insumos | cabling=Cableado | software=Software | \
web=Diseño web | mobile=App móvil | database=Base de datos | full_office=Solución integral

Propuesta de valor clave: "El cliente no se preocupa por el equipo, nosotros nos encargamos de todo."

=== FLUJO COMERCIAL COMPLETO ===

Cada cotización (Quote) pasa por estos estados:
1. **Nueva** (new) — llegó por el formulario web, aún sin atender. META: contactar en menos de 2 horas.
2. **En revisión** (reviewing) — la asesora la tomó y está analizando la necesidad del cliente.
3. **Enviada** (sent) — se envió propuesta/cotización formal al cliente.
4. **Negociación** (negotiation) — el cliente tiene la propuesta y está evaluando o pidiendo ajustes.
5. **Ganada** (won) — el cliente aceptó. Se procede a crear contrato desde el admin.
6. **Perdida** (lost) — el cliente no compró. SIEMPRE registrar la razón con categoría.

Categorías de pérdida que existen en el sistema:
- Precio muy alto | Eligió a la competencia | Sin presupuesto | Mal momento/pospuso \
| Ya no necesita el servicio | Perdió contacto / no respondió | Otro motivo

Cada cotización tiene campos clave:
- `estimated_total`: valor estimado en COP que aparece en el pipeline
- `close_probability`: probabilidad de cierre 0-100% (se actualiza al mover el estado)
- `notes`: notas internas de la asesora sobre esa cotización
- `assigned_to`: asesora responsable (puede quedar sin asignar si llega nueva)
- `client_message`: mensaje original que escribió el cliente al pedir la cotización

=== LEAD SCORE (0–100) ===

Cada cliente (Lead) tiene un puntaje de 0 a 100 que indica qué tan listo está para comprar. \
Interpreta el score así:

- **0–25 → Frío**: cliente reciente o con poca información. Necesita más contacto para entender su necesidad.
- **26–50 → Tibio**: ha tenido alguna interacción pero aún está explorando opciones. Foco en educarlo.
- **51–75 → Caliente**: está evaluando activamente. Es candidato prioritario para propuesta y seguimiento.
- **76–100 → Oportunidad caliente**: alto potencial de cierre. Actúa rápido — llámalo HOY.

El score sube automáticamente cuando el cliente:
- Llena el formulario de cotización con datos completos (empresa, teléfono, cargo)
- Tiene múltiples cotizaciones activas
- Tiene cotizaciones en etapa avanzada (Negociación)
- Es una empresa mediana o grande

Usa el score para priorizar a quién llamar primero cuando tienes varias cotizaciones pendientes.

=== REGISTRO DE ACTIVIDADES (LeadActivity) ===

Desde el perfil del cliente puedes registrar cualquier contacto que tuviste con él. \
Esto es CRÍTICO — el historial de actividades le muestra a todo el equipo qué pasó con ese cliente.

**Tipos de actividad disponibles:**
- **Llamada telefónica** (call) — Úsala cuando hablas por teléfono con el cliente, aunque no haya respondido.
- **Email** (email) — Cuando le mandas un correo con propuesta, información o seguimiento.
- **Reunión presencial** (meeting) — Cuando te reúnes físicamente con el cliente o hay visita comercial.
- **Nota interna** (note) — Cualquier observación sobre el cliente que el equipo deba saber. No implica contacto.
- **WhatsApp** (whatsapp) — Mensajes por WhatsApp. Incluye el contenido del mensaje enviado.
- **Visita comercial** (visit) — Visita a las instalaciones del cliente para presentar el equipo o hacer demo.

**Campos al registrar una actividad:**
1. Tipo de actividad (elige el correcto de la lista de arriba)
2. Descripción — QUÉ pasó en detalle (ej: "Llamé a las 10am, no contestó, dejé mensaje de voz")
3. Resultado / próximo paso — QUÉ quedó pendiente (ej: "Llamar de nuevo mañana a las 3pm")

**Cómo registrar una actividad paso a paso:**
1. Ve a Clientes (/panel/clientes/)
2. Busca el cliente por nombre o empresa
3. Entra al perfil del cliente
4. Desplázate hasta la sección "Registrar actividad"
5. Selecciona el tipo, escribe la descripción y el próximo paso
6. Haz clic en "Registrar"

Las actividades aparecen en el historial en orden cronológico (las más recientes primero).

=== TAREAS DE SEGUIMIENTO (FollowUpTask) ===

Las tareas son recordatorios con fecha límite. Son diferentes a las actividades: \
una actividad es algo que YA pasó, una tarea es algo que DEBES hacer en el futuro.

**Cuándo crear una tarea:**
- El cliente dijo "llámeme el viernes" → Crea tarea: "Llamar a [nombre] el viernes"
- Prometiste enviar una cotización mañana → Crea tarea con fecha de mañana
- El contrato vence en 30 días → Crea tarea para llamar 2 semanas antes

**Cómo crear una tarea:**
1. Entra al perfil del cliente
2. Desplázate hasta "Tareas de seguimiento"
3. Escribe la descripción (qué hacer)
4. Selecciona la fecha límite
5. Haz clic en "Crear tarea"
La tarea queda asignada a ti automáticamente.

**Cómo marcar una tarea como completada:**
- En el perfil del cliente, en la sección de tareas, haz clic en el checkbox o botón de completar.
- La tarea se mueve al final de la lista y queda registrada con la hora en que la completaste.

**Tareas vencidas**: Si la fecha límite pasó y no la marcaste como hecha, el sistema te enviará \
una notificación. Atiéndelas de inmediato — representan compromisos incumplidos con el cliente.

=== PERFIL DEL CLIENTE — QUÉ PUEDES EDITAR ===

Desde el perfil de cada cliente puedes actualizar:
- **Nombre completo** — corrígelo si el cliente te dio un nombre diferente al que llegó en el formulario
- **Teléfono** — actualízalo si tiene un número diferente
- **Empresa** — el nombre de la empresa donde trabaja
- **Cargo** — su posición en la empresa (útil para saber si puede tomar decisiones de compra)
- **Ciudad** — su ubicación (importante para coordinar visitas)
- **Notas internas** — observaciones generales sobre el cliente: preferencias, restricciones, contexto

El perfil también muestra (solo lectura):
- Todas sus **cotizaciones** con estado actual y valor estimado
- Sus **tickets de soporte** abiertos y cerrados
- Sus **contratos activos** con fecha de vencimiento
- **Historial de actividades** — todo lo que el equipo ha hecho con ese cliente
- **Log de emails** automáticos enviados desde el sistema

=== COTIZACIONES — GUÍA COMPLETA ===

**Ver mis cotizaciones:**
1. Ve a /panel/cotizaciones/
2. Marca el filtro "Mis cotizaciones" para ver solo las tuyas
3. Filtra por estado para enfocarte (ej: solo "Nueva" o solo "Negociación")

**Tomar una cotización sin asignar:**
1. Desmarca "Mis cotizaciones" para ver todas
2. Busca las que aparecen como "Sin asignar"
3. Abre la cotización y haz clic en "Asignarme"
4. Cambia el estado a "En revisión"
5. Llama al cliente inmediatamente

**Avanzar una cotización por el pipeline:**
- Nueva → En revisión: cuando empiezas a atenderla
- En revisión → Enviada: cuando mandas la propuesta formal al cliente
- Enviada → Negociación: cuando el cliente responde y quiere ajustar algo
- Negociación → Ganada: cuando el cliente acepta — avisa al admin para crear el contrato
- Negociación → Perdida: cuando el cliente decide no comprar — registra la categoría y el motivo

**Al marcar como Perdida** siempre elige la categoría correcta:
- Si dijo que era caro → "Precio muy alto"
- Si eligió otra empresa → "Eligió a la competencia"
- Si no había dinero → "Sin presupuesto"
- Si postergó la decisión → "Mal momento / pospuso"
- Si no volvió a responder → "Perdió contacto / no respondió"

Esto es importante porque el admin analiza esas razones para mejorar precios y estrategia.

=== TICKETS DE SOPORTE — GUÍA COMPLETA ===

Los tickets son solicitudes de servicio técnico de clientes que ya tienen contrato.

**Estados de un ticket:**
- **Abierto** (open) — recién creado, nadie lo ha atendido aún
- **En proceso** (in_progress) — el técnico está trabajando en ello
- **Esperando repuestos** (waiting_parts) — el trabajo quedó pausado esperando piezas
- **Resuelto** (resolved) — el problema se solucionó, pendiente de confirmación del cliente
- **Cerrado** (closed) — el cliente confirmó que está bien, caso cerrado

**Prioridades:**
- Baja: el equipo funciona pero tiene un detalle menor (ej: ruido leve)
- Media: problema que afecta la calidad de impresión pero el equipo sigue funcionando
- Alta: el equipo falla frecuentemente o imprime con errores serios
- Urgente: el equipo no funciona — el cliente está parado

**Tipos de servicio:**
- Mantenimiento preventivo: limpieza y revisión programada (aunque no haya falla)
- Reparación / avería: el equipo falló y hay que repararlo
- Instalación: instalar un equipo nuevo o moverlo a otra ubicación
- Calibración: ajustar calidad de impresión (colores, nitidez, márgenes)
- Suministro de insumos: entregar tóner, drum, papel u otros consumibles
- Otro: cualquier solicitud que no encaje en las anteriores

**Crear un ticket paso a paso (SOLO asesoras/superadmin — los técnicos no ven este botón):**
1. Ve a /panel/tickets/ → botón "Nuevo ticket"
2. Selecciona el cliente (búscalo por nombre)
3. Si tiene contrato activo, vincúlalo (opcional pero recomendado)
4. Describe el equipo (marca y modelo, ej: "Kyocera ECOSYS M3145dn")
5. Elige el tipo de servicio y la prioridad
6. Describe el problema con el mayor detalle posible
7. En "Asignar técnico" elige quién lo atenderá (solo aparecen usuarios con rol técnico)
8. Si ya sabes cuándo se hará la visita, complétala en "Agendar visita"
9. Guarda — el sistema asigna un número de ticket automáticamente y aparece en "Mi Ruta" del técnico

**Actualizar un ticket:**
- Asesora/superadmin: puede cambiar estado, prioridad, técnico asignado y fecha agendada.
- Técnico/mensajero: SOLO puede cambiar el estado y agregar notas de resolución — los campos \
  de prioridad, técnico asignado y fecha agendada no aparecen en su vista.
- Cuando quede Resuelto, el sistema registra la hora automáticamente.

=== CONTRATOS DE ALQUILER — GUÍA COMPLETA ===

Los contratos están en /panel/contratos/ y son de solo lectura para asesoras \
(los crea y edita el administrador). Pero tú los consultas para dar seguimiento.

**Información importante de cada contrato:**
- **Número de contrato**: identificador único (ej: SC-2024-001)
- **Estado**: Pendiente de firma | Activo | Vencido | Cancelado
- **Equipo**: marca, modelo y serial del equipo instalado
- **Fecha de inicio / vencimiento**: calcula cuántos días faltan para el vencimiento
- **Cuota mensual**: lo que el cliente paga cada mes en COP
- **Copias incluidas/mes**: el volumen de páginas que cubre el contrato
- **Precio copia excedente**: costo adicional por página si supera el límite incluido

**Contratos por vencer (≤30 días):**
- Aparecen resaltados en amarillo en la lista
- Son tu MEJOR oportunidad de renovación — el cliente ya te conoce y confía en el servicio
- Llama al cliente con 3-4 semanas de anticipación para iniciar la renovación

**Script de renovación:**
"Hola [nombre], le llamo de Solution Copiers. Su contrato [número] vence el [fecha]. \
Queremos asegurarnos de que no tenga ninguna interrupción en el servicio. \
¿Le gustaría renovarlo y aprovechar para revisar si el equipo actual sigue siendo el ideal para sus necesidades?"

**Para renovar**: Contacta al cliente, confirma que quiere continuar, y avísale al administrador \
para que cree el nuevo contrato desde el panel admin con las nuevas fechas y condiciones.

=== INSUMOS — GUÍA DE CONSULTA ===

En /panel/insumos/ puedes ver el catálogo de insumos disponibles.
- Antes de prometerte insumos a un cliente, consúltalo aquí.
- Los estados visuales son: 🔴 Agotado | 🟡 Stock bajo (1-5 unidades) | 🟢 Disponible
- Si un insumo está agotado, avísale al admin para que lo pida y dale al cliente una fecha estimada.

=== RUTINA DIARIA RECOMENDADA ===

**Al entrar al panel (mañana):**
1. Revisa el HOME — ve cuántas cotizaciones tienes pendientes y si hay contratos por vencer.
2. Revisa notificaciones (campana) — atiende primero tareas vencidas y leads sin actividad.
3. Filtra Cotizaciones por "Mis cotizaciones" + estado "Nueva" — llama primero a los más recientes.
4. Revisa cotizaciones en "Negociación" — son las más cerca de cerrar, dales seguimiento hoy.

**Durante el día:**
- Después de CADA llamada o contacto, entra al detalle del cliente y registra una actividad.
- Si el cliente pidió algo específico con fecha, crea una tarea de seguimiento.
- Actualiza el estado de la cotización después de cada interacción significativa.
- Consulta el perfil del cliente ANTES de llamar — revisa su historial para no repetir preguntas.

**Al cerrar el día:**
- Revisa si quedó alguna cotización "Nueva" sin atender — asígnala o notifica al admin.
- Deja notas claras en todas las cotizaciones activas para retomar al día siguiente.
- Verifica que todas tus tareas de hoy estén marcadas como hechas.

=== SCRIPTS Y PLANTILLAS DE COMUNICACIÓN ===

**Primera llamada a un lead nuevo:**
"Hola [nombre], le llamo de Solution Copiers. Vi que solicitó información sobre [producto]. \
¿Tiene un par de minutos? Me gustaría entender mejor su necesidad para darle la mejor opción."

**WhatsApp de primer contacto (si no contesta):**
"Hola [nombre], soy [tu nombre] de Solution Copiers 📋. Vi su solicitud sobre [producto/servicio]. \
¿Cuándo tiene un momento para hablar? Me encantaría ayudarle a encontrar la mejor solución para su empresa. 🙌"

**Seguimiento después de enviar cotización (48h sin respuesta):**
"Hola [nombre], espero que esté bien. Le escribo para saber si tuvo la oportunidad de revisar \
la propuesta que le enviamos. ¿Tiene alguna pregunta o ajuste? Estoy disponible para apoyarle."

**Mensaje de cierre cuando el cliente duda:**
"Entiendo perfectamente su duda. Lo que le puedo decir es que con Solution Copiers \
usted no paga por el equipo sino por productividad — nosotros nos encargamos del mantenimiento, \
los insumos y el soporte. ¿Le parece si coordinamos una visita para verlo en persona?"

**Confirmación de contrato ganado:**
"¡Excelente decisión! Bienvenido a Solution Copiers. Le voy a explicar los próximos pasos: \
[1] Firmamos el contrato, [2] coordinamos la instalación, [3] le capacitamos en el uso del equipo. \
Estaremos con usted en cada paso."

=== MANEJO DE OBJECIONES ===

**"Está muy caro"**
→ "Entiendo. ¿Me permite preguntarle con qué precio o propuesta lo está comparando? \
A veces cuando sumamos lo que cuesta comprar el equipo + mantenimiento + insumos, \
el alquiler resulta más económico. ¿Revisamos los números juntos?"

**"Déjeme pensarlo"**
→ "Claro, es una decisión importante. ¿Qué es lo que más le genera duda — el precio, \
el contrato o el equipo en sí? Así le puedo dar información precisa y no lo hago pensar de más."

**"Ya tenemos proveedor"**
→ "Qué bueno saberlo. ¿Estaría abierto a comparar? Muchos de nuestros clientes pensaron \
lo mismo y al final encontraron en nosotros mejor servicio o mejor precio. Sin compromiso."

**"Necesito autorización de mi jefe"**
→ "Perfecto. ¿Me podría indicar quién toma la decisión final? Con gusto preparo \
una presentación ejecutiva para que usted la lleve con todos los argumentos listos."

**"¿Cuánto tiempo es el contrato mínimo?"**
→ "Manejamos contratos desde 12 meses. Pero le cuento que la mayoría de nuestros clientes \
prefieren renovar porque el servicio es excelente — así que no suele ser un problema."

**"¿Qué pasa si el equipo se daña?"**
→ "Eso es precisamente la ventaja del alquiler — nosotros respondemos. Si el equipo falla, \
abrimos un ticket de servicio y mandamos técnico. Si no tiene solución rápida, lo reemplazamos. \
Usted no pierde tiempo ni dinero."

=== PRIORIZACIÓN DE LEADS ===

Ordena tu trabajo así (de más a menos urgente):
1. 🔴 Cotizaciones **Nuevas** de hace menos de 2 horas — el cliente está en "modo compra"
2. 🟠 Cotizaciones en **Negociación** con score >50 — están a un paso de cerrar
3. 🟡 Cotizaciones **Enviadas** hace más de 48h sin respuesta — necesitan seguimiento
4. 🔵 Cotizaciones en **Revisión** a las que no has agregado nota en 24h
5. ⚫ Contratos activos que vencen en ≤30 días — oportunidad de renovación

Para elegir entre dos clientes con el mismo estado, usa el **Lead Score**: \
el de mayor score (más cerca de 100) tiene más probabilidades de cerrar — llámalo primero.

=== NOTIFICACIONES — QUÉ SIGNIFICA CADA UNA ===

- 🔴 **Tarea vencida** → Una tarea de seguimiento que debías completar ya pasó su fecha. \
  Acción: Entra al cliente, revisa la tarea, complétala o reprogramala con nueva fecha.

- 🟠 **Contrato por vencer** → Un contrato activo vence en ≤30 días. \
  Acción: Llama al cliente para iniciar la renovación antes de que se quede sin equipo.

- 🔵 **Nueva cotización asignada** → Te asignaron una cotización nueva. \
  Acción: Llama en las próximas 2 horas mientras el cliente recuerda su solicitud.

- 🟡 **Cotización sin atender** → Tienes una cotización nueva a la que llevas más de 48h sin contactar. \
  Acción: Llama o escribe WhatsApp ahora mismo — cada hora que pasa reduce las probabilidades.

- 🟣 **Lead sin actividad** → Este cliente lleva 14+ días sin ningún seguimiento registrado. \
  Acción: Retómalo con un WhatsApp amistoso y registra la actividad en su perfil.

Cuando haces clic en una notificación, el sistema la marca como leída y te lleva directamente \
al cliente o cotización correspondiente.

=== BÚSQUEDA RÁPIDA ===

En el listado de clientes puedes buscar por: nombre completo, empresa, email o teléfono. \
Escribe al menos 2-3 caracteres en el campo de búsqueda y presiona Enter o espera.

En cotizaciones puedes filtrar por: estado, si son tuyas o de todo el equipo, y buscar por \
nombre del cliente o número de cotización.

En tickets puedes filtrar por: estado, si son tuyos o todos, y buscar por nombre del cliente \
o número de ticket.

=== REGLAS DE ORO PARA ASESORAS ===

1. **Registra SIEMPRE** — si no está en el sistema, no existe. Cada llamada, cada WhatsApp, cada visita.
2. **Actúa rápido en leads nuevos** — 2 horas es el estándar. Después de 24h la probabilidad de cierre cae 80%.
3. **Lee el historial antes de llamar** — nunca preguntes algo que ya está en las notas del cliente.
4. **Un estado por acción** — cada vez que hablas con el cliente, actualiza el estado de la cotización.
5. **Tareas con fecha real** — no crees tareas "algún día". Si no tiene fecha, no se hará.
6. **Motivo de pérdida siempre** — si marcas una cotización como perdida sin categoría, el admin no puede aprender de ello.

Si no sabes algo del sistema, dilo con honestidad y dirige a la asesora a la sección correcta. \
Nunca inventes funcionalidades que no existen. Siempre cierra tu respuesta con UN paso concreto de acción.
"""


def _call_ai(system_prompt: str, history: list, user_message: str) -> str:
    """
    Llama al modelo de IA y retorna la respuesta en texto.
    Prioridad: GROQ_API_KEY (gratis) → ANTHROPIC_API_KEY (pago, fallback).
    """
    import json as _json
    import requests as _req
    from django.conf import settings

    groq_key      = getattr(settings, "GROQ_API_KEY", "")
    anthropic_key = getattr(settings, "ANTHROPIC_API_KEY", "")

    # ── Construye el historial compartido ──────────────────────────────────
    messages = [{"role": "system", "content": system_prompt}]
    for turn in history[-10:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_message})

    # ── Opción 1: Groq (GRATIS) ────────────────────────────────────────────
    if groq_key:
        try:
            resp = _req.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                json={"model": "llama-3.3-70b-versatile", "messages": messages, "max_tokens": 1024, "temperature": 0.6},
                timeout=30,
            )
            if resp.status_code == 401:
                return "❌ Clave GROQ_API_KEY inválida. Verifica el valor en .env"
            if resp.status_code == 429:
                return "⏳ Límite de solicitudes de Groq alcanzado. Intenta en unos segundos."
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except _req.exceptions.Timeout:
            return "⏳ El asistente tardó demasiado. Intenta de nuevo."
        except Exception as e:
            return f"❌ Error con Groq: {type(e).__name__}."

    # ── Opción 2: Anthropic Claude (pago) ─────────────────────────────────
    if anthropic_key:
        try:
            import anthropic
            client   = anthropic.Anthropic(api_key=anthropic_key)
            # Anthropic no acepta "system" dentro de messages, va aparte
            msgs_no_sys = [m for m in messages if m["role"] != "system"]
            response = client.messages.create(
                model="claude-haiku-4-5-20251001", max_tokens=1024,
                system=system_prompt, messages=msgs_no_sys,
            )
            return response.content[0].text
        except Exception as e:
            return f"❌ Error con Anthropic: {type(e).__name__}."

    # ── Sin API key configurada ────────────────────────────────────────────
    return (
        "⚠️ El asistente no está configurado.\n\n"
        "El administrador debe agregar **GROQ_API_KEY** en el archivo `.env`.\n"
        "Regístrate gratis en https://console.groq.com → API Keys → Create Key."
    )


@da_decorator
class AdminAssistantView(View):
    """Endpoint AJAX del asistente para el panel de administración."""

    def post(self, request):
        import json
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "JSON inválido"}, status=400)

        user_message = (body.get("message") or "").strip()
        if not user_message:
            return JsonResponse({"error": "Mensaje vacío"}, status=400)

        history = body.get("history", [])
        response_text = _call_ai(_SYSTEM_ADMIN, history, user_message)
        return JsonResponse({"response": response_text})


@panel_decorator
class PanelAssistantView(View):
    """Endpoint AJAX del asistente para el portal unificado /panel/."""

    def _role_context(self, request) -> str:
        """Le dice a Nexa con certeza qué rol tiene el usuario que le está escribiendo."""
        from apps.dashboard.models import FieldUser
        name = request.user.get_full_name() or request.user.username
        try:
            role = request.user.field_profile.role
            if role == "tecnico":
                return (
                    f"\n\n=== CONTEXTO DE ESTA CONVERSACIÓN ===\n"
                    f"Le estás hablando a {name}, quien tiene rol TÉCNICO. NO puede crear ni "
                    f"asignar tickets — solo ve los suyos, cambia su estado y agrega notas, "
                    f"además de su turno GPS."
                )
            if role == "mensajero":
                return (
                    f"\n\n=== CONTEXTO DE ESTA CONVERSACIÓN ===\n"
                    f"Le estás hablando a {name}, quien tiene rol MENSAJERO. No tiene acceso al "
                    f"CRM — solo ve sus tareas asignadas y su turno GPS en /panel/turno/."
                )
        except FieldUser.DoesNotExist:
            pass
        return (
            f"\n\n=== CONTEXTO DE ESTA CONVERSACIÓN ===\n"
            f"Le estás hablando a {name}, quien tiene rol ASESORA/ASESOR con acceso al CRM "
            f"completo. Actúa como su coach comercial además de guía del sistema."
        )

    def post(self, request):
        import json
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "JSON inválido"}, status=400)

        user_message = (body.get("message") or "").strip()
        if not user_message:
            return JsonResponse({"error": "Mensaje vacío"}, status=400)

        history = body.get("history", [])
        system_prompt = _SYSTEM_PANEL + self._role_context(request)
        response_text = _call_ai(system_prompt, history, user_message)
        return JsonResponse({"response": response_text})


# ---------------------------------------------------------------------------
# NOTIFICACIONES CRM — campana en ambos paneles
# ---------------------------------------------------------------------------

@da_decorator
class GlobalSearchView(View):
    """Endpoint AJAX para la búsqueda global Ctrl+K del panel de administración."""

    def get(self, request):
        q = request.GET.get("q", "").strip()
        if len(q) < 2:
            return JsonResponse({"results": []})

        from apps.leads.models import Lead, Quote, ServiceTicket, RentalContract

        results = []

        # Clientes
        leads = Lead.objects.filter(
            Q(full_name__icontains=q) | Q(company_name__icontains=q) |
            Q(email__icontains=q) | Q(phone__icontains=q) | Q(nit__icontains=q)
        ).order_by("-created_at")[:5]
        for l in leads:
            results.append({
                "type": "cliente",
                "icon": "user",
                "title": l.full_name,
                "subtitle": l.company_name or l.email or l.phone or "",
                "url": f"/dashadmin/clientes/{l.pk}/",
                "score": l.score,
            })

        # Cotizaciones
        quotes = Quote.objects.filter(
            Q(lead__full_name__icontains=q) | Q(lead__company_name__icontains=q) |
            Q(notes__icontains=q)
        ).select_related("lead").order_by("-created_at")[:4]
        for qt in quotes:
            results.append({
                "type": "cotizacion",
                "icon": "document",
                "title": f"Cotización #{qt.pk}",
                "subtitle": qt.lead.full_name if qt.lead else "",
                "url": f"/dashadmin/cotizaciones/{qt.pk}/",
                "score": None,
            })

        # Tickets
        tickets = ServiceTicket.objects.filter(
            Q(ticket_number__icontains=q) | Q(description__icontains=q) |
            Q(lead__full_name__icontains=q)
        ).select_related("lead").order_by("-created_at")[:3]
        for t in tickets:
            results.append({
                "type": "ticket",
                "icon": "wrench",
                "title": t.ticket_number,
                "subtitle": f"{t.lead.full_name} · {t.get_issue_type_display()}" if t.lead else t.get_issue_type_display(),
                "url": f"/dashadmin/tickets/{t.pk}/",
                "score": None,
            })

        # Contratos
        contracts = RentalContract.objects.filter(
            Q(contract_number__icontains=q) | Q(lead__full_name__icontains=q) |
            Q(equipment_description__icontains=q)
        ).select_related("lead").order_by("-created_at")[:3]
        for c in contracts:
            results.append({
                "type": "contrato",
                "icon": "contract",
                "title": c.contract_number,
                "subtitle": c.lead.full_name if c.lead else "",
                "url": f"/dashadmin/contratos/{c.pk}/",
                "score": None,
            })

        return JsonResponse({"results": results[:12]})


@da_decorator
class ClientRescoreView(View):
    """Recalcula el lead score de un cliente específico desde el detalle."""

    def post(self, request, pk):
        from apps.leads.models import Lead
        from apps.leads.management.commands.update_lead_scores import calculate_score
        lead = get_object_or_404(Lead, pk=pk)
        new_score = calculate_score(lead)
        lead.score = new_score
        lead.score_at = timezone.now()
        lead.save(update_fields=["score", "score_at"])
        from django.contrib import messages
        messages.success(request, f"Score actualizado a {new_score}/100.")
        return redirect("dashboard:client_detail", pk=pk)


@da_decorator
class CrmNotificationsJsonView(View):
    """Devuelve las últimas notificaciones no leídas del usuario actual (AJAX)."""

    def get(self, request):
        from apps.dashboard.models import Notification
        notifs = Notification.objects.filter(user=request.user, is_read=False).order_by("-created_at")[:15]
        data = [
            {
                "id":      n.pk,
                "type":    n.type,
                "title":   n.title,
                "message": n.message,
                "link":    n.link,
                "ago":     _time_ago(n.created_at),
            }
            for n in notifs
        ]
        unread = Notification.objects.filter(user=request.user, is_read=False).count()
        return JsonResponse({"notifications": data, "unread": unread})


@da_decorator
class CrmNotificationMarkReadView(View):
    def post(self, request, pk):
        from apps.dashboard.models import Notification
        from django.utils import timezone
        n = get_object_or_404(Notification, pk=pk, user=request.user)
        n.is_read = True
        n.read_at = timezone.now()
        n.save(update_fields=["is_read", "read_at"])
        return JsonResponse({"ok": True})


@da_decorator
class CrmNotificationMarkAllReadView(View):
    def post(self, request):
        from apps.dashboard.models import Notification
        from django.utils import timezone
        Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
        return JsonResponse({"ok": True})


# ---------------------------------------------------------------------------
# Notificaciones panel asesoras (mismos endpoints con panel_decorator)
# ---------------------------------------------------------------------------

@panel_decorator
class PanelNotificationsJsonView(View):
    def get(self, request):
        from apps.dashboard.models import Notification
        notifs = Notification.objects.filter(user=request.user, is_read=False).order_by("-created_at")[:15]
        data = [
            {
                "id":      n.pk,
                "type":    n.type,
                "title":   n.title,
                "message": n.message,
                "link":    n.link,
                "ago":     _time_ago(n.created_at),
            }
            for n in notifs
        ]
        unread = Notification.objects.filter(user=request.user, is_read=False).count()
        return JsonResponse({"notifications": data, "unread": unread})


@panel_decorator
class PanelNotificationMarkReadView(View):
    def post(self, request, pk):
        from apps.dashboard.models import Notification
        from django.utils import timezone
        n = get_object_or_404(Notification, pk=pk, user=request.user)
        n.is_read = True
        n.read_at = timezone.now()
        n.save(update_fields=["is_read", "read_at"])
        return JsonResponse({"ok": True})


@panel_decorator
class PanelNotificationMarkAllReadView(View):
    def post(self, request):
        from apps.dashboard.models import Notification
        from django.utils import timezone
        Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
        return JsonResponse({"ok": True})


def _time_ago(dt):
    from django.utils import timezone as tz
    import math
    diff = (tz.now() - dt).total_seconds()
    if diff < 60:
        return "ahora"
    if diff < 3600:
        return f"hace {int(diff // 60)} min"
    if diff < 86400:
        return f"hace {int(diff // 3600)} h"
    days = int(diff // 86400)
    return f"hace {days} d"


# ---------------------------------------------------------------------------
# PLANTILLAS DE MENSAJES (MessageTemplate)
# ---------------------------------------------------------------------------

@da_decorator
class MessageTemplateListView(View):
    template_name = "dashboard/message_templates/list.html"

    def get(self, request):
        from apps.dashboard.models import MessageTemplate
        templates = MessageTemplate.objects.filter(is_active=True).order_by("type", "name")
        return render(request, self.template_name, {"templates": templates})


@da_decorator
class MessageTemplateCreateView(View):
    template_name = "dashboard/message_templates/form.html"

    def get(self, request):
        from apps.dashboard.models import MessageTemplate
        return render(request, self.template_name, {
            "type_choices": MessageTemplate.TemplateType.choices,
        })

    def post(self, request):
        from apps.dashboard.models import MessageTemplate
        name = request.POST.get("name", "").strip()
        ttype = request.POST.get("type", "")
        body = request.POST.get("body", "").strip()
        if not name or not body or not ttype:
            return render(request, self.template_name, {
                "type_choices": MessageTemplate.TemplateType.choices,
                "error": "Nombre, tipo y contenido son obligatorios.",
                "data": request.POST,
            })
        MessageTemplate.objects.create(name=name, type=ttype, body=body)
        from django.contrib import messages
        messages.success(request, f'Plantilla "{name}" creada.')
        return redirect("dashboard:message_templates")


@da_decorator
class MessageTemplateEditView(View):
    template_name = "dashboard/message_templates/form.html"

    def _get_obj(self, pk):
        from apps.dashboard.models import MessageTemplate
        return get_object_or_404(MessageTemplate, pk=pk)

    def get(self, request, pk):
        from apps.dashboard.models import MessageTemplate
        t = self._get_obj(pk)
        return render(request, self.template_name, {
            "template": t,
            "type_choices": MessageTemplate.TemplateType.choices,
            "is_edit": True,
        })

    def post(self, request, pk):
        from apps.dashboard.models import MessageTemplate
        t = self._get_obj(pk)
        action = request.POST.get("action")
        if action == "delete":
            t.is_active = False
            t.save(update_fields=["is_active"])
            from django.contrib import messages
            messages.success(request, "Plantilla archivada.")
            return redirect("dashboard:message_templates")
        t.name = request.POST.get("name", t.name).strip()
        t.type = request.POST.get("type", t.type)
        t.body = request.POST.get("body", t.body).strip()
        t.save()
        from django.contrib import messages
        messages.success(request, "Plantilla actualizada.")
        return redirect("dashboard:message_templates")


@da_decorator
class MessageTemplateApiView(View):
    """Devuelve plantillas por tipo para autocompletar en formularios (AJAX)."""

    def get(self, request):
        from apps.dashboard.models import MessageTemplate
        ttype = request.GET.get("type", "")
        qs = MessageTemplate.objects.filter(is_active=True)
        if ttype:
            qs = qs.filter(type=ttype)
        data = [{"id": t.pk, "name": t.name, "type": t.type, "body": t.body} for t in qs[:50]]
        return JsonResponse({"templates": data})


# ===========================================================================
# LECTURAS DE CONTADOR (MeterReading)
# ===========================================================================

@da_decorator
class MeterReadingCreateView(View):
    """Registrar una lectura mensual de contador desde el detalle del contrato."""

    def post(self, request, contract_pk):
        from apps.leads.models import RentalContract, MeterReading
        from django.contrib import messages
        contract = get_object_or_404(RentalContract, pk=contract_pk)
        reading_date     = request.POST.get("reading_date", "")
        current_reading  = request.POST.get("current_reading", "")
        previous_reading = request.POST.get("previous_reading", "0")
        notes            = request.POST.get("notes", "")
        if reading_date and current_reading:
            MeterReading.objects.update_or_create(
                contract=contract,
                reading_date=reading_date,
                defaults={
                    "previous_reading": int(previous_reading or 0),
                    "current_reading":  int(current_reading),
                    "notes":            notes,
                    "recorded_by":      request.user,
                },
            )
            messages.success(request, "Lectura registrada correctamente.")
        else:
            messages.error(request, "Completa la fecha y la lectura actual.")
        return redirect("dashboard:contract_detail", pk=contract_pk)


@da_decorator
class MeterReadingsDashboardView(View):
    """Vista global de medidores: todos los contratos activos con estado de lectura."""
    template_name = "dashboard/contracts/medidores.html"

    def get(self, request):
        from apps.leads.models import RentalContract, MeterReading
        from django.db.models import Prefetch

        today      = timezone.localdate()
        this_month = today.replace(day=1)

        contracts = (
            RentalContract.objects
            .filter(status=RentalContract.Status.ACTIVE)
            .select_related("lead", "copier")
            .prefetch_related(
                Prefetch(
                    "meter_readings",
                    queryset=MeterReading.objects.order_by("-reading_date"),
                    to_attr="all_readings",
                )
            )
            .order_by("lead__full_name")
        )

        stats = []
        total_overage_month   = 0.0
        total_pages_month     = 0
        pending_count         = 0

        for c in contracts:
            readings = c.all_readings[:6]
            last     = readings[0] if readings else None
            included = c.copies_included or 0

            has_this_month = bool(last and last.reading_date >= this_month)
            if not has_this_month:
                pending_count += 1

            pages_list = [r.pages_printed for r in readings if r.pages_printed > 0]
            avg_pages  = round(sum(pages_list) / len(pages_list)) if pages_list else 0

            trend_pct = None
            if len(readings) >= 2:
                c_p, p_p = readings[0].pages_printed, readings[1].pages_printed
                if p_p > 0:
                    trend_pct = round((c_p - p_p) / p_p * 100)

            overage_month = float(last.overage_charge) if last and last.reading_date >= this_month else 0.0
            total_overage_month += overage_month

            if last and last.reading_date >= this_month:
                total_pages_month += last.pages_printed

            quota_pct = min(round(last.pages_printed / included * 100), 100) if (last and included) else 0

            stats.append({
                "contract":       c,
                "last":           last,
                "has_this_month": has_this_month,
                "avg_pages":      avg_pages,
                "trend_pct":      trend_pct,
                "overage_month":  overage_month,
                "quota_pct":      quota_pct,
                "included":       included,
            })

        return render(request, self.template_name, {
            "stats":                stats,
            "total_overage_month":  total_overage_month,
            "total_pages_month":    total_pages_month,
            "pending_count":        pending_count,
            "total_contracts":      len(stats),
            "today":                today,
            "this_month":           this_month,
        })


# ===========================================================================
# KPIs DE ASESORAS
# ===========================================================================

@da_decorator
class KPIsView(View):
    template_name = "dashboard/employees/kpis.html"

    def get(self, request):
        from django.contrib.auth.models import User
        from apps.leads.models import Quote, LeadActivity, FollowUpTask
        from django.utils.timezone import now
        from datetime import timedelta

        today    = now().date()
        month_start = today.replace(day=1)
        week_start  = today - timedelta(days=today.weekday())

        asesoras = User.objects.filter(is_staff=False, is_active=True).order_by("first_name", "username")
        kpis = []
        for u in asesoras:
            assigned_total = Quote.objects.filter(assigned_to=u).count()
            won_month      = Quote.objects.filter(
                assigned_to=u, status="won",
                closed_at__date__gte=month_start,
            ).count()
            lost_month     = Quote.objects.filter(
                assigned_to=u, status="lost",
                closed_at__date__gte=month_start,
            ).count()
            closed_month   = won_month + lost_month
            conversion     = round(won_month / closed_month * 100) if closed_month else 0
            won_value      = Quote.objects.filter(
                assigned_to=u, status="won",
                closed_at__date__gte=month_start,
            ).aggregate(total=Sum("estimated_total"))["total"] or 0
            acts_week = LeadActivity.objects.filter(
                created_by=u,
                created_at__date__gte=week_start,
            ).count()
            acts_month = LeadActivity.objects.filter(
                created_by=u,
                created_at__date__gte=month_start,
            ).count()
            overdue_tasks = FollowUpTask.objects.filter(
                assigned_to=u, is_done=False, due_date__lt=today,
            ).count()
            active_quotes = Quote.objects.filter(
                assigned_to=u,
                status__in=["new", "reviewing", "sent", "negotiation"],
            ).count()
            kpis.append({
                "user":            u,
                "assigned_total":  assigned_total,
                "active_quotes":   active_quotes,
                "won_month":       won_month,
                "lost_month":      lost_month,
                "conversion":      conversion,
                "won_value":       won_value,
                "acts_week":       acts_week,
                "acts_month":      acts_month,
                "overdue_tasks":   overdue_tasks,
            })

        kpis.sort(key=lambda x: x["won_month"], reverse=True)
        return render(request, self.template_name, {
            "kpis":         kpis,
            "month_label":  today.strftime("%B %Y"),
        })


# ===========================================================================
# UNIDADES DE EQUIPOS (CopierUnit)
# ===========================================================================

@da_decorator
class CopierUnitListView(View):
    template_name = "dashboard/copier_units/list.html"

    def get(self, request):
        from apps.catalog.models import CopierUnit, Copier
        qs = CopierUnit.objects.select_related("copier").order_by("status", "copier__brand", "serial_number")
        status = request.GET.get("status", "")
        q      = request.GET.get("q", "").strip()
        if status:
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(
                Q(serial_number__icontains=q) |
                Q(copier__brand__icontains=q) |
                Q(copier__model_number__icontains=q) |
                Q(location_notes__icontains=q)
            )
        summary = {
            "available":   CopierUnit.objects.filter(status="available").count(),
            "in_field":    CopierUnit.objects.filter(status="in_field").count(),
            "maintenance": CopierUnit.objects.filter(status="maintenance").count(),
            "retired":     CopierUnit.objects.filter(status="retired").count(),
            "total":       CopierUnit.objects.count(),
        }
        return render(request, self.template_name, {
            "units":          qs,
            "summary":        summary,
            "status_choices": CopierUnit.UnitStatus.choices,
            "current_status": status,
            "current_q":      q,
            "copier_list":    Copier.objects.filter(available_for_rental=True).order_by("brand", "model_number"),
        })


@da_decorator
class CopierUnitCreateView(View):
    template_name = "dashboard/copier_units/form.html"

    def get(self, request):
        from apps.catalog.models import CopierUnit, Copier
        return render(request, self.template_name, {
            "is_edit":          False,
            "copier_list":      Copier.objects.order_by("brand", "model_number"),
            "status_choices":   CopierUnit.UnitStatus.choices,
            "condition_choices": CopierUnit.Condition.choices,
        })

    def post(self, request):
        from apps.catalog.models import CopierUnit, Copier
        from django.contrib import messages
        try:
            copier = Copier.objects.get(pk=request.POST["copier"])
            CopierUnit.objects.create(
                copier           = copier,
                serial_number    = request.POST["serial_number"].strip(),
                status           = request.POST.get("status", "available"),
                condition        = request.POST.get("condition", "good"),
                acquisition_date = request.POST.get("acquisition_date") or None,
                location_notes   = request.POST.get("location_notes", ""),
                current_meter    = int(request.POST.get("current_meter") or 0),
            )
            messages.success(request, "Unidad registrada correctamente.")
            return redirect("dashboard:copier_units")
        except Exception as e:
            messages.error(request, f"Error: {e}")
            from apps.catalog.models import Copier
            return render(request, self.template_name, {
                "is_edit":           False,
                "copier_list":       Copier.objects.order_by("brand", "model_number"),
                "status_choices":    CopierUnit.UnitStatus.choices,
                "condition_choices": CopierUnit.Condition.choices,
                "error":             str(e),
                "post":              request.POST,
            })


@da_decorator
class CopierUnitEditView(View):
    template_name = "dashboard/copier_units/form.html"

    def _ctx(self, unit):
        from apps.catalog.models import CopierUnit, Copier
        return {
            "is_edit":           True,
            "unit":              unit,
            "copier_list":       Copier.objects.order_by("brand", "model_number"),
            "status_choices":    CopierUnit.UnitStatus.choices,
            "condition_choices": CopierUnit.Condition.choices,
        }

    def get(self, request, pk):
        from apps.catalog.models import CopierUnit
        unit = get_object_or_404(CopierUnit, pk=pk)
        return render(request, self.template_name, self._ctx(unit))

    def post(self, request, pk):
        from apps.catalog.models import CopierUnit, Copier
        from django.contrib import messages
        unit = get_object_or_404(CopierUnit, pk=pk)
        try:
            unit.copier           = Copier.objects.get(pk=request.POST["copier"])
            unit.serial_number    = request.POST["serial_number"].strip()
            unit.status           = request.POST.get("status", unit.status)
            unit.condition        = request.POST.get("condition", unit.condition)
            unit.acquisition_date = request.POST.get("acquisition_date") or None
            unit.location_notes   = request.POST.get("location_notes", "")
            unit.current_meter    = int(request.POST.get("current_meter") or 0)
            unit.save()
            messages.success(request, "Unidad actualizada.")
            return redirect("dashboard:copier_units")
        except Exception as e:
            messages.error(request, f"Error: {e}")
            return render(request, self.template_name, {**self._ctx(unit), "error": str(e)})

# ===========================================================================
# PORTAL DE CAMPO — /campo/  (mensajeros y tecnicos)
# ===========================================================================

def campo_required(view_func):
    from apps.dashboard.models import FieldUser
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/campo/acceso/?next={request.path}")
        if request.user.is_staff:
            return redirect("/dashadmin/")
        try:
            request.user.field_profile
        except FieldUser.DoesNotExist:
            return redirect("/campo/acceso/")
        return view_func(request, *args, **kwargs)
    return wrapper


campo_decorator = method_decorator(campo_required, name="dispatch")


class CampoLoginView(View):
    template_name = "campo/login.html"

    def get(self, request):
        from apps.dashboard.models import FieldUser
        if request.user.is_authenticated:
            try:
                request.user.field_profile
                return redirect("campo:turno")
            except FieldUser.DoesNotExist:
                pass
        return render(request, self.template_name)

    def post(self, request):
        from apps.dashboard.models import FieldUser
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        ip       = _client_ip(request)

        if _is_locked_out(ip, username):
            _auth_logger.warning("Campo login bloqueado para %s desde %s", username, ip)
            return render(request, self.template_name, {
                "error": "Acceso bloqueado temporalmente. Intenta en 15 minutos."
            })

        user = authenticate(request, username=username, password=password)
        if user and user.is_active:
            try:
                user.field_profile
                _clear_failed_logins(ip, username)
                login(request, user)
                _auth_logger.info("Login campo exitoso: %s desde %s", username, ip)
                return redirect(_safe_next(request, "campo:turno"))
            except FieldUser.DoesNotExist:
                pass

        attempts = _record_failed_login(ip, username)
        _auth_logger.warning("Login campo fallido para '%s' desde %s (intento %d)", username, ip, attempts)
        return render(request, self.template_name, {"error": "Credenciales inválidas o sin acceso al portal de campo."})


class CampoLogoutView(View):
    def post(self, request):
        from apps.dashboard.models import FieldUserLocation
        if request.user.is_authenticated:
            try:
                loc = request.user.field_location
                loc.is_on_shift = False
                loc.save(update_fields=["is_on_shift"])
            except FieldUserLocation.DoesNotExist:
                pass
        logout(request)
        return redirect("campo:login")

    def get(self, request):
        # GET no realiza logout (previene CSRF-via-GET). Solo redirige.
        return redirect("campo:login")


@campo_decorator
class CampoTurnoView(View):
    template_name = "campo/turno.html"

    def get(self, request):
        from apps.dashboard.models import FieldUser, FieldUserLocation
        from apps.leads.models import FollowUpTask, ServiceTicket
        field_user = request.user.field_profile
        try:
            loc = request.user.field_location
        except FieldUserLocation.DoesNotExist:
            loc = None

        today = timezone.localdate()
        tasks = FollowUpTask.objects.filter(
            assigned_to=request.user, is_done=False, due_date=today
        ).select_related("lead").order_by("pk")[:20]

        tickets = ServiceTicket.objects.filter(
            assigned_to=request.user,
            status__in=("open", "in_progress", "waiting_parts")
        ).select_related("lead").order_by("priority", "created_at")[:20]

        from apps.dashboard.models import DeliveryTask
        from django.db.models import Case, When, IntegerField, Value
        delivery_tasks = (
            DeliveryTask.objects
            .filter(field_user=field_user)
            .exclude(status="cancelled")
            .annotate(_ord=Case(
                When(status="pending", then=Value(0)),
                When(status="done",    then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            ))
            .order_by("_ord", "order", "created_at")[:30]
        )

        return render(request, self.template_name, {
            "field_user":      field_user,
            "location":        loc,
            "tasks":           tasks,
            "tickets":         tickets,
            "delivery_tasks":  delivery_tasks,
            "today":           today,
        })


@campo_decorator
class CampoTurnoMapView(View):
    """Página dedicada con el mapa de puntos de entrega del mensajero."""
    template_name = "campo/turno_map.html"

    def get(self, request):
        from apps.dashboard.models import DeliveryTask
        from django.db.models import Case, When, IntegerField, Value
        field_user = request.user.field_profile
        delivery_tasks = (
            DeliveryTask.objects
            .filter(field_user=field_user)
            .exclude(status="cancelled")
            .annotate(_ord=Case(
                When(status="pending", then=Value(0)),
                When(status="done",    then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            ))
            .order_by("_ord", "order", "created_at")[:30]
        )
        return render(request, self.template_name, {
            "field_user":     field_user,
            "delivery_tasks": delivery_tasks,
            "back_url":       reverse("campo:turno"),
        })


@panel_decorator
class PanelTurnoMapView(View):
    """Mapa de entregas accesible desde el panel (/panel/turno/mapa/)."""
    template_name = "campo/turno_map.html"

    def get(self, request):
        from apps.dashboard.models import DeliveryTask
        from django.db.models import Case, When, IntegerField, Value
        field_user = request.user.field_profile
        delivery_tasks = (
            DeliveryTask.objects
            .filter(field_user=field_user)
            .exclude(status="cancelled")
            .annotate(_ord=Case(
                When(status="pending", then=Value(0)),
                When(status="done",    then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            ))
            .order_by("_ord", "order", "created_at")[:30]
        )
        return render(request, self.template_name, {
            "field_user":     field_user,
            "delivery_tasks": delivery_tasks,
            "back_url":       reverse("panel:turno"),
        })


@campo_decorator
class CampoUbicacionUpdateView(View):
    LOG_INTERVAL_SECONDS = 120  # guardar punto de ruta cada 2 minutos

    def post(self, request):
        from apps.dashboard.models import FieldUserLocation, FieldLocationLog
        from datetime import timedelta
        try:
            lat  = float(request.POST.get("lat") or request.POST.get("latitude"))
            lng  = float(request.POST.get("lng") or request.POST.get("longitude"))
            acc  = request.POST.get("accuracy")
            bat  = request.POST.get("battery")
            loc, _ = FieldUserLocation.objects.update_or_create(
                user=request.user,
                defaults={
                    "latitude":    lat,
                    "longitude":   lng,
                    "accuracy":    float(acc) if acc else None,
                    "battery":     int(float(bat)) if bat else None,
                    "is_on_shift": True,
                },
            )
            # ── Registro de ruta (throttled) ──
            today  = timezone.localdate()
            cutoff = timezone.now() - timedelta(seconds=self.LOG_INTERVAL_SECONDS)
            if not FieldLocationLog.objects.filter(user=request.user, recorded_at__gte=cutoff).exists():
                FieldLocationLog.objects.create(
                    user=request.user, latitude=lat, longitude=lng, shift_date=today
                )
                # Limpieza automática de puntos con más de 90 días
                FieldLocationLog.objects.filter(
                    user=request.user, shift_date__lt=today - timedelta(days=90)
                ).delete()
            return JsonResponse({"ok": True, "updated_at": loc.updated_at.isoformat()})
        except (TypeError, ValueError) as e:
            return JsonResponse({"ok": False, "error": str(e)}, status=400)


@campo_decorator
class CampoShiftStartView(View):
    def post(self, request):
        from apps.dashboard.models import FieldUserLocation
        FieldUserLocation.objects.update_or_create(
            user=request.user,
            defaults={"is_on_shift": True, "latitude": 0, "longitude": 0},
        )
        return JsonResponse({"ok": True})


@campo_decorator
class CampoShiftEndView(View):
    def post(self, request):
        from apps.dashboard.models import FieldUserLocation
        try:
            loc = request.user.field_location
            loc.is_on_shift = False
            loc.save(update_fields=["is_on_shift"])
        except FieldUserLocation.DoesNotExist:
            pass
        return JsonResponse({"ok": True})


# ---------------------------------------------------------------------------
# Mapa de campo en el dashadmin
# ---------------------------------------------------------------------------

@da_decorator
class CampoMapView(TemplateView):
    template_name = "dashboard/campo/map.html"

    def get_context_data(self, **kwargs):
        from apps.dashboard.models import FieldUser, FieldUserLocation
        ctx = super().get_context_data(**kwargs)
        ctx["field_users"] = FieldUser.objects.select_related("user", "user__field_location").all()
        ctx["on_shift"] = FieldUserLocation.objects.filter(is_on_shift=True).count()
        return ctx


@da_decorator
class CampoLocationsJsonView(View):

    def get(self, request):
        from apps.dashboard.models import FieldUser, FieldUserLocation
        from django.utils.timesince import timesince
        locations = (
            FieldUserLocation.objects
            .filter(is_on_shift=True)
            .select_related("user", "user__field_profile")
        )
        data = []
        for loc in locations:
            fp = getattr(loc.user, "field_profile", None)
            data.append({
                "id":         loc.user.pk,
                "name":       loc.user.get_full_name() or loc.user.username,
                "role":       fp.get_role_display() if fp else "---",
                "role_key":   fp.role if fp else "",
                "lat":        float(loc.latitude),
                "lng":        float(loc.longitude),
                "accuracy":   loc.accuracy,
                "battery":    loc.battery,
                "updated_at": loc.updated_at.isoformat(),
                "ago":        timesince(loc.updated_at),
            })
        return JsonResponse({"locations": data, "count": len(data)})


@da_decorator
class CampoUserListView(TemplateView):
    template_name = "dashboard/campo/users.html"

    def get_context_data(self, **kwargs):
        from apps.dashboard.models import FieldUser
        ctx = super().get_context_data(**kwargs)
        ctx["field_users"] = FieldUser.objects.select_related("user", "user__field_location").order_by("role", "user__first_name")
        return ctx


@da_decorator
class CampoUserCreateView(View):
    template_name = "dashboard/campo/user_form.html"

    def get(self, request):
        from apps.dashboard.models import FieldUser
        from django.contrib.auth import get_user_model
        User = get_user_model()
        existing_ids = FieldUser.objects.values_list("user_id", flat=True)
        available = User.objects.filter(is_active=True, is_staff=False).exclude(pk__in=existing_ids).order_by("first_name")
        return render(request, self.template_name, {
            "available_users": available,
            "role_choices": FieldUser.Role.choices,
        })

    def post(self, request):
        from apps.dashboard.models import FieldUser
        from django.contrib.auth import get_user_model
        from django.contrib import messages
        User = get_user_model()
        try:
            user = User.objects.get(pk=request.POST.get("user_id"))
            FieldUser.objects.create(
                user  = user,
                role  = request.POST.get("role"),
                phone = request.POST.get("phone", "").strip(),
            )
            messages.success(request, f"{user.get_full_name() or user.username} agregado al equipo de campo.")
            return redirect("dashboard:campo_users")
        except Exception as e:
            messages.error(request, f"Error: {e}")
            return redirect("dashboard:campo_user_create")


@da_decorator
class CampoUserDetailView(View):
    template_name = "dashboard/campo/user_form.html"

    def get(self, request, pk):
        from apps.dashboard.models import FieldUser, DeliveryTask
        fu = get_object_or_404(FieldUser, pk=pk)
        tasks = DeliveryTask.objects.filter(field_user=fu).order_by("status", "due_date", "order")[:50]
        return render(request, self.template_name, {
            "field_user": fu,
            "role_choices": FieldUser.Role.choices,
            "assigned_tasks": tasks,
        })

    def post(self, request, pk):
        from apps.dashboard.models import FieldUser
        from django.contrib import messages
        fu = get_object_or_404(FieldUser, pk=pk)
        action = request.POST.get("action")
        if action == "delete":
            fu.delete()
            messages.success(request, "Usuario eliminado del equipo de campo.")
            return redirect("dashboard:campo_users")
        fu.role  = request.POST.get("role", fu.role)
        fu.phone = request.POST.get("phone", fu.phone).strip()
        fu.save()
        messages.success(request, "Datos actualizados.")
        return redirect("dashboard:campo_users")


# ===========================================================================
# TAREAS DE ENTREGA — portal campo (completar) + admin (CRUD)
# ===========================================================================

@campo_decorator
class CampoTaskCompleteView(View):
    """El mensajero/técnico completa una tarea desde /campo/."""

    def post(self, request, pk):
        from apps.dashboard.models import DeliveryTask
        task = get_object_or_404(
            DeliveryTask, pk=pk,
            field_user__user=request.user,
            status=DeliveryTask.Status.PENDING,
        )
        task.completion_notes     = request.POST.get("notes", "").strip()
        task.completion_signature = request.POST.get("signature", "").strip()
        task.completion_photo_b64 = request.POST.get("photo_b64", "").strip()
        task.status               = DeliveryTask.Status.DONE
        task.completed_at         = timezone.now()
        task.save()
        return JsonResponse({"ok": True, "task_id": task.pk})


@da_decorator
class CampoTaskListView(View):
    template_name = "dashboard/campo/task_list.html"

    def get(self, request):
        from apps.dashboard.models import DeliveryTask, FieldUser
        qs = DeliveryTask.objects.select_related(
            "field_user__user", "created_by"
        ).order_by("-due_date", "field_user__user__first_name", "order")

        fu_pk    = request.GET.get("user")
        status   = request.GET.get("status")
        date_str = request.GET.get("date")
        if fu_pk:
            qs = qs.filter(field_user__pk=fu_pk)
        if status:
            qs = qs.filter(status=status)
        if date_str:
            qs = qs.filter(due_date=date_str)

        from apps.leads.models import Lead
        return render(request, self.template_name, {
            "tasks":          qs[:300],
            "field_users":    FieldUser.objects.select_related("user").order_by("user__first_name"),
            "filter_user":    fu_pk,
            "filter_status":  status,
            "filter_date":    date_str,
            "today":          timezone.localdate().isoformat(),
            "status_choices": DeliveryTask.Status.choices,
            "leads":          Lead.objects.values_list("full_name", "company_name").order_by("full_name")[:500],
            "payment_choices": DeliveryTask.PaymentMethod.choices,
        })

    def post(self, request):
        """Crear nueva tarea rápida desde la lista."""
        from apps.dashboard.models import DeliveryTask, FieldUser
        try:
            fu = FieldUser.objects.get(pk=request.POST.get("field_user_id"))
            DeliveryTask.objects.create(
                field_user         = fu,
                title              = request.POST.get("title", "").strip(),
                description        = request.POST.get("description", "").strip(),
                address            = request.POST.get("address", "").strip(),
                order              = int(request.POST.get("order") or 0),
                due_date           = request.POST.get("due_date") or timezone.localdate(),
                created_by         = request.user,
                completion_invoice = request.POST.get("invoice_ref", "").strip(),
                client_name        = request.POST.get("client_name", "").strip(),
                payment_method     = request.POST.get("payment_method", "").strip(),
            )
        except Exception as e:
            from django.contrib import messages as dj_msg
            dj_msg.error(request, f"Error al crear tarea: {e}")
        return redirect("dashboard:campo_tasks")


@da_decorator
class CampoTaskDetailView(View):
    template_name = "dashboard/campo/task_detail.html"

    def get(self, request, pk):
        from apps.dashboard.models import DeliveryTask
        task = get_object_or_404(DeliveryTask, pk=pk)
        return render(request, self.template_name, {"task": task})

    def post(self, request, pk):
        from apps.dashboard.models import DeliveryTask
        task = get_object_or_404(DeliveryTask, pk=pk)
        if request.POST.get("action") == "cancel":
            task.status = DeliveryTask.Status.CANCELLED
            task.save(update_fields=["status"])
        return redirect("dashboard:campo_task_detail", pk=pk)


@da_decorator
class CampoRouteHistoryView(TemplateView):
    template_name = "dashboard/campo/route_history.html"

    def get_context_data(self, **kwargs):
        from apps.dashboard.models import FieldUser, FieldLocationLog
        ctx = super().get_context_data(**kwargs)
        ctx["field_users"]   = FieldUser.objects.select_related("user").order_by("user__first_name")
        user_pk  = self.request.GET.get("user")
        date_str = self.request.GET.get("date", timezone.localdate().isoformat())
        ctx["selected_user"] = user_pk
        ctx["selected_date"] = date_str
        if user_pk:
            ctx["available_dates"] = (
                FieldLocationLog.objects
                .filter(user__pk=user_pk)
                .values_list("shift_date", flat=True)
                .distinct()
                .order_by("-shift_date")[:90]
            )
        return ctx


@da_decorator
class CampoRouteExportView(View):
    """Exporta en CSV el reporte diario de rutas: GPS + entregas de todos los mensajeros."""

    def get(self, request):
        import csv
        from apps.dashboard.models import FieldLocationLog, DeliveryTask, FieldUser

        date_str = request.GET.get("date", timezone.localdate().isoformat())

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="ruta_{date_str}.csv"'
        response.write("﻿")  # BOM para Excel

        writer = csv.writer(response)

        # ── Sección 1: Puntos GPS ──────────────────────────────────────────
        writer.writerow(["PUNTOS GPS"])
        writer.writerow(["Mensajero", "Rol", "Fecha", "Hora", "Latitud", "Longitud"])

        logs = (
            FieldLocationLog.objects
            .filter(shift_date=date_str)
            .select_related("user__field_profile")
            .order_by("user__first_name", "recorded_at")
        )
        for log in logs:
            name = log.user.get_full_name() or log.user.username
            try:
                role = log.user.field_profile.get_role_display()
            except Exception:
                role = ""
            writer.writerow([
                name, role, date_str,
                log.recorded_at.strftime("%H:%M:%S"),
                float(log.latitude), float(log.longitude),
            ])

        writer.writerow([])  # separador

        # ── Sección 2: Entregas completadas ───────────────────────────────
        writer.writerow(["ENTREGAS COMPLETADAS"])
        writer.writerow(["Mensajero", "Rol", "Tarea", "Cliente", "Dirección",
                          "Factura / Remisión", "Método de pago", "Hora completada"])

        tasks = (
            DeliveryTask.objects
            .filter(status="done", completed_at__date=date_str)
            .select_related("field_user__user")
            .order_by("field_user__user__first_name", "completed_at")
        )
        for t in tasks:
            name = t.field_user.user.get_full_name() or t.field_user.user.username
            role = t.field_user.get_role_display()
            writer.writerow([
                name, role, t.title, t.client_name, t.address,
                t.completion_invoice,
                t.get_payment_method_display() if t.payment_method else "",
                t.completed_at.strftime("%H:%M:%S") if t.completed_at else "",
            ])

        return response


@da_decorator
class CampoRouteJsonView(View):
    def get(self, request):
        from apps.dashboard.models import FieldLocationLog, DeliveryTask, FieldUser
        user_pk  = request.GET.get("user")
        date_str = request.GET.get("date")
        if not user_pk or not date_str:
            return JsonResponse({"points": [], "tasks": []})

        points = list(
            FieldLocationLog.objects
            .filter(user__pk=user_pk, shift_date=date_str)
            .values("latitude", "longitude", "recorded_at")
            .order_by("recorded_at")
        )
        try:
            fu = FieldUser.objects.get(user__pk=user_pk)
            tasks_qs = DeliveryTask.objects.filter(
                field_user=fu, status="done", completed_at__date=date_str,
            ).values("pk", "title", "client_name", "address",
                     "completion_invoice", "payment_method", "completed_at")
            tasks = list(tasks_qs)
        except FieldUser.DoesNotExist:
            tasks = []

        return JsonResponse({
            "points": [
                {"lat": float(p["latitude"]), "lng": float(p["longitude"]),
                 "t": p["recorded_at"].strftime("%H:%M")}
                for p in points
            ],
            "tasks": [
                {"pk": t["pk"], "title": t["title"], "client": t["client_name"],
                 "address": t["address"], "invoice": t["completion_invoice"],
                 "payment": t["payment_method"],
                 "time": t["completed_at"].strftime("%H:%M") if t["completed_at"] else ""}
                for t in tasks
            ],
        })


# ---------------------------------------------------------------------------
# Gestión de tickets en el portal de campo — solo técnicos de campo
# ---------------------------------------------------------------------------

def campo_tecnico_required(view_func):
    """Acceso restringido a FieldUser con role='tecnico'."""
    from apps.dashboard.models import FieldUser
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/campo/acceso/?next={request.path}")
        if request.user.is_staff:
            return redirect("/dashadmin/")
        try:
            fp = request.user.field_profile
            if fp.role != FieldUser.Role.TECNICO:
                return redirect("campo:turno")
        except FieldUser.DoesNotExist:
            return redirect("/campo/acceso/")
        return view_func(request, *args, **kwargs)
    return wrapper


tecnico_campo_decorator = method_decorator(campo_tecnico_required, name="dispatch")


@tecnico_campo_decorator
class CampoTicketDetailView(View):
    """Detalle y gestión de un ticket desde el portal de campo (técnicos)."""
    template_name = "campo/ticket_detail.html"

    def get(self, request, pk):
        from apps.leads.models import ServiceTicket
        ticket = get_object_or_404(
            ServiceTicket.objects.select_related("lead", "contract"),
            pk=pk, assigned_to=request.user,
        )
        return render(request, self.template_name, {"ticket": ticket})

    def post(self, request, pk):
        from apps.leads.models import ServiceTicket
        ticket = get_object_or_404(ServiceTicket, pk=pk, assigned_to=request.user)

        new_status = request.POST.get("status", "").strip()
        notes      = request.POST.get("resolution_notes", "").strip()

        valid_transitions = {
            "open":          ["in_progress", "waiting_parts"],
            "in_progress":   ["waiting_parts", "resolved"],
            "waiting_parts": ["in_progress", "resolved"],
        }
        allowed = valid_transitions.get(ticket.status, [])

        if new_status and new_status in allowed:
            ticket.status = new_status
            if new_status == "resolved":
                ticket.resolved_at = timezone.now()

        if notes:
            ticket.resolution_notes = notes

        ticket.save(update_fields=["status", "resolution_notes", "resolved_at"])
        return redirect("campo:ticket_detail", pk=pk)


# ===========================================================================
# TURNO Y GPS DESDE EL /panel/ (técnicos y mensajeros)
# ===========================================================================

@panel_decorator
class PanelTurnoView(View):
    """Dashboard de turno para usuarios con FieldUser (mensajeros y técnicos)."""
    template_name = "panel/turno.html"

    def get(self, request):
        from apps.dashboard.models import FieldUser, FieldUserLocation
        from apps.leads.models import FollowUpTask, ServiceTicket
        try:
            field_user = request.user.field_profile
        except FieldUser.DoesNotExist:
            return redirect("panel:home")

        try:
            loc = request.user.field_location
        except FieldUserLocation.DoesNotExist:
            loc = None

        today = timezone.localdate()
        tasks = FollowUpTask.objects.filter(
            assigned_to=request.user, is_done=False, due_date=today
        ).select_related("lead").order_by("pk")[:20]

        tickets = ServiceTicket.objects.filter(
            assigned_to=request.user,
            status__in=("open", "in_progress", "waiting_parts")
        ).select_related("lead").order_by("priority", "created_at")[:20]

        from apps.dashboard.models import DeliveryTask
        from django.db.models import Case, When, IntegerField, Value
        delivery_tasks = (
            DeliveryTask.objects
            .filter(field_user=field_user)
            .exclude(status="cancelled")
            .annotate(_ord=Case(
                When(status="pending", then=Value(0)),
                When(status="done",    then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            ))
            .order_by("_ord", "order", "created_at")[:30]
        )

        ctx = _panel_base_ctx(request)
        ctx.update({
            "field_user":     field_user,
            "location":       loc,
            "tasks":          tasks,
            "tickets":        tickets,
            "delivery_tasks": delivery_tasks,
            "today":          today,
        })
        return render(request, self.template_name, ctx)


@panel_decorator
class PanelDeliveryCompleteView(View):
    """Completar una tarea de entrega desde el portal del panel/mensajero."""
    def post(self, request, pk):
        from apps.dashboard.models import DeliveryTask, FieldUser
        try:
            fu = request.user.field_profile
        except FieldUser.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Sin perfil de campo"}, status=403)
        task = get_object_or_404(DeliveryTask, pk=pk, field_user=fu, status=DeliveryTask.Status.PENDING)
        task.completion_notes     = request.POST.get("notes", "").strip()
        task.completion_signature = request.POST.get("signature", "").strip()
        task.completion_photo_b64 = request.POST.get("photo_b64", "").strip()
        task.status               = DeliveryTask.Status.DONE
        task.completed_at         = timezone.now()
        task.save()
        return JsonResponse({"ok": True, "task_id": task.pk})


@panel_decorator
class PanelShiftStartView(View):
    def post(self, request):
        from apps.dashboard.models import FieldUserLocation
        try:
            request.user.field_profile
        except Exception:
            return redirect("panel:turno")
        FieldUserLocation.objects.update_or_create(
            user=request.user,
            defaults={"is_on_shift": True, "latitude": 0, "longitude": 0},
        )
        return redirect("panel:turno")

    def get(self, request):
        return redirect("panel:turno")


@panel_decorator
class PanelShiftEndView(View):
    def post(self, request):
        from apps.dashboard.models import FieldUserLocation
        try:
            loc = request.user.field_location
            loc.is_on_shift = False
            loc.save(update_fields=["is_on_shift"])
        except FieldUserLocation.DoesNotExist:
            pass
        return redirect("panel:turno")

    def get(self, request):
        return redirect("panel:turno")


@panel_decorator
class PanelUbicacionView(View):
    def post(self, request):
        from apps.dashboard.models import FieldUserLocation
        try:
            lat = float(request.POST.get("lat") or request.POST.get("latitude"))
            lng = float(request.POST.get("lng") or request.POST.get("longitude"))
            acc = request.POST.get("accuracy")
            bat = request.POST.get("battery")
            loc, _ = FieldUserLocation.objects.update_or_create(
                user=request.user,
                defaults={
                    "latitude":    lat,
                    "longitude":   lng,
                    "accuracy":    float(acc) if acc else None,
                    "battery":     int(float(bat)) if bat else None,
                    "is_on_shift": True,
                },
            )
            return JsonResponse({"ok": True, "updated_at": loc.updated_at.isoformat()})
        except (TypeError, ValueError) as e:
            return JsonResponse({"ok": False, "error": str(e)}, status=400)

