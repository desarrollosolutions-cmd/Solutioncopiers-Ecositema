"""
Vistas del módulo de pagos.

Flujo público:
  /pago/<slug>/           — checkout de un solo consumible
  /pago/carrito/          — checkout del carrito (sesión)
  /pago/confirmacion/<ref>/ — página de resultado post-redirect
  /pago/webhook/wompi/    — endpoint webhook de Wompi

Flujo CRM (prefijo /dashadmin/facturacion/):
  facturas/               — lista de facturas
  facturas/nueva/         — crear factura manual
  facturas/<pk>/          — detalle y edición
  ar/                     — dashboard cuentas por cobrar
  pedidos/                — lista de pedidos online
  pedidos/<ref>/          — detalle pedido
"""
from __future__ import annotations

import json
import logging
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, ListView

from apps.catalog.models import Consumable
from apps.leads.models import Lead

from .models import Invoice, InvoiceItem, Order, OrderItem, Payment
from .services import build_checkout_url, fetch_transaction_by_reference, verify_webhook_signature

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers de sesión (carrito)
# ---------------------------------------------------------------------------

CART_SESSION_KEY = "sc_cart"


def _get_cart(request) -> dict:
    return request.session.get(CART_SESSION_KEY, {})


def _save_cart(request, cart: dict):
    request.session[CART_SESSION_KEY] = cart
    request.session.modified = True


# ---------------------------------------------------------------------------
# Vistas públicas
# ---------------------------------------------------------------------------

class CartAddView(View):
    """POST /pago/carrito/agregar/ — añade o actualiza un ítem al carrito."""

    def post(self, request):
        consumable_id = request.POST.get("consumable_id") or request.POST.get("id")
        quantity      = max(1, int(request.POST.get("quantity", 1)))

        try:
            consumable = Consumable.published.get(pk=consumable_id)
        except (Consumable.DoesNotExist, ValueError, TypeError):
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"ok": False, "error": "Producto no encontrado"}, status=404)
            messages.error(request, "Producto no encontrado.")
            return redirect("catalog:consumables_list")

        unit_price = consumable.price or Decimal("0")
        cart       = _get_cart(request)
        key        = str(consumable.pk)

        if key in cart:
            cart[key]["quantity"] += quantity
        else:
            cart[key] = {
                "consumable_id": consumable.pk,
                "name":          consumable.name,
                "part_number":   consumable.part_number,
                "unit_price":    str(unit_price),
                "image_url":     consumable.main_image.url if consumable.main_image else "",
            }
            cart[key]["quantity"] = quantity

        _save_cart(request, cart)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            total_items = sum(v["quantity"] for v in cart.values())
            return JsonResponse({"ok": True, "cart_count": total_items})

        messages.success(request, f'"{consumable.name}" agregado al carrito.')
        return redirect("payments:cart")


class CartUpdateView(View):
    """POST /pago/carrito/actualizar/ — actualiza cantidad o elimina."""

    def post(self, request):
        consumable_id = request.POST.get("consumable_id")
        quantity      = int(request.POST.get("quantity", 0))
        cart          = _get_cart(request)
        key           = str(consumable_id)

        if quantity <= 0:
            cart.pop(key, None)
        elif key in cart:
            cart[key]["quantity"] = quantity

        _save_cart(request, cart)
        return redirect("payments:cart")


class CartView(View):
    """GET /pago/carrito/ — muestra el carrito."""

    template_name = "payments/cart.html"

    def get(self, request):
        cart  = _get_cart(request)
        items = _enrich_cart(cart)
        subtotal = sum(i["line_total"] for i in items)
        iva      = (subtotal * Decimal("0.19")).quantize(Decimal("0.01"))
        total    = subtotal + iva
        return render(request, self.template_name, {
            "cart_items": items,
            "subtotal":   subtotal,
            "iva":        iva,
            "total":      total,
        })


def _enrich_cart(cart: dict) -> list:
    """Devuelve lista de ítems del carrito con línea de total calculada."""
    items = []
    for key, data in cart.items():
        unit_price = Decimal(data["unit_price"])
        qty        = data["quantity"]
        items.append({
            **data,
            "unit_price": unit_price,
            "line_total": (unit_price * qty).quantize(Decimal("0.01")),
        })
    return items


