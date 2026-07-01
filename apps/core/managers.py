"""Managers reutilizables."""
from django.db import models
from django.utils import timezone


class PublishedManager(models.Manager):
    """Devuelve únicamente registros publicados con published_at <= ahora."""

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(status="published", published_at__lte=timezone.now())
        )


class FeaturedManager(models.Manager):
    """Devuelve solo destacados publicados."""

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(status="published", is_featured=True)
            .order_by("order")
        )
