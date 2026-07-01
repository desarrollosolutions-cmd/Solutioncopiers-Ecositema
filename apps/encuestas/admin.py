from django.contrib import admin
from django.utils.html import format_html
from .models import Encuesta


@admin.register(Encuesta)
class EncuestaAdmin(admin.ModelAdmin):
    list_display = (
        "nombre", "empresa", "tipo_servicio_badge",
        "promedio_stars", "recomendaria_badge", "fecha",
    )
    list_filter = ("tipo_servicio", "recomendaria", "fecha")
    search_fields = ("nombre", "email", "empresa", "comentarios")
    readonly_fields = ("fecha", "ip_origen", "promedio_display")
    date_hierarchy = "fecha"
    ordering = ("-fecha",)

    fieldsets = (
        ("Datos del cliente", {
            "fields": ("nombre", "empresa", "email", "telefono"),
        }),
        ("Evaluación", {
            "fields": (
                "tipo_servicio",
                "calificacion_atencion",
                "calificacion_servicio",
                "calificacion_tiempo",
                "calificacion_precio",
                "promedio_display",
                "recomendaria",
                "comentarios",
            ),
        }),
        ("Metadata", {
            "fields": ("fecha", "ip_origen"),
            "classes": ("collapse",),
        }),
    )

    def tipo_servicio_badge(self, obj):
        return format_html('<span style="font-weight:600">{}</span>', obj.get_tipo_servicio_display())
    tipo_servicio_badge.short_description = "Servicio"

    def promedio_stars(self, obj):
        p = obj.promedio
        stars = "★" * int(p) + ("½" if p % 1 >= 0.5 else "")
        color = "#1a9e5c" if p >= 4 else ("#e09000" if p >= 3 else "#c4121a")
        return format_html('<span style="color:{};font-weight:700">{} {}</span>', color, stars, p)
    promedio_stars.short_description = "Promedio"

    def recomendaria_badge(self, obj):
        if obj.recomendaria:
            return format_html('<span style="color:#1a9e5c;font-weight:700">✓ Sí</span>')
        return format_html('<span style="color:#c4121a;font-weight:700">✗ No</span>')
    recomendaria_badge.short_description = "Recomienda"

    def promedio_display(self, obj):
        return f"{obj.promedio} / 5"
    promedio_display.short_description = "Promedio general"