class CheckoutView(View):
    """
    GET  /pago/checkout/ — formulario de datos del comprador
    POST /pago/checkout/ — crea Order y redirige a Wompi
    """
    template_name = "payments/checkout.html"

    def get(self, request):
        cart  = _get_cart(request)
        items = _enrich_cart(cart)
        if not items:
            messages.warning(request, "Tu carrito está vacío.")
            return redirect("catalog:consumables_list")

        subtotal = sum(i["line_total"] for i in items)
        iva      = (subtotal * Decimal("0.19")).quantize(Decimal("0.01"))
        total    = subtotal + iva
        return render(request, self.template_name, {
            "cart_items": items,
            "subtotal":   subtotal,
            "iva":        iva,
            "total":      total,
        })

    def post(self, request):
        cart  = _get_cart(request)
        items = _enrich_cart(cart)
        if not items:
            return redirect("catalog:consumables_list")

        # -- Crear Order --
        order = Order(
            buyer_name    = request.POST.get("buyer_name", "").strip(),
            buyer_email   = request.POST.get("buyer_email", "").strip(),
            buyer_phone   = request.POST.get("buyer_phone", "").strip(),
            buyer_nit     = request.POST.get("buyer_nit", "").strip(),
            buyer_company = request.POST.get("buyer_company", "").strip(),
            buyer_city    = request.POST.get("buyer_city", "Medellín").strip(),
            buyer_address = request.POST.get("buyer_address", "").strip(),
            notes         = request.POST.get("notes", "").strip(),
        )
        order.save()

        # -- OrderItems --
        for item in items:
            try:
                consumable = Consumable.published.get(pk=item["consumable_id"])
            except Consumable.DoesNotExist:
                continue
            OrderItem.objects.create(
                order        = order,
                consumable   = consumable,
                quantity     = item["quantity"],
                unit_price   = item["unit_price"],
                product_name = item["name"],
                part_number  = item["part_number"],
            )

        order.recalculate_totals()
        order.save(update_fields=["subtotal", "tax_amount", "total"])

        # -- Vincular Lead si existe por email --
        email = order.buyer_email
        if email:
            lead = Lead.objects.filter(email=email).first()
            if lead:
                order.lead = lead
            else:
                lead = Lead.objects.create(
                    full_name    = order.buyer_name,
                    email        = email,
                    phone        = order.buyer_phone,
                    nit          = order.buyer_nit,
                    company_name = order.buyer_company,
                    city         = order.buyer_city,
                    source       = Lead.Source.CONTACT_FORM,
                    notes_internal = f"Pedido online {order.reference}",
                )
                order.lead = lead
            order.save(update_fields=["lead"])

        # -- Crear Payment pendiente --
        payment = Payment.objects.create(
            order          = order,
            reference      = order.reference,
            amount_in_cents = order.amount_in_cents,
            currency       = "COP",
        )

        # -- Construir URL de Wompi --
        redirect_url = request.build_absolute_uri(
            f"/pago/confirmacion/{order.reference}/"
        )
        checkout_url = build_checkout_url(
            reference             = order.reference,
            amount_in_cents       = order.amount_in_cents,
            redirect_url          = redirect_url,
            customer_email        = order.buyer_email,
            customer_full_name    = order.buyer_name,
            customer_phone_number = order.buyer_phone,
            customer_legal_id     = order.buyer_nit or "",
        )

        # Limpiar carrito
        _save_cart(request, {})

        return redirect(checkout_url)


class OrderConfirmationView(View):
    """
    GET /pago/confirmacion/<reference>/
    Wompi redirige aquí con ?id=<transaction_id> tras el pago.
    Consultamos el estado y actualizamos Order + Payment.
    """
    template_name = "payments/confirmation.html"

    def get(self, request, reference: str):
        order = get_object_or_404(Order, reference=reference)

        # Intentar refrescar estado desde Wompi si aún está pendiente
        if order.status == Order.Status.PENDING:
            wompi_id = request.GET.get("id", "")
            if wompi_id:
                self._sync_from_wompi(order, wompi_id)

        return render(request, self.template_name, {"order": order})

    @staticmethod
    def _sync_from_wompi(order: Order, wompi_id: str):
        """Consulta la API de Wompi y actualiza el estado del pedido."""
        try:
            txn = fetch_transaction_by_reference(order.reference)
            if not txn:
                return
            status_map = {
                "APPROVED": (Order.Status.PAID,     Payment.Status.APPROVED),
                "DECLINED": (Order.Status.FAILED,   Payment.Status.DECLINED),
                "VOIDED":   (Order.Status.CANCELLED, Payment.Status.VOIDED),
                "ERROR":    (Order.Status.FAILED,   Payment.Status.ERROR),
            }
            wompi_status = txn.get("status", "PENDING")
            order_status, pay_status = status_map.get(wompi_status, (Order.Status.PENDING, Payment.Status.PENDING))

            order.status = order_status
            order.save(update_fields=["status"])

            Payment.objects.filter(reference=order.reference).update(
                wompi_id           = txn.get("id", wompi_id),
                status             = pay_status,
                payment_method_type = txn.get("payment_method_type", ""),
                finalized_at       = timezone.now(),
                raw_payload        = txn,
            )
        except Exception as exc:
            logger.error("Error syncing Wompi status for %s: %s", order.reference, exc)


