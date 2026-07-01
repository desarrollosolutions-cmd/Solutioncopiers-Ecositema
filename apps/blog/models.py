"""Modelos del Blog."""
from __future__ import annotations

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.core.models import (
    FeatureableModel, MainImageModel, PublishableModel,
    SEOModel, SluggableModel, TimeStampedModel,
)


class Category(TimeStampedModel, SluggableModel, SEOModel):
    class Silo(models.TextChoices):
        HARDWARE = "hardware", _("Hardware / Infraestructura")
        SOFTWARE = "software", _("Software / Digital")
        GENERAL = "general", _("General")

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    silo = models.CharField(max_length=20, choices=Silo.choices, default=Silo.GENERAL)

    class Meta:
        verbose_name = _("Categoría del blog")
        verbose_name_plural = _("Categorías del blog")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("blog:post_by_category", kwargs={"slug": self.slug})


class Tag(TimeStampedModel, SluggableModel):
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Post(
    TimeStampedModel, SluggableModel, SEOModel, MainImageModel,
    PublishableModel, FeatureableModel,
):
    title = models.CharField(max_length=200)
    excerpt = models.TextField(_("resumen"), max_length=300)
    content = models.TextField(_("contenido completo"))
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="posts")
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")
    author = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, related_name="posts",
    )
    reading_time_min = models.PositiveSmallIntegerField(_("tiempo de lectura"), default=5)

    slug_source_field = "title"

    class Meta:
        verbose_name = _("Post")
        verbose_name_plural = _("Posts")
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "published_at"]),
            models.Index(fields=["category", "status"]),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("blog:post_detail", kwargs={"slug": self.slug})
