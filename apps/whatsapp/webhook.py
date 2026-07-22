"""
Webhook de WhatsApp Cloud API (Meta).
En modo prototipo: solo persiste en DB, no llama a Meta.
Al activar producción: descomentar _send_to_meta() y configurar WHATSAPP_TOKEN.
"""
from __future__ import annotations

import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import WhatsAppConversation, WhatsAppMessage

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name="dispatch")
class WhatsAppWebhookView(View):
    """
    GET  /webhook/whatsapp/  → verificación de Meta (hub.challenge)
    POST /webhook/whatsapp/  → mensajes entrantes reales de Meta
    """

    def get(self, request):
        # Leído en tiempo de petición para que override_settings funcione en tests
        verify_token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", "prototipo_sc_2026")
        mode      = request.GET.get("hub.mode")
        token     = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if mode == "subscribe" and token == verify_token:
            logger.info("WhatsApp webhook verificado correctamente.")
            return HttpResponse(challenge, content_type="text/plain")
        return HttpResponse("Forbidden", status=403)

    def post(self, request):
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"error": "invalid json"}, status=400)

        try:
            _process_meta_payload(data)
        except Exception as exc:
            logger.exception("Error procesando payload de WhatsApp: %s", exc)

        # Meta requiere siempre 200 OK
        return JsonResponse({"status": "ok"})


def _process_meta_payload(data: dict):
    """Procesa el payload estándar de Meta Cloud API."""
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            contacts = {c["wa_id"]: c.get("profile", {}).get("name", "") for c in value.get("contacts", [])}

            for msg in messages:
                phone      = msg.get("from", "")
                wa_msg_id  = msg.get("id", "")
                msg_type   = msg.get("type", "text")
                body       = ""

                if msg_type == "text":
                    body = msg.get("text", {}).get("body", "")
                elif msg_type in ("image", "document", "audio", "video"):
                    body = f"[{msg_type.upper()}]"

                _upsert_inbound_message(
                    phone=phone,
                    contact_name=contacts.get(phone, ""),
                    wa_message_id=wa_msg_id,
                    body=body,
                    media_type=msg_type if msg_type in WhatsAppMessage.MediaType.values else "text",
                )


def _upsert_inbound_message(phone: str, contact_name: str,
                             wa_message_id: str, body: str, media_type: str = "text"):
    """Crea o reutiliza la conversación y agrega el mensaje entrante."""
    from apps.leads.models import Lead

    # Busca conversación activa (no resuelta ni spam)
    conv = (
        WhatsAppConversation.objects
        .filter(phone=phone)
        .exclude(status__in=[WhatsAppConversation.Status.RESOLVED, WhatsAppConversation.Status.SPAM])
        .order_by("-last_message_at")
        .first()
    )

    if not conv:
        # Intentar vincular a un Lead existente por teléfono
        lead = Lead.objects.filter(phone__icontains=phone.lstrip("+57").lstrip("57")).first()
        conv = WhatsAppConversation.objects.create(
            phone=phone,
            contact_name=contact_name or phone,
            lead=lead,
            status=WhatsAppConversation.Status.NEW,
        )
        logger.info("Nueva conversación WA creada: %s → lead=%s", phone, lead)

    elif contact_name and not conv.contact_name:
        conv.contact_name = contact_name
        conv.save(update_fields=["contact_name"])

    WhatsAppMessage.objects.create(
        conversation=conv,
        direction=WhatsAppMessage.Direction.INBOUND,
        wa_message_id=wa_message_id,
        body=body,
        media_type=media_type,
        status=WhatsAppMessage.MsgStatus.DELIVERED,
    )
    return conv


# ---------------------------------------------------------------------------
# Función pública: enviar mensaje saliente
# En prototipo solo guarda en DB. Con API real: llama a Meta.
# ---------------------------------------------------------------------------
def send_whatsapp_message(conversation: WhatsAppConversation,
                          body: str, sent_by) -> WhatsAppMessage:
    """
    Envía (o simula enviar) un mensaje saliente.
    Para activar la API real: configurar WHATSAPP_TOKEN y WHATSAPP_PHONE_ID en settings.
    """
    msg = WhatsAppMessage.objects.create(
        conversation=conversation,
        direction=WhatsAppMessage.Direction.OUTBOUND,
        body=body,
        sent_by=sent_by,
        status=WhatsAppMessage.MsgStatus.SENT,
    )

    token    = getattr(settings, "WHATSAPP_TOKEN", "")
    phone_id = getattr(settings, "WHATSAPP_PHONE_ID", "")

    if token and phone_id:
        _send_to_meta(conversation.phone, body, token, phone_id, msg)

    return msg


def _send_to_meta(to_phone: str, body: str,
                  token: str, phone_id: str,
                  msg: WhatsAppMessage):
    """Llama a Meta Cloud API — solo se ejecuta cuando hay token configurado."""
    import urllib.request
    payload = json.dumps({
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": body},
    }).encode()
    req = urllib.request.Request(
        f"https://graph.facebook.com/v19.0/{phone_id}/messages",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            result = json.loads(resp.read())
            wa_id = result.get("messages", [{}])[0].get("id", "")
            if wa_id:
                msg.wa_message_id = wa_id
                msg.status = WhatsAppMessage.MsgStatus.SENT
                msg.save(update_fields=["wa_message_id", "status"])
    except Exception as exc:
        logger.error("Error enviando a Meta API: %s", exc)
        msg.status = WhatsAppMessage.MsgStatus.FAILED
        msg.save(update_fields=["status"])
