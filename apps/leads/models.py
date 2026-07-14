"""Modelos del módulo Leads."""
from __future__ import annotations

import uuid
from datetime import date

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class Lead(TimeStampedModel):
    class CompanySize(models.TextChoices):
        MICRO = "1-10", _("1-10 empleados")
        SMALL = "11-50", _("11-50 empleados")
        MEDIUM = "51-200", _("51-200 empleados")
        LARGE = "201+", _("Más de 200 empleados")

    class Source(models.TextChoices):
        QUOTE_WIZARD = "wizard", _("Cotizador interactivo")
        CONTACT_FORM = "contact", _("Formulario de contacto")
        WHATSAPP = "whatsapp", _("WhatsApp")
        PHONE = "phone", _("Llamada telefónica")
        REFERRAL = "referral", _("Referido")
        IMPORT = "import", _("Base de datos importada")

    full_name = models.CharField(_("nombre completo"), max_length=150)
    email = models.EmailField(_("email"), blank=True)
    phone = models.CharField(_("teléfono"), max_length=30, blank=True)
    nit = models.CharField(_("NIT / Cédula"), max_length=25, blank=True, db_index=True)
    company_name = models.CharField(_("empresa"), max_length=200, blank=True)
    company_size = models.CharField(max_length=10, choices=CompanySize.choices, blank=True)
    job_title = models.CharField(_("cargo"), max_length=120, blank=True)
    city = models.CharField(_("ciudad"), max_length=80, default="Medellín")
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.QUOTE_WIZARD)
    notes_internal = models.TextField(_("notas internas"), blank=True)
    gdpr_consent = models.BooleanField(_("consentimiento GDPR"), default=False)

    # ── Lead Scoring (0-100) ──────────────────────────────────────────
    score      = models.PositiveSmallIntegerField(_("lead score"), default=0, db_index=True)
    score_at   = models.DateTimeField(_("score calculado el"), null=True, blank=True)

    class Meta:
        verbose_name = _("Lead")
        verbose_name_plural = _("Leads")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.company_name or 'particular'})"


class LeadActivity(TimeStampedModel):
    class ActivityType(models.TextChoices):
        CALL     = "call",     _("Llamada telefónica")
        EMAIL    = "email",    _("Email")
        MEETING  = "meeting",  _("Reunión presencial")
        NOTE     = "note",     _("Nota interna")
        WHATSAPP = "whatsapp", _("WhatsApp")
        VISIT    = "visit",    _("Visita comercial")

    lead          = models.ForeignKey("Lead", on_delete=models.CASCADE, related_name="activities")
    activity_type = models.CharField(_("tipo"), max_length=20, choices=ActivityType.choices, default=ActivityType.NOTE)
    notes         = models.TextField(_("descripción"))
    outcome       = models.CharField(_("resultado / próximo paso"), max_length=300, blank=True)
    created_by    = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="lead_activities", verbose_name=_("registrado por"),
    )

    class Meta:
        verbose_name = _("Actividad")
        verbose_name_plural = _("Actividades del lead")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_activity_type_display()} — {self.lead.full_name}"


class FollowUpTask(TimeStampedModel):
    lead        = models.ForeignKey("Lead", on_delete=models.CASCADE, related_name="tasks")
    assigned_to = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="followup_tasks", verbose_name=_("asignado a"),
    )
    due_date    = models.DateField(_("fecha límite"))
    description = models.TextField(_("descripción de la tarea"))
    is_done     = models.BooleanField(_("completada"), default=False, db_index=True)
    done_at     = models.DateTimeField(_("completada el"), null=True, blank=True)

    class Meta:
        verbose_name = _("Tarea de seguimiento")
        verbose_name_plural = _("Tareas de seguimiento")
        ordering = ["is_done", "due_date"]

    def __str__(self):
        mark = "✓" if self.is_done else "◻"
        return f"{mark} {self.description[:60]} — {self.lead.full_name}"


class EmailLog(TimeStampedModel):
    class Status(models.TextChoices):
        SENT   = "sent",   _("Enviado")
        FAILED = "failed", _("Error")

    lead      = models.ForeignKey(
        "Lead", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="email_logs", verbose_name=_("cliente"),
    )
    subject   = models.CharField(_("asunto"), max_length=300)
    recipient = models.EmailField(_("destinatario"))
    status    = models.CharField(max_length=10, choices=Status.choices, default=Status.SENT)
    error_msg = models.TextField(_("error"), blank=True)

    class Meta:
        verbose_name = _("Log de email")
        verbose_name_plural = _("Log de emails")
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.status}] {self.subject} → {self.recipient}"


