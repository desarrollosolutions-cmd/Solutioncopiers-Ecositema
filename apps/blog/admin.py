from django.contrib import admin
from .models import Category, Post, Tag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "silo", "slug")
    list_filter = ("silo",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "title", "category", "author", "status",
        "is_featured", "reading_time_min", "published_at",
    )
    list_filter = ("status", "is_featured", "category", "tags")
    search_fields = ("title", "content", "excerpt")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("tags",)
    date_hierarchy = "published_at"
    list_editable = ("status", "is_featured")
    readonly_fields = ("created_at", "updated_at", "reading_time_min")
    fieldsets = (
        ("Contenido", {
            "fields": ("title", "slug", "category", "tags", "author"),
        }),
        ("Texto", {
            "fields": ("excerpt", "content"),
        }),
        ("Imagen", {
            "fields": ("image_hero", "image_card"),
        }),
        ("Publicación", {
            "fields": ("status", "is_featured", "published_at", "reading_time_min"),
        }),
        ("SEO", {
            "fields": ("meta_title", "meta_description", "meta_keywords", "noindex"),
            "classes": ("collapse",),
        }),
    )
