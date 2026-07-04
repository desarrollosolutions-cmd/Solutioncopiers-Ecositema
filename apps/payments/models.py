"""
Modelos de Pagos y Facturación.

Estructura:
  Order / OrderItem  — pedido público desde el catálogo web (consumibles)
  Invoice / InvoiceItem — factura DIAN (B2B y B2C, manual o desde Order)
  Payment            — transacción Wompi vinculada a Order o Invoice
"""
from __future__ import annotations

import hashlib
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _order_ref() -> str:
    """Referencia única para Wompi: SC-XXXXXXXX (8 hex mayúsculas)."""
    return "SC-" + uuid.uuid4().hex[:8].upper()


# ---------------------------------------------------------------------------
# ORDER — pedido público
# ---------------------------------------------------------------------------

class Order(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING  = "pending",   _("Pendiente de pago")
        PAID     = "paid",      _("Pagado")
        FAILED   = "failed",    _("Pago fallido")
        CANCELLED = "cancelled", _("Cancelado")
        REFUNDED = "refunded",  _("Reembolsado")

    reference    = models.CharField(_("referencia"), max_length=20, unique=True, default=_order_ref, db_index=True)
    status       = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)

    # Datos del comprador (puede no tener cuenta)
    buyer_name   = models.CharField(_("nombre del comprador"), max_length=150)
    buyer_email  = models.EmailField(_("email"))
    buyer_phone  = models.CharField(_("teléfono"), max_length=30, blank=True)
    buyer_nit    = models.CharField(_("NIT / Cédula"), max_length=25, blank=True)
    buyer_company = models.CharField(_("empresa"), max_length=200, blank=True)
    buyer_city   = models.CharField(_("ciudad"), max_length=80, default="Medellín")
    buyer_address = models.CharField(_("dirección"), max_length=300, blank=True)

    # Totales
    subtotal     = models.DecimalField(_("subtotal"), max_digits=14, decimal_places=2, default=0)
    tax_amount   = models.DecimalField(_("IVA"), max_digits=14, decimal_places=2, default=0)
    total        = models.DecimalField(_("total"), max_digits=14, decimal_places=2, default=0)

    # Notas
    notes        = models.TextField(_("notas"), blank=True)

    # Relación opcional con Lead del CRM
    lead         = models.ForeignKey(
        "leads.Lead", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="orders", verbose_name=_("lead CRM"),
    )

    class Meta:
        verbose_name        = _("Pedido")
        verbose_name_plural = _("Pedidos")
        ordering            = ["-created_at"]
        indexes             = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"{self.reference} — {self.buyer_name} ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse("payments:order_confirmation", kwargs={"reference": self.reference})

    # ── helpers ──────────────────────────────────────────────────────────────

    @property
    def amount_in_cents(self) -> int:
        """Total en centavos para Wompi (1 COP = 100 centavos)."""
        return int(self.total * 100)

    def recalculate_totals(self):
        subtotal = sum((item.line_total for item in self.items.all()), Decimal("0.00"))
        iva      = subtotal * Decimal("0.19")
        self.subtotal   = subtotal
        self.tax_amount = iva.quantize(Decimal("0.01"))
        self.total      = (subtotal + self.tax_amount).quantize(Decimal("0.01"))


class OrderItem(TimeStampedModel):
    order        = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    consumable   = models.ForeignKey(
        "catalog.Consumable", on_delete=models.PROTECT, related_name="order_items",
    )
    quantity     = models.PositiveSmallIntegerField(_("cantidad"), default=1)
    unit_price   = models.DecimalField(_("precio unitario"), max_digits=12, decimal_places=2)
    # precio al momento de la compra (puede cambiar luego en catálogo)
    product_name = models.CharField(_("nombre del producto"), max_length=200)
    part_number  = models.CharField(_("referencia"), max_length=80, blank=True)

    class Meta:
        verbose_name        = _("Línea de pedido")
        verbose_name_plural = _("Líneas de pedido")

    def __str__(self):
        return f"{self.quantity}x {self.product_name}"

    @property
    def line_total(self) -> Decimal:
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------
# INVOICE — factura DIAN
# ---------------------------------------------------------------------------