class Quote(TimeStampedModel):
    class Status(models.TextChoices):
        NEW = "new", _("Nueva")
        REVIEWING = "reviewing", _("En revisión")
        SENT = "sent", _("Enviada al cliente")
        WON = "won", _("Ganada")
        LOST = "lost", _("Perdida")

    class InterestArea(models.TextChoices):
        RENTAL = "rental", _("Alquiler de fotocopiadoras")
        SALE = "sale", _("Compra de fotocopiadoras")
        CONSUMABLES = "consumables", _("Tóner, tintas y repuestos")
        CABLING = "cabling", _("Cableado estructurado")
        SOFTWARE = "software", _("Desarrollo de software")
        WEB = "web", _("Diseño web")
        MOBILE = "mobile", _("App móvil")
        DATABASE = "database", _("Base de datos")
        FULL_OFFICE = "full_office", _("Solución integral de oficina")

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="quotes")
    interest_area = models.CharField(max_length=20, choices=InterestArea.choices)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.NEW, db_index=True)
    estimated_total = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    wizard_data = models.JSONField(default=dict, blank=True)
    client_message = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_quotes",
    )
    class LostCategory(models.TextChoices):
        PRICE     = "price",     _("Precio muy alto")
        COMPETITOR= "competitor",_("Eligió a la competencia")
        NO_BUDGET = "no_budget", _("Sin presupuesto")
        TIMING    = "timing",    _("Mal momento / pospuso")
        NO_NEED   = "no_need",   _("Ya no necesita el servicio")
        NO_CONTACT= "no_contact",_("Perdió contacto / no respondió")
        OTHER     = "other",     _("Otro motivo")

    lost_reason   = models.TextField(_("motivo de pérdida"), blank=True)
    lost_category = models.CharField(
        _("categoría de pérdida"), max_length=15,
        choices=LostCategory.choices, blank=True, db_index=True
    )
    closed_at     = models.DateTimeField(_("cerrada el"), null=True, blank=True)
    close_probability = models.PositiveSmallIntegerField(
        _("probabilidad de cierre (%)"), default=0,
        help_text="0-100 %. Se actualiza al mover en el pipeline."
    )
    notes         = models.TextField(_("notas internas"), blank=True)

    class Meta:
        verbose_name = _("Cotización")
        verbose_name_plural = _("Cotizaciones")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Cotización #{self.public_id.hex[:8]} — {self.lead.full_name}"


class RentalContract(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING   = "pending",   _("Pendiente de firma")
        ACTIVE    = "active",    _("Activo")
        EXPIRED   = "expired",   _("Vencido")
        CANCELLED = "cancelled", _("Cancelado")

    lead = models.ForeignKey(
        Lead, on_delete=models.PROTECT, related_name="contracts",
        verbose_name=_("cliente"),
    )
    copier = models.ForeignKey(
        "catalog.Copier", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="rental_contracts",
        verbose_name=_("fotocopiadora"),
    )
    equipment_description = models.CharField(
        _("descripción del equipo"), max_length=300,
        help_text=_("Marca, modelo y serial del equipo entregado."),
    )
    contract_number = models.CharField(
        _("número de contrato"), max_length=30, unique=True,
    )
    status = models.CharField(
        _("estado"), max_length=15, choices=Status.choices,
        default=Status.ACTIVE, db_index=True,
    )
    start_date = models.DateField(_("fecha de inicio"))
    end_date    = models.DateField(_("fecha de vencimiento"), null=True, blank=True)
    monthly_rate = models.DecimalField(
        _("cuota mensual"), max_digits=12, decimal_places=2,
    )
    copies_included = models.PositiveIntegerField(
        _("copias incluidas/mes"), default=0,
    )
    copy_overage_rate = models.DecimalField(
        _("precio copia excedente"), max_digits=8, decimal_places=4,
        null=True, blank=True,
    )
    notes = models.TextField(_("notas / condiciones"), blank=True)

    class Meta:
        verbose_name = _("Contrato de alquiler")
        verbose_name_plural = _("Contratos de alquiler")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.contract_number} — {self.lead.full_name}"

    @property
    def days_until_expiry(self):
        if not self.end_date:
            return None
        return (self.end_date - date.today()).days

    @property
    def is_expiring_soon(self):
        d = self.days_until_expiry
        return d is not None and 0 <= d <= 30

    @property
    def is_overdue(self):
        d = self.days_until_expiry
        return d is not None and d < 0


