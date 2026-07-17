"""Modelos del módulo WhatsApp CRM."""
from __future__ import annotations

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class ConversationLabel(TimeStampedModel):
    """Etiquetas para clasificar conversaciones (ej: Cotización, Soporte, Postventa)."""

    name       = models.CharField(_("nombre"), max_length=60)
    color      = models.CharField(_("color"), max_length=7, default="#3B82F6",
                                  help_text="Código hex, ej: #3B82F6")
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="wa_labels",
        verbose_name=_("creada por"),
    )

    class Meta:
        verbose_name        = _("Etiqueta de conversación")
        verbose_name_plural = _("Etiquetas de conversación")
        ordering            = ["name"]

    def __str__(self):
        return self.name


class WhatsAppConversation(TimeStampedModel):
    """Una conversación de WhatsApp vinculada a un Lead y una asesora."""

    class Status(models.TextChoices):
        NEW      = "new",      _("Nueva")
        OPEN     = "open",     _("Abierta")
        PENDING  = "pending",  _("Pendiente")
        RESOLVED = "resolved", _("Resuelta")
        SPAM     = "spam",     _("Spam")

    # Contacto WhatsApp
    phone          = models.CharField(_("teléfono WA"), max_length=30, db_index=True)
    contact_name   = models.CharField(_("nombre del contacto"), max_length=150, blank=True)
    wa_contact_id  = models.CharField(_("WA contact ID"), max_length=100, blank=True,
                                      help_text="ID interno de Meta — se completa con API real")

    # Vínculo con CRM
    lead = models.ForeignKey(
        "leads.Lead", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="wa_conversations",
        verbose_name=_("cliente CRM"),
    )
    assigned_to = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="wa_conversations",
        verbose_name=_("asesora asignada"),
    )

    # Estado y etiquetas
    status  = models.CharField(_("estado"), max_length=15,
                               choices=Status.choices, default=Status.NEW, db_index=True)
    labels  = models.ManyToManyField(ConversationLabel, blank=True,
                                     verbose_name=_("etiquetas"))

    # Preview rápido (se actualiza en cada mensaje)
    last_message_at      = models.DateTimeField(_("último mensaje"), null=True, blank=True)
    last_message_preview = models.CharField(_("preview"), max_length=200, blank=True)
    unread_count         = models.PositiveSmallIntegerField(_("sin leer"), default=0)

    class Meta:
        verbose_name        = _("Conversación WhatsApp")
        verbose_name_plural = _("Conversaciones WhatsApp")
        ordering            = ["-last_message_at"]

    def __str__(self):
        name = self.contact_name or self.phone
        return f"{name} [{self.get_status_display()}]"

    def mark_read(self):
        self.unread_count = 0
        self.save(update_fields=["unread_count"])


class WhatsAppMessage(TimeStampedModel):
    """Mensaje individual dentro de una conversación WhatsApp."""

    class Direction(models.TextChoices):
        INBOUND  = "inbound",  _("Entrante")
        OUTBOUND = "outbound", _("Saliente")

    class MsgStatus(models.TextChoices):
        PENDING   = "pending",   _("Pendiente")
        SENT      = "sent",      _("Enviado")
        DELIVERED = "delivered", _("Entregado")
        READ      = "read",      _("Leído")
        FAILED    = "failed",    _("Fallido")

    class MediaType(models.TextChoices):
        TEXT     = "text",     _("Texto")
        IMAGE    = "image",    _("Imagen")
        DOCUMENT = "document", _("Documento")
        AUDIO    = "audio",    _("Audio")
        VIDEO    = "video",    _("Video")
        STICKER  = "sticker",  _("Sticker")

    conversation  = models.ForeignKey(
        WhatsAppConversation, on_delete=models.CASCADE,
        related_name="messages", verbose_name=_("conversación"),
    )
    direction     = models.CharField(_("dirección"), max_length=10,
                                     choices=Direction.choices, default=Direction.INBOUND)
    wa_message_id = models.CharField(_("WA message ID"), max_length=100,
                                     blank=True, unique=False,
                                     help_text="ID de Meta — vacío en modo prototipo")
    body          = models.TextField(_("texto"), blank=True)
    media_type    = models.CharField(_("tipo"), max_length=12,
                                     choices=MediaType.choices, default=MediaType.TEXT)
    media_url     = models.CharField(_("URL de archivo"), max_length=500, blank=True)
    sent_by       = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="wa_messages_sent",
        verbose_name=_("enviado por"),
    )
    status = models.CharField(_("estado"), max_length=12,
                              choices=MsgStatus.choices, default=MsgStatus.SENT)

    class Meta:
        verbose_name        = _("Mensaje WhatsApp")
        verbose_name_plural = _("Mensajes WhatsApp")
        ordering            = ["created_at"]

    def __str__(self):
        return f"[{self.direction}] {self.body[:60]}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Actualizar preview y timestamp en la conversación
        conv = self.conversation
        conv.last_message_at      = self.created_at or timezone.now()
        conv.last_message_preview = self.body[:120]
        if self.direction == self.Direction.INBOUND:
            conv.unread_count = models.F("unread_count") + 1
        conv.save(update_fields=["last_message_at", "last_message_preview", "unread_count"])