class Invoice(TimeStampedModel):
    class InvoiceType(models.TextChoices):
        SALE     = "FV", _("Factura de Venta")
        CREDIT   = "NC", _("Nota Crédito")
        DEBIT    = "ND", _("Nota Débito")

    class Status(models.TextChoices):
        DRAFT    = "draft",    _("Borrador")
        ISSUED   = "issued",   _("Emitida")
        SENT     = "sent",     _("Enviada al cliente")
        PAID     = "paid",     _("Pagada")
        OVERDUE  = "overdue",  _("Vencida")
        VOIDED   = "voided",   _("Anulada")

    class PaymentMethod(models.TextChoices):
        CASH        = "10", _("Efectivo")
        BANK_XFER   = "42", _("Transferencia bancaria")
        CREDIT_CARD = "48", _("Tarjeta de crédito/débito")
        WOMPI       = "49", _("Pasarela electrónica (Wompi)")
        CHECK       = "20", _("Cheque")

    # ── Campos DIAN ───────────────────────────────────────────────────────
    invoice_type     = models.CharField(max_length=2, choices=InvoiceType.choices, default=InvoiceType.SALE)
    # Resolución DIAN (se llenará cuando el usuario tenga PT y resolución)
    dian_resolution  = models.CharField(_("resolución DIAN"), max_length=50, blank=True)
    dian_prefix      = models.CharField(_("prefijo"), max_length=10, blank=True, default="FV")
    dian_consecutive = models.PositiveIntegerField(_("consecutivo"), default=0)
    # CUFE: Código Único de Factura Electrónica (generado por el PT)
    cufe             = models.CharField(_("CUFE"), max_length=200, blank=True)
    # QR code URL (generado por el PT)
    qr_url           = models.URLField(_("URL QR DIAN"), blank=True)

    # ── Estado y fechas ───────────────────────────────────────────────────
    status           = models.CharField(max_length=8, choices=Status.choices, default=Status.DRAFT, db_index=True)
    issue_date       = models.DateField(_("fecha de emisión"), default=timezone.localdate)
    due_date         = models.DateField(_("fecha de vencimiento"), null=True, blank=True)
    paid_date        = models.DateField(_("fecha de pago"), null=True, blank=True)

    # ── Emisor (nuestra empresa) ──────────────────────────────────────────
    issuer_name      = models.CharField(_("nombre emisor"), max_length=200, default="Solution Copiers")
    issuer_nit       = models.CharField(_("NIT emisor"), max_length=20, blank=True)
    issuer_address   = models.CharField(_("dirección emisor"), max_length=300, blank=True)
    issuer_city      = models.CharField(_("ciudad emisor"), max_length=80, default="Medellín")
    issuer_email     = models.EmailField(_("email emisor"), blank=True)
    issuer_phone     = models.CharField(_("teléfono emisor"), max_length=30, blank=True)
    issuer_tax_regime = models.CharField(_("régimen tributario"), max_length=60, blank=True, default="Responsable de IVA")

    # ── Receptor (cliente) ────────────────────────────────────────────────
    client_name      = models.CharField(_("nombre cliente"), max_length=200)
    client_nit       = models.CharField(_("NIT / Cédula cliente"), max_length=25, blank=True)
    client_email     = models.EmailField(_("email cliente"), blank=True)
    client_phone     = models.CharField(_("teléfono cliente"), max_length=30, blank=True)
    client_address   = models.CharField(_("dirección cliente"), max_length=300, blank=True)
    client_city      = models.CharField(_("ciudad cliente"), max_length=80, blank=True)

    # ── Totales ───────────────────────────────────────────────────────────
    subtotal         = models.DecimalField(_("subtotal"), max_digits=14, decimal_places=2, default=0)
    discount_amount  = models.DecimalField(_("descuento"), max_digits=14, decimal_places=2, default=0)
    tax_base         = models.DecimalField(_("base gravable"), max_digits=14, decimal_places=2, default=0)
    tax_amount       = models.DecimalField(_("IVA (19%)"), max_digits=14, decimal_places=2, default=0)
    total            = models.DecimalField(_("total"), max_digits=14, decimal_places=2, default=0)

    # ── Retenciones (Colombia) ────────────────────────────────────────────
    # Retención en la Fuente — el comprador retiene al vendedor
    # Tarifa típica: 2.5% productos (declarantes), 3.5% (no declarantes)
    retention_fuente_pct  = models.DecimalField(
        _("tarifa RteFuente %"), max_digits=5, decimal_places=2, default=Decimal("0.00"),
    )
    retention_fuente      = models.DecimalField(
        _("RteFuente aplicada"), max_digits=14, decimal_places=2, default=0,
    )
    # ReteICA — Industria y Comercio (Medellín comercio: 9.66‰ = 0.966%)
    retention_ica_pct     = models.DecimalField(
        _("tarifa ReteICA ‰"), max_digits=5, decimal_places=2, default=Decimal("0.00"),
    )
    retention_ica         = models.DecimalField(
        _("ReteICA aplicada"), max_digits=14, decimal_places=2, default=0,
    )
    # ReteIVA — 15% del IVA; solo aplica cuando el comprador es gran contribuyente
    retention_iva_pct     = models.DecimalField(
        _("tarifa ReteIVA %"), max_digits=5, decimal_places=2, default=Decimal("0.00"),
    )
    retention_iva         = models.DecimalField(
        _("ReteIVA aplicada"), max_digits=14, decimal_places=2, default=0,
    )
    # Neto a pagar: total - retenciones (lo que realmente se recibe)
    net_received          = models.DecimalField(
        _("neto recibido"), max_digits=14, decimal_places=2, default=0,
    )

    # ── Método de pago ────────────────────────────────────────────────────
    payment_method   = models.CharField(max_length=2, choices=PaymentMethod.choices, default=PaymentMethod.WOMPI)
    payment_notes    = models.TextField(_("notas de pago"), blank=True)

    # ── Relaciones ────────────────────────────────────────────────────────
    order            = models.OneToOneField(
        Order, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="invoice", verbose_name=_("pedido origen"),
    )
    lead             = models.ForeignKey(
        "leads.Lead", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="invoices", verbose_name=_("cliente CRM"),
    )
    created_by       = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="invoices_created",
    )

    # ── Notas ─────────────────────────────────────────────────────────────
    notes            = models.TextField(_("observaciones"), blank=True)

    # ── Stock ─────────────────────────────────────────────────────────────
    stock_reduced    = models.BooleanField(_("stock descontado"), default=False)

    class Meta:
        verbose_name        = _("Factura")
        verbose_name_plural = _("Facturas")
        ordering            = ["-issue_date", "-dian_consecutive"]
        indexes             = [
            models.Index(fields=["status", "issue_date"]),
            models.Index(fields=["client_nit"]),
        ]

    def __str__(self):
        num = f"{self.dian_prefix}-{self.dian_consecutive:05d}" if self.dian_consecutive else f"BORR-{self.pk}"
        return f"{num} | {self.client_name} | ${self.total:,.0f}"

    @property
    def invoice_number(self) -> str:
        if self.dian_consecutive:
            return f"{self.dian_prefix}-{self.dian_consecutive:05d}"
        return f"BORR-{self.pk}"

    @property
    def is_overdue(self) -> bool:
        if self.due_date and self.status not in (self.Status.PAID, self.Status.VOIDED):
            return timezone.localdate() > self.due_date
        return False

    def recalculate_totals(self, tax_rate: Decimal = Decimal("0.19")):
        subtotal = sum((item.line_total for item in self.items.all()), Decimal("0.00"))
        discount = Decimal(self.discount_amount)
        base     = (subtotal - discount).quantize(Decimal("0.01"))
        iva      = (base * tax_rate).quantize(Decimal("0.01"))
        total    = (base + iva).quantize(Decimal("0.01"))

        # Retenciones sobre el total facturado
        rte_fuente = (total * self.retention_fuente_pct / 100).quantize(Decimal("0.01"))
        rte_ica    = (base * self.retention_ica_pct / 1000).quantize(Decimal("0.01"))  # ‰ sobre base
        rte_iva    = (iva  * self.retention_iva_pct  / 100).quantize(Decimal("0.01"))

        self.subtotal          = subtotal
        self.tax_base          = base
        self.tax_amount        = iva
        self.total             = total
        self.retention_fuente  = rte_fuente
        self.retention_ica     = rte_ica
        self.retention_iva     = rte_iva
        self.net_received      = (total - rte_fuente - rte_ica - rte_iva).quantize(Decimal("0.01"))

    @property
    def total_retenciones(self) -> Decimal:
        return (self.retention_fuente + self.retention_ica + self.retention_iva).quantize(Decimal("0.01"))


