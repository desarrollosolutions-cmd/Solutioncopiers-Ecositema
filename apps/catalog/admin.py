"""Admin del Silo 1."""
from django.contrib import admin
from .models import CablingService, Consumable, Copier, CopierCategory, CopierImage


class CopierImageInline(admin.TabularInline):
    model = CopierImage
    extra = 1


@admin.register(CopierCategory)
class CopierCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "order")
    list_editable = ("status", "order")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Copier)
class CopierAdmin(admin.ModelAdmin):
    list_display = (
        "name", "model_number", "category", "toner_type",
        "monthly_rental_price", "status", "is_featured",
    )
    list_filter = ("status", "is_featured", "category", "toner_type", "paper_size")
    search_fields = ("name", "model_number", "brand")
    list_editable = ("status", "is_featured")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [CopierImageInline]
    fieldsets = (
        ("Identidad", {
            "fields": ("name", "slug", "brand", "model_number", "category"),
        }),
        ("Descripciones", {
            "fields": ("short_description", "description"),
        }),
        ("Especificaciones técnicas", {
            "fields": (
                "toner_type", "paper_size", "speed_ppm",
                "monthly_duty_cycle",
                ("has_scanner", "has_duplex", "has_network", "has_wifi"),
            ),
        }),
        ("Disponibilidad y precios", {
            "fields": (
                ("available_for_rental", "available_for_sale"),
                "monthly_rental_price", "sale_price",
                "pages_included_monthly", "extra_page_cost",
            ),
        }),
        ("Imagen y archivos", {
            "fields": ("main_image", "main_image_alt", "datasheet_pdf"),
        }),
        ("SEO", {
            "fields": ("meta_title", "meta_description", "meta_keywords", "og_image", "schema_type", "noindex"),
            "classes": ("collapse",),
        }),
        ("Publicación", {
            "fields": ("status", "published_at", "is_featured", "order"),
        }),
    )


@admin.register(Consumable)
class ConsumableAdmin(admin.ModelAdmin):
    list_display = ("name", "consumable_type", "part_number", "price", "in_stock", "status")
    list_filter = ("status", "consumable_type", "in_stock", "brand")
    search_fields = ("name", "part_number")
    filter_horizontal = ("compatible_models",)


@admin.register(CablingService)
class CablingServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "base_price", "status", "is_featured", "order")
    list_editable = ("status", "is_featured", "order")
    list_filter = ("status", "is_featured")