class ServiceTicket(TimeStampedModel):
    class IssueType(models.TextChoices):
        MAINTENANCE  = "maintenance",  _("Mantenimiento preventivo")
        REPAIR       = "repair",       _("Reparación / avería")
        INSTALLATION = "installation", _("Instalación")
        CALIBRATION  = "calibration",  _("Calibración")
        SUPPLY       = "supply",       _("Suministro de insumos")
        OTHER        = "other",        _("Otro")

    class Priority(models.TextChoices):
        LOW    = "low",    _("Baja")
        MEDIUM = "medium", _("Media")
        HIGH   = "high",   _("Alta")
        URGENT = "urgent", _("Urgente")

    class Status(models.TextChoices):
        OPEN          = "open",          _("Abierto")
        IN_PROGRESS   = "in_progress",   _("En proceso")
        WAITING_PARTS = "waiting_parts", _("Esperando repuestos")
        RESOLVED      = "resolved",      _("Resuelto")
        CLOSED        = "closed",        _("Cerrado")

    ticket_number = models.CharField(_("número de ticket"), max_length=30, unique=True)
    lead = models.ForeignKey(
        Lead, on_delete=models.PROTECT, related_name="tickets",
        verbose_name=_("cliente"),
    )
    contract = models.ForeignKey(
        RentalContract, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="tickets",
        verbose_name=_("contrato relacionado"),
    )
    equipment_description = models.CharField(
        _("equipo"), max_length=300, blank=True,
    )
    issue_type = models.CharField(
        _("tipo de servicio"), max_length=20, choices=IssueType.choices,
        default=IssueType.REPAIR,
    )
    priority = models.CharField(
        _("prioridad"), max_length=10, choices=Priority.choices,
        default=Priority.MEDIUM, db_index=True,
    )
    status = models.CharField(
        _("estado"), max_length=20, choices=Status.choices,
        default=Status.OPEN, db_index=True,
    )
    description = models.TextField(_("descripción del problema"))
    address = models.CharField(_("dirección de visita"), max_length=300, blank=True)
    resolution_notes = models.TextField(_("notas de resolución"), blank=True)
    assigned_to = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_tickets", verbose_name=_("técnico asignado"),
    )
    scheduled_for = models.DateTimeField(_("visita programada"), null=True, blank=True)
    resolved_at   = models.DateTimeField(_("resuelto el"), null=True, blank=True)

    class Meta:
        verbose_name = _("Ticket de servicio")
        verbose_name_plural = _("Tickets de servicio")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ticket_number} — {self.lead.full_name}"

    @property
    def is_open(self):
        return self.status in ("open", "in_progress", "waiting_parts")


class MeterReading(TimeStampedModel):
    """Lectura mensual del contador de páginas de un contrato de alquiler."""

    contract        = models.ForeignKey(
        RentalContract, on_delete=models.CASCADE,
        related_name="meter_readings", verbose_name=_("contrato"),
    )
    reading_date    = models.DateField(_("fecha de lectura"))
    previous_reading = models.PositiveIntegerField(_("lectura anterior"), default=0)
    current_reading  = models.PositiveIntegerField(_("lectura actual"))
    notes           = models.TextField(_("notas"), blank=True)
    recorded_by     = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="meter_readings",
        verbose_name=_("registrado por"),
    )

    class Meta:
        verbose_name = _("Lectura de contador")
        verbose_name_plural = _("Lecturas de contador")
        ordering = ["-reading_date"]
        unique_together = [("contract", "reading_date")]

    def __str__(self):
        return f"Lectura {self.reading_date} — {self.contract.contract_number}"

    @property
    def pages_printed(self):
        return max(0, self.current_reading - self.previous_reading)

    @property
    def overage_pages(self):
        included = self.contract.copies_included or 0
        return max(0, self.pages_printed - included)

    @property
    def overage_charge(self):
        rate = self.contract.copy_overage_rate
        if not rate or self.overage_pages == 0:
            return 0
        return self.overage_pages * rate


class QuoteItem(TimeStampedModel):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="items")
    content_type = models.ForeignKey(
        "contenttypes.ContentType", on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)

    item_name = models.CharField(max_length=200)
    item_description = models.TextField(blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = _("Ítem de cotización")
        verbose_name_plural = _("Ítems de cotización")

    def __str__(self):
        return f"{self.quantity}x {self.item_name}"
