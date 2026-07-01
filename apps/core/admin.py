"""Admin del módulo Core."""
from django.contrib import admin
from .models import SiteSettings, Testimonial


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Identidad", {"fields": ("site_name", "tagline", "default_meta_description", "default_og_image")}),
        ("Contacto", {"fields": ("phone_primary", "phone_whatsapp", "email_contact", "email_sales", "address", "city", "google_maps_url")}),
        ("Redes sociales", {"fields": ("instagram_url", "facebook_url", "linkedin_url")}),
        ("Analytics", {"fields": ("google_analytics_id", "google_tag_manager_id")}),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("author_name", "author_company", "rating", "status", "is_featured", "order")
    list_filter = ("status", "is_featured", "rating")
    search_fields = ("author_name", "author_company", "quote")
    list_editable = ("status", "is_featured", "order")