# ---------------------------------------------------------------------------
# Webhook de Wompi
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name="dispatch")
class WompiWebhookView(View):
    """
    POST /pago/webhook/wompi/
    Wompi envía eventos de transacción aquí.
    """

    def post(self, request):
        try:
            payload_bytes = request.body
            data          = json.loads(payload_bytes)
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Wompi webhook: invalid JSON — %s", exc)
            return HttpResponse(status=400)

        # Verificar firma
        sig        = data.get("signature", {})
        checksum   = sig.get("checksum", "")
        properties = sig.get("properties", [])
        event_data = data.get("data", {})

        if not verify_webhook_signature(payload_bytes, checksum, properties, event_data):
            logger.warning("Wompi webhook: signature verification failed.")
            return HttpResponse(status=401)

        event = data.get("event", "")
        if event == "transaction.updated":
            self._handle_transaction(data)

        return HttpResponse(status=200)

    @staticmethod
    def _handle_transaction(data: dict):
        txn = data.get("data", {}).get("transaction", {})
        if not txn:
            return

        reference    = txn.get("reference", "")
        wompi_status = txn.get("status", "")
        wompi_id     = txn.get("id", "")

        # Actualizar Payment
        Payment.objects.filter(reference=reference).update(
            wompi_id            = wompi_id,
            status              = wompi_status,
            payment_method_type = txn.get("payment_method_type", ""),
            finalized_at        = timezone.now(),
            webhook_received_at = timezone.now(),
            raw_payload         = txn,
        )

        # Actualizar Order
        order_status_map = {
            "APPROVED": Order.Status.PAID,
            "DECLINED": Order.Status.FAILED,
            "VOIDED":   Order.Status.CANCELLED,
            "ERROR":    Order.Status.FAILED,
        }
        new_status = order_status_map.get(wompi_status)
        if new_status:
            updated = Order.objects.filter(reference=reference, status=Order.Status.PENDING).update(
                status=new_status
            )
            if updated and new_status == Order.Status.PAID:
                # Generar factura automática si el pedido fue aprobado
                try:
                    order = Order.objects.select_related("lead").get(reference=reference)
                    _auto_generate_invoice(order)
                except Order.DoesNotExist:
                    pass


def _auto_generate_invoice(order: Order):
    """Crea borrador de factura automáticamente al confirmar el pago."""
    if hasattr(order, "invoice") and order.invoice:
        return  # Ya tiene factura

    from django.db import transaction as db_transaction

    with db_transaction.atomic():
        company_settings = _get_company_settings()
        invoice = Invoice.objects.create(
            order           = order,
            lead            = order.lead,
            status          = Invoice.Status.ISSUED,
            issue_date      = timezone.localdate(),
            due_date        = timezone.localdate(),  # pago inmediato
            paid_date       = timezone.localdate(),
            client_name     = order.buyer_name,
            client_nit      = order.buyer_nit,
            client_email    = order.buyer_email,
            client_phone    = order.buyer_phone,
            client_address  = order.buyer_address,
            client_city     = order.buyer_city,
            payment_method  = Invoice.PaymentMethod.WOMPI,
            issuer_name     = company_settings.get("name", "Solution Copiers"),
            issuer_nit      = company_settings.get("nit", ""),
            issuer_address  = company_settings.get("address", ""),
            issuer_email    = company_settings.get("email", ""),
            issuer_phone    = company_settings.get("phone", ""),
        )
        for item in order.items.all():
            InvoiceItem.objects.create(
                invoice    = invoice,
                description = item.product_name,
                quantity   = item.quantity,
                unit_price = item.unit_price,
                consumable = item.consumable,
            )
        invoice.recalculate_totals()
        invoice.save(update_fields=["subtotal", "tax_base", "tax_amount", "total"])