class InvoiceItem(TimeStampedModel):
    invoice      = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    description  = models.CharField(_("descripción"), max_length=300)
    quantity     = models.DecimalField(_("cantidad"), max_digits=10, decimal_places=2, default=1)
    unit         = models.CharField(_("unidad"), max_length=30, default="UND")
    unit_price   = models.DecimalField(_("precio unitario"), max_digits=14, decimal_places=2)
    discount_pct = models.DecimalField(_("descuento %"), max_digits=5, decimal_places=2, default=0)
    tax_rate     = models.DecimalField(_("tasa IVA"), max_digits=5, decimal_places=4, default=Decimal("0.19"))
    # Referencia opcional al consumible o copier
    consumable   = models.ForeignKey(
        "catalog.Consumable", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="invoice_items",
    )

    class Meta:
        verbose_name        = _("Línea de factura")
        verbose_name_plural = _("Líneas de factura")
        ordering            = ["pk"]

    def __str__(self):
        return f"{self.quantity} x {self.description}"

    @property
    def line_subtotal(self) -> Decimal:
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))

    @property
    def line_discount(self) -> Decimal:
        return (self.line_subtotal * self.discount_pct / 100).quantize(Decimal("0.01"))

    @property
    def line_total(self) -> Decimal:
        return (self.line_subtotal - self.line_discount).quantize(Decimal("0.01"))

    @property
    def line_tax(self) -> Decimal:
        return (self.line_total * self.tax_rate).quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------
