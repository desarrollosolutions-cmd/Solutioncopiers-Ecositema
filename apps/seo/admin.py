"""Admin del módulo SEO."""
from django.contrib import admin
from .models import DesignTokens, RedirectRule


@admin.register(DesignTokens)
class DesignTokensAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Identidad", {"fields": ("name",)}),
        ("Paleta de Colores Principales", {
            "fields": (
                ("color_primary", "color_primary_dark", "color_primary_light"),
                ("color_accent", "color_accent_dark"),
                ("color_success", "color_warning", "color_danger"),
            )
        }),
        ("Neutros y Superficies", {
            "fields": (
                ("color_bg", "color_bg_alt", "color_surface"),
                ("color_text_primary", "color_text_secondary", "color_text_muted"),
                ("color_border",),
            )
        }),
        ("Tipografía", {"fields": ("font_display", "font_body", "font_mono", "google_fonts_url")}),
        ("Spacing", {"fields": ("spacing_base", ("border_radius_base", "border_radius_lg"))}),
        ("Glassmorphism", {"fields": (("glass_blur_amount", "glass_opacity"),)}),
        ("Sombras", {"fields": ("shadow_card", "shadow_card_hover")}),
        ("Animaciones", {"fields": (
            "animations_enabled", "animation_duration_base",
            ("parallax_enabled", "smooth_scroll_enabled"),
        )}),
    )

    def has_add_permission(self, request):
        return not DesignTokens.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RedirectRule)
class RedirectRuleAdmin(admin.ModelAdmin):
    list_display = ("old_path", "new_path", "redirect_type", "is_active", "hits")
    list_filter = ("redirect_type", "is_active")
    search_fields = ("old_path", "new_path")
    readonly_fields = ("hits", "created_at", "updated_at")
