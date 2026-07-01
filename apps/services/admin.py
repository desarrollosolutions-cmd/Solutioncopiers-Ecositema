from django.contrib import admin
from .models import (
    CaseStudy, DatabaseService, MobileService,
    SoftwareService, Technology, WebService,
)


@admin.register(Technology)
class TechnologyAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "proficiency_level", "order")
    list_filter = ("category",)
    list_editable = ("proficiency_level", "order")


class _ServiceBaseAdmin(admin.ModelAdmin):
    list_display = ("name", "starting_price", "status", "is_featured", "order")
    list_filter = ("status", "is_featured")
    list_editable = ("status", "is_featured", "order")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("technologies",)


@admin.register(SoftwareService)
class SoftwareServiceAdmin(_ServiceBaseAdmin):
    list_display = _ServiceBaseAdmin.list_display + ("software_type",)


@admin.register(WebService)
class WebServiceAdmin(_ServiceBaseAdmin):
    list_display = _ServiceBaseAdmin.list_display + ("web_type",)


@admin.register(MobileService)
class MobileServiceAdmin(_ServiceBaseAdmin):
    list_display = _ServiceBaseAdmin.list_display + ("mobile_type",)


@admin.register(DatabaseService)
class DatabaseServiceAdmin(_ServiceBaseAdmin):
    list_display = _ServiceBaseAdmin.list_display + ("database_type",)


@admin.register(CaseStudy)
class CaseStudyAdmin(admin.ModelAdmin):
    list_display = ("title", "client_name", "client_industry", "status", "is_featured")
    list_filter = ("status", "is_featured", "client_industry")
    search_fields = ("title", "client_name")
    list_editable = ("status", "is_featured")
    filter_horizontal = ("technologies_used",)