def _get_company_settings() -> dict:
    """Lee configuración de empresa desde SiteSettings (apps.core) si existe."""
    try:
        from apps.core.models import SiteSettings
        s = SiteSettings.objects.first()
        if s:
            return {
                "name":    getattr(s, "company_name", "Solution Copiers"),
                "nit":     getattr(s, "nit", ""),
                "address": getattr(s, "address", ""),
                "email":   getattr(s, "email", ""),
                "phone":   getattr(s, "phone", ""),
            }
    except Exception:
        pass
    return {"name": "Solution Copiers"}


# ---------------------------------------------------------------------------
# Vistas CRM — Facturas
# ---------------------------------------------------------------------------

class CRMLoginMixin(LoginRequiredMixin):
    """Solo staff puede acceder a vistas de facturación/CRM."""
    login_url = "/dashadmin/acceso/"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_staff:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("Acceso restringido al personal autorizado.")
        return super().dispatch(request, *args, **kwargs)


class InvoiceListView(CRMLoginMixin, ListView):
    model               = Invoice
    template_name       = "dashboard/payments/invoice_list.html"
    context_object_name = "invoices"
    paginate_by         = 25

    def get_queryset(self):
        qs = Invoice.objects.select_related("lead").order_by("-issue_date", "-pk")
        status = self.request.GET.get("estado")
        q      = self.request.GET.get("q", "").strip()
        if status:
            qs = qs.filter(status=status)
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(client_name__icontains=q) |
                Q(client_nit__icontains=q) |
                Q(dian_consecutive__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = Invoice.Status.choices
        ctx["estado_actual"]  = self.request.GET.get("estado", "")
        ctx["q_actual"]       = self.request.GET.get("q", "")
        # Totales para el encabezado
        from django.db.models import Sum
        ctx["total_issued"]  = Invoice.objects.filter(status__in=["issued", "sent"]).aggregate(s=Sum("total"))["s"] or 0
        ctx["total_overdue"] = Invoice.objects.filter(status="overdue").aggregate(s=Sum("total"))["s"] or 0
        ctx["total_paid"]    = Invoice.objects.filter(status="paid").aggregate(s=Sum("total"))["s"] or 0
        return ctx


class InvoiceCreateView(CRMLoginMixin, View):
    """GET/POST /dashadmin/facturacion/facturas/nueva/"""

    template_name = "dashboard/payments/invoice_form.html"

    def get(self, request):
        leads = Lead.objects.order_by("full_name")[:200]
        return render(request, self.template_name, {
            "leads":           leads,
            "payment_methods": Invoice.PaymentMethod.choices,
            "action":          "Crear",
        })

    def post(self, request):
        try:
            invoice = self._create_from_post(request)
            messages.success(request, f"Factura {invoice.invoice_number} creada exitosamente.")
            return redirect("dashboard:invoice_detail", pk=invoice.pk)
        except Exception as exc:
            messages.error(request, f"Error al crear la factura: {exc}")
            return redirect("dashboard:invoice_create")

    @staticmethod
    def _create_from_post(request) -> Invoice:
        from django.db import transaction as db_transaction
        post = request.POST

        with db_transaction.atomic():
            invoice = Invoice(
                client_name     = post.get("client_name", "").strip(),
                client_nit      = post.get("client_nit", "").strip(),
                client_email    = post.get("client_email", "").strip(),
                client_phone    = post.get("client_phone", "").strip(),
                client_address  = post.get("client_address", "").strip(),
                client_city     = post.get("client_city", "").strip(),
                payment_method  = post.get("payment_method", "42"),
                notes           = post.get("notes", "").strip(),
                status          = Invoice.Status.DRAFT,
                created_by      = request.user,
            )
            # Vincular lead si se pasó
            lead_pk = post.get("lead_id")
            if lead_pk:
                try:
                    invoice.lead = Lead.objects.get(pk=lead_pk)
                    if not invoice.client_name:
                        invoice.client_name = invoice.lead.full_name
                    if not invoice.client_nit:
                        invoice.client_nit = invoice.lead.nit
                    if not invoice.client_email:
                        invoice.client_email = invoice.lead.email
                except Lead.DoesNotExist:
                    pass

            invoice.save()

            # Líneas
            descriptions = post.getlist("item_description")
            quantities   = post.getlist("item_quantity")
            prices       = post.getlist("item_price")
            for desc, qty, price in zip(descriptions, quantities, prices):
                desc = desc.strip()
                if not desc:
                    continue
                InvoiceItem.objects.create(
                    invoice    = invoice,
                    description = desc,
                    quantity   = Decimal(qty or "1"),
                    unit_price = Decimal(price or "0"),
                )

            invoice.recalculate_totals()
            invoice.save(update_fields=["subtotal", "tax_base", "tax_amount", "total"])

        return invoice


class InvoiceDetailView(CRMLoginMixin, DetailView):
    model               = Invoice
    template_name       = "dashboard/payments/invoice_detail.html"
    context_object_name = "invoice"

    def get_queryset(self):
        return Invoice.objects.prefetch_related("items").select_related("lead", "order")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["payments"] = self.object.payments.all()
        return ctx


class InvoiceStatusUpdateView(CRMLoginMixin, View):
    """POST /dashadmin/facturacion/facturas/<pk>/estado/"""

    def post(self, request, pk: int):
        invoice    = get_object_or_404(Invoice, pk=pk)
        new_status = request.POST.get("status")
        if new_status in dict(Invoice.Status.choices):
            invoice.status = new_status
            if new_status == Invoice.Status.PAID and not invoice.paid_date:
                invoice.paid_date = timezone.localdate()
            invoice.save(update_fields=["status", "paid_date"])
            messages.success(request, "Estado de factura actualizado.")
        return redirect("dashboard:invoice_detail", pk=pk)


# ---------------------------------------------------------------------------
# Vistas CRM — Pedidos online
# ---------------------------------------------------------------------------

class OrderListView(CRMLoginMixin, ListView):
    model               = Order
    template_name       = "dashboard/payments/order_list.html"
    context_object_name = "orders"
    paginate_by         = 25

    def get_queryset(self):
        qs = Order.objects.select_related("lead").prefetch_related("items").order_by("-created_at")
        status = self.request.GET.get("estado")
        q      = self.request.GET.get("q", "").strip()
        if status:
            qs = qs.filter(status=status)
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(buyer_name__icontains=q) |
                Q(buyer_email__icontains=q) |
                Q(reference__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = Order.Status.choices
        ctx["estado_actual"]  = self.request.GET.get("estado", "")
        ctx["q_actual"]       = self.request.GET.get("q", "")
        return ctx


class OrderDetailView(CRMLoginMixin, DetailView):
    model               = Order
    template_name       = "dashboard/payments/order_detail.html"
    context_object_name = "order"

    def get_queryset(self):
        return Order.objects.prefetch_related("items").select_related("lead")

    def get_object(self, queryset=None):
        return get_object_or_404(
            self.get_queryset(),
            reference=self.kwargs.get("reference")
        )


# ---------------------------------------------------------------------------
# Vistas CRM — AR Dashboard (Cuentas por Cobrar)
# ---------------------------------------------------------------------------

class ARDashboardView(CRMLoginMixin, View):
    template_name = "dashboard/payments/ar_dashboard.html"

    def get(self, request):
        from django.db.models import Count, Q, Sum
        from django.utils.timezone import now

        today  = timezone.localdate()
        month_start = today.replace(day=1)

        # Resumen facturas
        invoices_qs = Invoice.objects.all()

        summary = {
            "draft":   invoices_qs.filter(status="draft").aggregate(n=Count("pk"), s=Sum("total")),
            "issued":  invoices_qs.filter(status__in=["issued", "sent"]).aggregate(n=Count("pk"), s=Sum("total")),
            "paid":    invoices_qs.filter(status="paid").aggregate(n=Count("pk"), s=Sum("total")),
            "overdue": invoices_qs.filter(status="overdue").aggregate(n=Count("pk"), s=Sum("total")),
            "voided":  invoices_qs.filter(status="voided").aggregate(n=Count("pk"), s=Sum("total")),
        }

        # Facturas vencidas (por fecha, no por status aún)
        auto_overdue = Invoice.objects.filter(
            status__in=["issued", "sent"],
            due_date__lt=today,
        ).select_related("lead")

        # Pedidos del mes
        orders_month = Order.objects.filter(
            created_at__date__gte=month_start,
            status=Order.Status.PAID,
        ).aggregate(n=Count("pk"), s=Sum("total"))

        # Últimas facturas emitidas
        recent_invoices = Invoice.objects.filter(
            status__in=["issued", "sent", "paid"]
        ).select_related("lead").order_by("-issue_date")[:10]

        # Ingresos por mes (últimos 6 meses)
        from django.db.models.functions import TruncMonth
        monthly_revenue = (
            Invoice.objects
            .filter(status="paid")
            .annotate(month=TruncMonth("paid_date"))
            .values("month")
            .annotate(total=Sum("total"))
            .order_by("month")
        )

        return render(request, self.template_name, {
            "summary":        summary,
            "auto_overdue":   auto_overdue,
            "orders_month":   orders_month,
            "recent_invoices": recent_invoices,
            "monthly_revenue": list(monthly_revenue),
        })


# ---------------------------------------------------------------------------
# CONTABILIDAD COLOMBIA
# ---------------------------------------------------------------------------

# Bimestres DIAN: (inicio_mes, fin_mes) — Ene-Feb, Mar-Abr, May-Jun, Jul-Ago, Sep-Oct, Nov-Dic
BIMESTRES = [
    (1, 2, "Ene–Feb"),
    (3, 4, "Mar–Abr"),
    (5, 6, "May–Jun"),
    (7, 8, "Jul–Ago"),
    (9, 10, "Sep–Oct"),
    (11, 12, "Nov–Dic"),
]


def _get_periodo(request):
    """Retorna (year, mes_inicio, mes_fin, label) según ?year= y ?bimestre= GET params."""
    import calendar
    today = timezone.localdate()
    year = int(request.GET.get("year", today.year))
    bim  = int(request.GET.get("bimestre", 0))  # 0=año completo, 1-6=bimestre
    if bim and 1 <= bim <= 6:
        m_ini, m_fin, label = BIMESTRES[bim - 1]
        return year, m_ini, m_fin, f"{label} {year}"
    # Año completo
    return year, 1, 12, f"Año {year}"


class ContabilidadView(CRMLoginMixin, View):
    """
    Dashboard principal de contabilidad colombiana.
    Muestra: ingresos, IVA recaudado, retenciones sufridas, neto recibido,
    pedidos del carrito, y resumen de Estado de Resultados.
    """
    template_name = "dashboard/payments/contabilidad.html"

    def get(self, request):
        from django.db.models import Count, Q, Sum
        import calendar

        year, m_ini, m_fin, periodo_label = _get_periodo(request)
        today = timezone.localdate()

        date_from = timezone.datetime(year, m_ini, 1).date()
        last_day  = calendar.monthrange(year, m_fin)[1]
        date_to   = timezone.datetime(year, m_fin, last_day).date()

        # ── Facturas emitidas en el período ──────────────────────────────
        facturas_qs = Invoice.objects.filter(
            issue_date__range=(date_from, date_to),
        ).exclude(status=Invoice.Status.VOIDED)

        agg = facturas_qs.aggregate(
            n_facturas      = Count("pk"),
            subtotal        = Sum("subtotal"),
            iva_generado    = Sum("tax_amount"),
            total_facturado = Sum("total"),
            rte_fuente      = Sum("retention_fuente"),
            rte_ica         = Sum("retention_ica"),
            rte_iva         = Sum("retention_iva"),
            neto_recibido   = Sum("net_received"),
        )

        # ── Pedidos del carrito pagados en el período ─────────────────────
        orders_qs = Order.objects.filter(
            created_at__date__range=(date_from, date_to),
            status=Order.Status.PAID,
        )
        orders_agg = orders_qs.aggregate(
            n_pedidos      = Count("pk"),
            ventas_online  = Sum("total"),
            iva_online     = Sum("tax_amount"),
        )

        # ── IVA a declarar bimestral ──────────────────────────────────────
        iva_generado   = agg["iva_generado"]   or Decimal("0")
        rte_iva_sufrid = agg["rte_iva"]        or Decimal("0")
        # IVA descontable requiere llevar compras — ponemos 0 (campo para completar)
        iva_declarar   = (iva_generado - rte_iva_sufrid).quantize(Decimal("0.01"))

        # ── Retenciones totales sufridas ──────────────────────────────────
        total_rte = (
            (agg["rte_fuente"] or Decimal("0")) +
            (agg["rte_ica"]    or Decimal("0")) +
            (agg["rte_iva"]    or Decimal("0"))
        ).quantize(Decimal("0.01"))

        # ── Ingresos por mes (para gráfico) ──────────────────────────────
        from django.db.models.functions import TruncMonth
        ingresos_mes = list(
            Invoice.objects.filter(
                issue_date__year=year,
            ).exclude(status=Invoice.Status.VOIDED)
            .annotate(mes=TruncMonth("issue_date"))
            .values("mes")
            .annotate(
                total=Sum("total"),
                iva=Sum("tax_amount"),
                neto=Sum("net_received"),
            )
            .order_by("mes")
        )

        # ── Pedidos recientes (carrito) ────────────────────────────────────
        pedidos_recientes = Order.objects.filter(
            status=Order.Status.PAID
        ).prefetch_related("items").order_by("-created_at")[:10]

        # ── Años disponibles para filtro ─────────────────────────────────
        años = list(range(today.year - 2, today.year + 1))

        return render(request, self.template_name, {
            "periodo_label":   periodo_label,
            "year":            year,
            "bimestre":        int(request.GET.get("bimestre", 0)),
            "bimestres":       [(i+1, lbl) for i, (_, _, lbl) in enumerate(BIMESTRES)],
            "años":            años,
            "agg":             agg,
            "orders_agg":      orders_agg,
            "iva_declarar":    iva_declarar,
            "total_rte":       total_rte,
            "ingresos_mes":    ingresos_mes,
            "pedidos_recientes": pedidos_recientes,
            "date_from":       date_from,
            "date_to":         date_to,
        })


class LibroVentasView(CRMLoginMixin, View):
    """
    Libro auxiliar de ventas (requerido por DIAN).
    Lista todas las facturas con NIT, base, IVA, retenciones, neto.
    Exportable a CSV.
    """
    template_name = "dashboard/payments/libro_ventas.html"

    def get(self, request):
        import calendar

        year, m_ini, m_fin, periodo_label = _get_periodo(request)
        date_from = timezone.datetime(year, m_ini, 1).date()
        last_day  = calendar.monthrange(year, m_fin)[1]
        date_to   = timezone.datetime(year, m_fin, last_day).date()

        qs = Invoice.objects.filter(
            issue_date__range=(date_from, date_to),
        ).exclude(status=Invoice.Status.VOIDED).order_by("issue_date", "dian_consecutive")

        today = timezone.localdate()
        años  = list(range(today.year - 2, today.year + 1))

        # Exportar CSV
        if request.GET.get("export") == "csv":
            return self._export_csv(qs, periodo_label)

        from django.db.models import Sum
        totales = qs.aggregate(
            sub=Sum("subtotal"), iva=Sum("tax_amount"), total=Sum("total"),
            rte_f=Sum("retention_fuente"), rte_i=Sum("retention_ica"),
            rte_v=Sum("retention_iva"), neto=Sum("net_received"),
        )

        return render(request, self.template_name, {
            "facturas":       qs,
            "periodo_label":  periodo_label,
            "year":           year,
            "bimestre":       int(request.GET.get("bimestre", 0)),
            "bimestres":      [(i+1, lbl) for i, (_, _, lbl) in enumerate(BIMESTRES)],
            "años":           años,
            "totales":        totales,
            "date_from":      date_from,
            "date_to":        date_to,
        })

    @staticmethod
    def _export_csv(qs, label: str):
        import csv
        from django.http import HttpResponse as HR
        resp = HR(content_type="text/csv; charset=utf-8-sig")
        resp["Content-Disposition"] = f'attachment; filename="libro_ventas_{label}.csv"'
        w = csv.writer(resp)
        w.writerow([
            "Nro. Factura", "Fecha", "NIT/Cédula cliente", "Cliente",
            "Subtotal", "IVA (19%)", "Total facturado",
            "RteFuente", "RteICA", "RteIVA", "Neto recibido",
            "Estado", "Método pago",
        ])
        for inv in qs:
            w.writerow([
                inv.invoice_number, inv.issue_date, inv.client_nit,
                inv.client_name, inv.subtotal, inv.tax_amount, inv.total,
                inv.retention_fuente, inv.retention_ica, inv.retention_iva,
                inv.net_received, inv.get_status_display(), inv.get_payment_method_display(),
            ])
        return resp


class IVAReportView(CRMLoginMixin, View):
    """
    Reporte de IVA bimestral — ayuda a completar la declaración de IVA ante DIAN.
    Muestra IVA generado (ventas), IVA descontable (compras — manual), saldo a pagar/favor.
    """
    template_name = "dashboard/payments/iva_report.html"

    def get(self, request):
        from django.db.models import Count, Sum
        import calendar

        today = timezone.localdate()
        year  = int(request.GET.get("year", today.year))
        años  = list(range(today.year - 2, today.year + 1))

        # IVA por bimestre del año seleccionado
        datos_bimestres = []
        for idx, (m_ini, m_fin, label) in enumerate(BIMESTRES):
            df = timezone.datetime(year, m_ini, 1).date()
            dt = timezone.datetime(year, m_fin, calendar.monthrange(year, m_fin)[1]).date()

            agg = Invoice.objects.filter(
                issue_date__range=(df, dt)
            ).exclude(status=Invoice.Status.VOIDED).aggregate(
                iva_generado  = Sum("tax_amount"),
                rte_iva       = Sum("retention_iva"),
                total_ventas  = Sum("total"),
                n             = Count("pk"),
            )
            iva_gen   = agg["iva_generado"] or Decimal("0")
            rte_iva   = agg["rte_iva"]      or Decimal("0")
            datos_bimestres.append({
                "num":           idx + 1,
                "label":         label,
                "date_from":     df,
                "date_to":       dt,
                "total_ventas":  agg["total_ventas"] or Decimal("0"),
                "iva_generado":  iva_gen,
                "rte_iva":       rte_iva,
                # IVA descontable: el usuario debe ingresar manualmente (compras)
                "iva_saldo":     (iva_gen - rte_iva).quantize(Decimal("0.01")),
                "n_facturas":    agg["n"],
            })

        # Totales anuales
        total_año = Invoice.objects.filter(
            issue_date__year=year
        ).exclude(status=Invoice.Status.VOIDED).aggregate(
            iva=Sum("tax_amount"), ventas=Sum("total"), rte=Sum("retention_iva"),
        )

        return render(request, self.template_name, {
            "year":             year,
            "años":             años,
            "datos_bimestres":  datos_bimestres,
            "total_año":        total_año,
        })


class RetencionesSufridasView(CRMLoginMixin, View):
    """
    Reporte de retenciones aplicadas a Solution Copiers por sus clientes.
    (RteFuente + RteICA + RteIVA sufridas)
    Útil para el formulario de declaración de renta y para descontar del IVA.
    """
    template_name = "dashboard/payments/retenciones.html"

    def get(self, request):
        from django.db.models import Sum
        import calendar

        year, m_ini, m_fin, periodo_label = _get_periodo(request)
        date_from = timezone.datetime(year, m_ini, 1).date()
        last_day  = calendar.monthrange(year, m_fin)[1]
        date_to   = timezone.datetime(year, m_fin, last_day).date()

        qs = Invoice.objects.filter(
            issue_date__range=(date_from, date_to),
            retention_fuente__gt=0,
        ).exclude(status=Invoice.Status.VOIDED).order_by("issue_date")

        # También incluir las que tienen RteICA o RteIVA aunque no tengan RteFuente
        qs_ica = Invoice.objects.filter(
            issue_date__range=(date_from, date_to),
            retention_ica__gt=0,
        ).exclude(status=Invoice.Status.VOIDED)

        from django.db.models import Q as _Q
        all_rte_qs = Invoice.objects.filter(
            issue_date__range=(date_from, date_to),
        ).filter(
            _Q(retention_fuente__gt=0) |
            _Q(retention_ica__gt=0) |
            _Q(retention_iva__gt=0)
        ).exclude(status=Invoice.Status.VOIDED).order_by("issue_date")

        totales = all_rte_qs.aggregate(
            rte_fuente = Sum("retention_fuente"),
            rte_ica    = Sum("retention_ica"),
            rte_iva    = Sum("retention_iva"),
        )

        today = timezone.localdate()
        años  = list(range(today.year - 2, today.year + 1))

        if request.GET.get("export") == "csv":
            return self._export_csv(all_rte_qs, periodo_label)

        return render(request, self.template_name, {
            "facturas":      all_rte_qs,
            "totales":       totales,
            "periodo_label": periodo_label,
            "year":          year,
            "bimestre":      int(request.GET.get("bimestre", 0)),
            "bimestres":     [(i+1, lbl) for i, (_, _, lbl) in enumerate(BIMESTRES)],
            "años":          años,
            "date_from":     date_from,
            "date_to":       date_to,
        })

    @staticmethod
    def _export_csv(qs, label: str):
        import csv
        from django.http import HttpResponse as HR
        resp = HR(content_type="text/csv; charset=utf-8-sig")
        resp["Content-Disposition"] = f'attachment; filename="retenciones_{label}.csv"'
        w = csv.writer(resp)
        w.writerow([
            "Factura", "Fecha", "NIT cliente", "Cliente",
            "Total facturado", "RteFuente %", "RteFuente $",
            "RteICA ‰", "RteICA $", "RteIVA %", "RteIVA $",
            "Total retenciones", "Neto recibido",
        ])
        for inv in qs:
            w.writerow([
                inv.invoice_number, inv.issue_date, inv.client_nit, inv.client_name,
                inv.total,
                inv.retention_fuente_pct, inv.retention_fuente,
                inv.retention_ica_pct, inv.retention_ica,
                inv.retention_iva_pct, inv.retention_iva,
                inv.total_retenciones, inv.net_received,
            ])
        return resp
