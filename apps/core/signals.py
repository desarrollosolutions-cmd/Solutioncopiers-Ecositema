"""Signals globales del proyecto."""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


def generate_slug_on_save(sender, instance, **kwargs):
    """Pre-save: genera slug si está vacío."""
    if hasattr(instance, "_generate_unique_slug") and not instance.slug:
        instance.slug = instance._generate_unique_slug()


def set_published_at_on_publish(sender, instance, **kwargs):
    """Setea published_at automáticamente al publicar."""
    if not hasattr(instance, "status") or not hasattr(instance, "published_at"):
        return
    if instance.status == "published" and not instance.published_at:
        instance.published_at = timezone.now()
