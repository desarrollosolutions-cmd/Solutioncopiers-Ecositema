"""Señales Django para triggers automáticos de notificación."""
from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Quote, ServiceTicket

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Quote)
def on_quote_created(sender, instance: Quote, created: bool, **kwargs):
    """Envía email + WhatsApp al equipo cuando llega una nueva cotización."""
    if not created:
        return
    try:
        from .services import send_new_quote_email, send_whatsapp_quote_notification
        send_new_quote_email(instance)
        send_whatsapp_quote_notification(instance)
    except Exception as exc:
        logger.error("Error en on_quote_created signal: %s", exc)


@receiver(post_save, sender=ServiceTicket)
def on_ticket_resolved(sender, instance: ServiceTicket, created: bool, **kwargs):
    """Envía encuesta de satisfacción al cliente cuando el ticket se marca como resuelto."""
    if created:
        return
    if instance.status not in ("resolved", "closed"):
        return

    # Solo enviar si acaba de resolverse (resolved_at recién seteado)
    if not instance.resolved_at:
        return

    # Evitar reenviar si el ticket ya fue cerrado previamente: verificar que
    # resolved_at sea reciente (menos de 5 minutos), como proxy de "acaba de ocurrir"
    from django.utils import timezone
    from datetime import timedelta
    if (timezone.now() - instance.resolved_at) > timedelta(minutes=5):
        return

    try:
        from .services import send_ticket_survey_email
        send_ticket_survey_email(instance)
    except Exception as exc:
        logger.error("Error en on_ticket_resolved signal: %s", exc)
