import csv

from django.contrib import admin
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    EmailLog, FollowUpTask, Lead, LeadActivity,
    Quote, QuoteItem, RentalContract, ServiceTicket,
)


# ---------------------------------------------------------------------------
# Acción exportar CSV (reutilizable)
# ---------------------------------------------------------------------------
def _export_csv(queryset, filename, fields):
    """Descarga CSV con los campos indicados como (header, callable/attr)."""
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow([h for h, _ in fields])
    for obj in queryset:
        row = []
        for _, getter in fields:
            if callable(getter):
                row.append(getter(obj))
            else:
                val = obj
                for attr in getter.split("__"):
                    val = getattr(val, attr, "") if val is not None else ""
                row.append(val if val is not None else "")
        writer.writerow(row)
    return response


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------
class LeadActivityInline(admin.StackedInline):
    model = LeadActivity
    extra = 1
    fields = ("activity_type", "notes", "outcome", "created_by", "created_at")
    readonly_fields = ("created_at",)
    show_change_link = False
    ordering = ("-created_at",)


class FollowUpTaskInline(admin.TabularInline):
    model = FollowUpTask
    extra = 1
    fields = ("description", "due_date", "assigned_to", "is_done", "done_at")
    readonly_fields = ("done_at",)
    ordering = ("is_done", "due_date")


class QuoteItemInline(admin.TabularInline):
    model = QuoteItem
    extra = 0
    readonly_fields = ("created_at",)


# ---------------------------------------------------------------------------
# Lead
# ---------------------------------------------------------------------------
def export_leads_csv(modeladmin, request, queryset):
    fields = [
        ("Nombre",        "full_name"),
        ("Empresa",       "company_name"),
        ("Email",         "email"),
        ("Teléfono",      "phone"),
        ("Ciudad",        "city"),
        ("Tamaño",        "company_size"),
        ("Cargo",         "job_title"),
        ("Fuente",        "source"),
        ("Creado el",     lambda o: o.created_at.strftime("%Y-%m-%d")),
    ]
    return _export_csv(queryset, "leads.csv", fields)

export_leads_csv.short_description = "Exportar selección a CSV"


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "full_name", "company_name", "email", "whatsapp_link",
        "source", "city", "created_at",
    )
    list_filter = ("source", "company_size", "city")
    search_fields = ("full_name", "email", "company_name", "phone")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    actions = [export_leads_csv]
    inlines = [LeadActivityInline, FollowUpTaskInline]

    @admin.display(description="WhatsApp")
    def whatsapp_link(self, obj):
        if not obj.phone:
            return "—"
        number = obj.phone.replace("+", "").replace(" ", "").replace("-", "")
        if not number.startswith("57"):
            number = "57" + number
        url = f"https://wa.me/{number}?text=Hola+{obj.full_name.split()[0]}%2C+te+contactamos+desde+Solution+Copiers"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer"'
            '   style="color:#25D366;font-weight:600">💬 Escribir</a>', url
        )


# ---------------------------------------------------------------------------
# LeadActivity stand-alone
# ---------------------------------------------------------------------------
@admin.register(LeadActivity)
class LeadActivityAdmin(admin.ModelAdmin):
    list_display  = ("activity_type", "lead", "outcome", "created_by", "created_at")
    list_filter   = ("activity_type",)
    search_fields = ("lead__full_name", "notes", "outcome")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("lead",)
    date_hierarchy = "created_at"


# ---------------------------------------------------------------------------
# FollowUpTask stand-alone
# ---------------------------------------------------------------------------
@admin.register(FollowUpTask)
class FollowUpTaskAdmin(admin.ModelAdmin):
    list_display  = ("description_short", "lead", "assigned_to", "due_date", "is_done", "done_at")
    list_filter   = ("is_done", "assigned_to")
    search_fields = ("lead__full_name", "description")
    list_editable = ("is_done",)
    readonly_fields = ("done_at", "created_at")
    autocomplete_fields = ("lead",)
    date_hierarchy = "due_date"

    @admin.display(description="Tarea")
    def description_short(self, obj):
        return obj.description[:70] + ("…" if len(obj.description) > 70 else "")

    def save_model(self, request, obj, form, change):
        if obj.is_done and not obj.done_at:
            obj.done_at = timezone.now()
        elif not obj.is_done:
            obj.done_at = None
        super().save_model(request, obj, form, change)


# ---------------------------------------------------------------------------
# Quote
# ---------------------------------------------------------------------------
def export_quotes_csv(modeladmin, request, queryset):
    fields = [
        ("ID",            lambda o: str(o.public_id)[:8]),
        ("Cliente",       "lead__full_name"),
        ("Empresa",       "lead__company_name"),
        ("Email",         "lead__email"),
        ("Área",          "interest_area"),
        ("Estado",        "status"),
        ("Total estim.",  lambda o: str(o.estimated_total or "")),
        ("Motivo pérdida","lost_reason"),
        ("Creado el",     lambda o: o.created_at.strftime("%Y-%m-%d")),
        ("Cerrado el",    lambda o: o.closed_at.strftime("%Y-%m-%d") if o.closed_at else ""),
    ]
    return _export_csv(queryset, "cotizaciones.csv", fields)