# PAYMENT — transacción Wompi
# ---------------------------------------------------------------------------

class Payment(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING   = "PENDING",   _("Pendiente")
        APPROVED  = "APPROVED",  _("Aprobado")
        DECLINED  = "DECLINED",  _("Rechazado")
        VOIDED    = "VOIDED",    _("Anulado")
        ERROR     = "ERROR",     _("Error")

    class Currency(models.TextChoices):
        COP = "COP", "COP"
        USD = "USD", "USD"

    # ── Relaciones ────────────────────────────────────────────────────────
    order         = models.ForeignKey(
        Order, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="payments",
    )
    invoice       = models.ForeignKey(
        Invoice, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="payments",
    )

    # ── Datos Wompi ───────────────────────────────────────────────────────
    wompi_id           = models.CharField(_("ID transacción Wompi"), max_length=30, blank=True, db_index=True)
    reference          = models.CharField(_("referencia"), max_length=30, db_index=True)
    status             = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    amount_in_cents    = models.PositiveBigIntegerField(_("monto en centavos"))
    currency           = models.CharField(max_length=3, choices=Currency.choices, default=Currency.COP)
    payment_method_type = models.CharField(_("método Wompi"), max_length=30, blank=True)
    # e.g. "CARD", "NEQUI", "PSE", "BANCOLOMBIA_TRANSFER"

    # Datos de tarjeta/PSE (parciales, para referencia)
    card_brand         = models.CharField(_("marca tarjeta"), max_length=20, blank=True)
    card_last_four     = models.CharField(_("últimos 4 dígitos"), max_length=4, blank=True)
    bank_name          = models.CharField(_("banco PSE"), max_length=80, blank=True)

    # ── Webhook ───────────────────────────────────────────────────────────
    webhook_received_at = models.DateTimeField(_("webhook recibido"), null=True, blank=True)
    raw_payload         = models.JSONField(_("payload Wompi"), default=dict, blank=True)

    # ── Timestamps Wompi ──────────────────────────────────────────────────
    finalized_at        = models.DateTimeField(_("finalizada"), null=True, blank=True)

    class Meta:
        verbose_name        = _("Pago")
        verbose_name_plural = _("Pagos")
        ordering            = ["-created_at"]
        indexes             = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        amount_cop = self.amount_in_cents / 100
        return f"{self.reference} | {self.get_status_display()} | ${amount_cop:,.0f} COP"

    @property
    def amount_cop(self) -> Decimal:
        return Decimal(self.amount_in_cents) / 100
