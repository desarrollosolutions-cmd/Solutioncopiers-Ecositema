from django.contrib import admin
from django.utils.html import format_html

from .models import Invoice, InvoiceItem, Order, OrderItem, Payment


class OrderItemInline(admin.TabularInline):
    model  = OrderItem
    extra  = 0
    fields = ("product_name", "part_number", "quantity", "unit_price")
    readonly_fields = ("line_total",)

    def line_total(self, obj):
        return f"${obj.line_total:,.0f}"
    line_total.short_description = "Total línea"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display  = ("reference", "buyer_name", "buyer_email", "status_badge", "total_display", "created_at")
    list_filter   = ("status", "created_at")
    search_fields = ("reference", "buyer_name", "buyer_email", "buyer_nit")
    readonly_fields = ("reference", "created_at", "updated_at")
    inlines       = [OrderItemInline]

    def status_badge(self, obj):
        colors = {
            "pending":   "#f59e0b",
            "paid":      "#10b981",
            "failed":    "#ef4444",
            "cancelled": "#6b7280",
            "refunded":  "#8b5cf6",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = "Estado"

    def total_display(self, obj):
        return f"${obj.total:,.0f} COP"
    total_display.short_description = "Total"


class InvoiceItemInline(admin.TabularInline):
    model  = InvoiceItem
    extra  = 1
    fields = ("description", "quantity", "unit", "unit_price", "discount_pct", "tax_rate")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display  = ("invoice_number", "client_name", "status", "total_display", "issue_date", "due_date")
    list_filter   = ("status", "invoice_type", "issue_date")
    search_fields = ("client_name", "client_nit", "dian_consecutive", "cufe")
    readonly_fields = ("created_at", "updated_at", "invoice_number")
    inlines       = [InvoiceItemInline]

    def total_display(self, obj):
        return f"${obj.total:,.0f} COP"
    total_display.short_description = "Total"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display  = ("reference", "wompi_id", "status", "amount_display", "payment_method_type", "created_at")
    list_filter   = ("status", "currency", "payment_method_type")
    search_fields = ("reference", "wompi_id")
    readonly_fields = ("created_at", "updated_at", "raw_payload")

    def amount_display(self, obj):
        return f"${obj.amount_cop:,.0f} COP"
    amount_display.short_description = "Monto"