export_quotes_csv.short_description = "Exportar selección a CSV"


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = (
        "public_id_short", "lead", "interest_area", "status",
        "estimated_total", "assigned_to", "created_at",
    )
    list_filter   = ("status", "interest_area", "assigned_to")
    search_fields = ("lead__full_name", "lead__email", "public_id")
    readonly_fields = ("public_id", "created_at", "updated_at", "wizard_data")
    inlines       = [QuoteItemInline]
    date_hierarchy = "created_at"
    list_editable  = ("status",)
    actions        = [export_quotes_csv]
    fieldsets = (
        ("Identificación", {
            "fields": ("public_id", "lead", "interest_area", "assigned_to"),
        }),
        ("Estado", {
            "fields": ("status", "estimated_total", "closed_at"),
        }),
        ("Detalles", {
            "fields": ("client_message", "wizard_data"),
        }),
        ("Cierre", {
            "fields": ("lost_reason",),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="ID")
    def public_id_short(self, obj):
        return str(obj.public_id)[:8]

    def save_model(self, request, obj, form, change):
        if obj.status in ("won", "lost") and not obj.closed_at:
            obj.closed_at = timezone.now()
        super().save_model(request, obj, form, change)


# ---------------------------------------------------------------------------
# RentalContract
# ---------------------------------------------------------------------------
def export_contracts_csv(modeladmin, request, queryset):
    fields = [
        ("Contrato",      "contract_number"),
        ("Cliente",       "lead__full_name"),
        ("Empresa",       "lead__company_name"),
        ("Equipo",        "equipment_description"),
        ("Estado",        "status"),
        ("Cuota mensual", lambda o: str(o.monthly_rate)),
        ("Inicio",        lambda o: str(o.start_date)),
        ("Vencimiento",   lambda o: str(o.end_date) if o.end_date else ""),
        ("Días restantes",lambda o: str(o.days_until_expiry) if o.days_until_expiry is not None else ""),
    ]
    return _export_csv(queryset, "contratos.csv", fields)

export_contracts_csv.short_description = "Exportar selección a CSV"


@admin.register(RentalContract)
class RentalContractAdmin(admin.ModelAdmin):
    list_display = (
        "contract_number", "lead_name", "equipment_description",
        "status", "monthly_rate", "start_date", "end_date", "days_left",
    )
    list_filter   = ("status",)
    search_fields = (
        "contract_number", "lead__full_name",
        "lead__company_name", "equipment_description",
    )
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy  = "start_date"
    autocomplete_fields = ("lead",)
    actions = [export_contracts_csv]
    fieldsets = (
        ("Identificación", {
            "fields": ("contract_number", "lead", "copier", "equipment_description"),
        }),
        ("Fechas y estado", {
            "fields": ("status", "start_date", "end_date"),
        }),
        ("Condiciones económicas", {
            "fields": ("monthly_rate", "copies_included", "copy_overage_rate"),
        }),
        ("Notas", {"fields": ("notes",)}),
    )

    @admin.display(description="Cliente")
    def lead_name(self, obj):
        return obj.lead.full_name

    @admin.display(description="Días restantes")
    def days_left(self, obj):
        d = obj.days_until_expiry
        if d is None:
            return "—"
        if d < 0:
            return format_html('<span style="color:red;font-weight:600">Vencido {}</span>', abs(d))
        if d <= 30:
            return format_html('<span style="color:orange;font-weight:600">{} días</span>', d)
        return f"{d} días"


# ---------------------------------------------------------------------------
# ServiceTicket
# ---------------------------------------------------------------------------
@admin.register(ServiceTicket)
class ServiceTicketAdmin(admin.ModelAdmin):
    list_display = (
        "ticket_number", "lead_name", "issue_type", "priority",
        "status", "assigned_to", "scheduled_for", "created_at",
    )
    list_filter   = ("status", "priority", "issue_type")
    search_fields = (
        "ticket_number", "lead__full_name",
        "lead__company_name", "equipment_description",
    )
    readonly_fields = ("created_at", "updated_at", "resolved_at")
    date_hierarchy  = "created_at"
    list_editable   = ("status", "priority")
    autocomplete_fields = ("lead",)
    fieldsets = (
        ("Identificación", {
            "fields": ("ticket_number", "lead", "contract", "equipment_description"),
        }),
        ("Problema", {
            "fields": ("issue_type", "priority", "status", "description"),
        }),
        ("Resolución", {
            "fields": ("assigned_to", "scheduled_for", "resolution_notes", "resolved_at"),
        }),
    )

    @admin.display(description="Cliente")
    def lead_name(self, obj):
        return obj.lead.full_name


# ---------------------------------------------------------------------------
# EmailLog (solo lectura — auditoría)
# ---------------------------------------------------------------------------
@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display  = ("subject_short", "recipient", "lead", "status", "created_at")
    list_filter   = ("status",)
    search_fields = ("subject", "recipient", "lead__full_name")
    readonly_fields = ("lead", "subject", "recipient", "status", "error_msg", "created_at")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Asunto")
    def subject_short(self, obj):
        return obj.subject[:60] + ("…" if len(obj.subject) > 60 else "")
