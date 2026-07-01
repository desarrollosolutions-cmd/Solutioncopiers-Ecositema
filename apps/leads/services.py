"""Capa de servicios del módulo Leads."""
from __future__ import annotations

import logging
import threading
import urllib.parse
import urllib.request
from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from apps.catalog.models import Copier
from .models import EmailLog, Lead, Quote, QuoteItem

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# EMAIL NOTIFICATIONS
# ---------------------------------------------------------------------------

def _build_dashboard_url(path: str) -> str:
    base = getattr(settings, "SITE_URL", "https://solutioncopiers.com")
    return f"{base}{path}"


def _send_email_async(
    subject: str,
    html_content: str,
    to: list[str],
    lead=None,
) -> None:
    """Envía un email HTML en hilo separado y registra el resultado en EmailLog."""
    def _send():
        try:
            text_content = strip_tags(html_content)
            from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@solutioncopiers.com")
            msg = EmailMultiAlternatives(subject, text_content, from_email, to)
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            logger.info("Email enviado a %s — %s", to, subject[:60])
            for addr in to:
                EmailLog.objects.create(
                    lead=lead, subject=subject[:300], recipient=addr,
                    status=EmailLog.Status.SENT,
                )
        except Exception as exc:
            logger.error("Error enviando email a %s: %s", to, exc)
            for addr in to:
                try:
                    EmailLog.objects.create(
                        lead=lead, subject=subject[:300], recipient=addr,
                        status=EmailLog.Status.FAILED, error_msg=str(exc)[:500],
                    )
                except Exception:
                    pass

    threading.Thread(target=_send, daemon=True).start()


def send_new_quote_email(quote: Quote) -> None:
    """Notifica al equipo de ventas cuando llega una nueva cotización."""
    notify_email = getattr(settings, "LEADS_NOTIFICATION_EMAIL", "")
    if not notify_email:
        logger.info("send_new_quote_email omitida — configura LEADS_NOTIFICATION_EMAIL en .env")
        return

    ctx = {
        "quote": quote,
        "dashboard_url": _build_dashboard_url(f"/dashadmin/cotizaciones/{quote.pk}/"),
    }
    html = render_to_string("leads/emails/new_quote.html", ctx)
    subject = f"🔔 Nueva cotización — {quote.lead.full_name} ({quote.get_interest_area_display()})"
    _send_email_async(subject, html, [notify_email])


def send_followup_email(quote: Quote, days_pending: int) -> None:
    """Alerta interna cuando una cotización lleva X días sin atender."""
    notify_email = getattr(settings, "LEADS_NOTIFICATION_EMAIL", "")
    if not notify_email:
        return

    ctx = {
        "quote": quote,
        "days_pending": days_pending,
        "dashboard_url": _build_dashboard_url(f"/dashadmin/cotizaciones/{quote.pk}/"),
    }
    html = render_to_string("leads/emails/followup.html", ctx)
    subject = f"⏳ Seguimiento pendiente — {quote.lead.full_name} ({days_pending} días)"
    _send_email_async(subject, html, [notify_email])


def send_contract_expiry_email(contract, days_left: int) -> None:
    """Alerta interna de contrato próximo a vencer."""
    notify_email = getattr(settings, "LEADS_NOTIFICATION_EMAIL", "")
    if not notify_email:
        return

    ctx = {
        "contract": contract,
        "days_left": days_left,
        "dashboard_url": _build_dashboard_url(f"/dashadmin/contratos/{contract.pk}/"),
    }
    html = render_to_string("leads/emails/contract_expiry.html", ctx)
    subject = f"📋 Contrato por vencer — {contract.lead.full_name} ({days_left} días)"
    _send_email_async(subject, html, [notify_email])


def send_contact_message_email(form_data: dict) -> None:
    """Notifica al equipo cuando alguien envía el formulario de /contacto/."""
    notify_email = getattr(settings, "LEADS_NOTIFICATION_EMAIL", "")
    if not notify_email:
        logger.info("send_contact_message_email omitida — configura LEADS_NOTIFICATION_EMAIL en .env")
        return

    subject = f"📬 Mensaje de contacto — {form_data['full_name']} · {form_data['subject']}"
    lines = [
        f"<b>Nombre:</b> {form_data['full_name']}",
        f"<b>Email:</b> {form_data['email']}",
        f"<b>Teléfono:</b> {form_data.get('phone', '—')}",
        f"<b>Empresa:</b> {form_data.get('company_name') or '—'}",
        f"<b>Asunto:</b> {form_data['subject']}",
        "",
        f"<b>Mensaje:</b><br>{form_data['message'].replace(chr(10), '<br>')}",
    ]
    html = (
        "<div style='font-family:sans-serif;max-width:600px'>"
        + "<br>".join(lines)
        + "</div>"
    )
    _send_email_async(subject, html, [notify_email])


def send_ticket_survey_email(ticket) -> None:
    """Envía encuesta de satisfacción al cliente cuando se resuelve un ticket."""
    client_email = ticket.lead.email
    if not client_email:
        return

    survey_url = _build_dashboard_url("/encuesta/servicio/")
    ctx = {
        "ticket": ticket,
        "survey_url": survey_url,
    }
    html = render_to_string("leads/emails/ticket_survey.html", ctx)
    subject = f"⭐ ¿Cómo fue tu experiencia? — Ticket {ticket.ticket_number}"
    _send_email_async(subject, html, [client_email])


class QuoteCalculator:
    """Calcula estimaciones rápidas."""

    @staticmethod
    def calculate_rental(wizard_data):
        copier_id = wizard_data.get("copier_id")
        quantity = int(wizard_data.get("quantity", 1) or 1)
        monthly_pages = int(wizard_data.get("monthly_pages", 0) or 0)

        if not copier_id:
            return Decimal("0")

        try:
            copier = Copier.objects.get(pk=copier_id)
        except Copier.DoesNotExist:
            return Decimal("0")

        base = (copier.monthly_rental_price or Decimal("0")) * quantity
        extra_pages = max(0, monthly_pages - (copier.pages_included_monthly * quantity))
        extra_cost = extra_pages * (copier.extra_page_cost or Decimal("0"))
        return base + extra_cost

    @staticmethod
    def calculate_cabling(wizard_data):
        points_logical = int(wizard_data.get("logical_points", 0) or 0)
        points_electrical = int(wizard_data.get("electrical_points", 0) or 0)
        price_logical = Decimal("180000")
        price_electrical = Decimal("220000")
        return (points_logical * price_logical) + (points_electrical * price_electrical)

    @staticmethod
    def calculate_software(wizard_data):
        complexity = wizard_data.get("complexity", "medium")
        ranges = {
            "low": Decimal("8000000"),
            "medium": Decimal("25000000"),
            "high": Decimal("60000000"),
            "enterprise": Decimal("150000000"),
        }
        return ranges.get(complexity, Decimal("0"))

    @staticmethod
    def calculate_consumables(wizard_data):
        """Estimación basada en precio unitario × cantidad cuando hay producto seleccionado."""
        from decimal import Decimal
        try:
            unit_price = Decimal(str(wizard_data.get("consumable_unit_price") or 0))
        except Exception:
            unit_price = Decimal("0")
        qty = int(wizard_data.get("consumable_qty", 1) or 1)
        return unit_price * qty if unit_price > 0 else Decimal("0")

    @classmethod
    def calculate(cls, interest_area, wizard_data):
        dispatcher = {
            "rental": cls.calculate_rental,
            "sale": cls.calculate_rental,
            "consumables": cls.calculate_consumables,
            "cabling": cls.calculate_cabling,
            "software": cls.calculate_software,
            "web": cls.calculate_software,
            "mobile": cls.calculate_software,
            "database": cls.calculate_software,
            "full_office": cls.calculate_software,
        }
        calculator = dispatcher.get(interest_area)
        if not calculator:
            return Decimal("0")
        return calculator(wizard_data)


class LeadCreator:
    """Orquesta creación atómica de Lead + Quote."""

    @staticmethod
    def create_from_wizard(contact_data, quote_data, wizard_data):
        from django.db import transaction

        with transaction.atomic():
            lead, _ = Lead.objects.get_or_create(
                email=contact_data["email"],
                defaults=contact_data,
            )

            interest_area = quote_data.get("interest_area")
            estimated_total = QuoteCalculator.calculate(interest_area, wizard_data)

            quote = Quote.objects.create(
                lead=lead,
                interest_area=interest_area,
                wizard_data=wizard_data,
                estimated_total=estimated_total,
                client_message=quote_data.get("client_message", ""),
            )

            LeadCreator._create_quote_items(quote, wizard_data)

        return quote

    @staticmethod
    def _create_quote_items(quote, wizard_data):
        copier_id = wizard_data.get("copier_id")
        if copier_id:
            try:
                copier = Copier.objects.get(pk=copier_id)
                QuoteItem.objects.create(
                    quote=quote,
                    content_type=ContentType.objects.get_for_model(Copier),
                    object_id=copier.pk,
                    item_name=str(copier),
                    item_description=copier.short_description,
                    quantity=int(wizard_data.get("quantity", 1) or 1),
                    unit_price=copier.monthly_rental_price,
                )
            except Copier.DoesNotExist:
                pass


def send_whatsapp_quote_notification(quote: Quote) -> None:
    """
    Envía notificación automática de nueva cotización al WhatsApp del negocio.

    Usa CallMeBot — servicio de notificaciones 1-a-1, sin riesgo de baneo.

    ACTIVACIÓN (solo una vez):
    1. Abre WhatsApp y envía este mensaje al número +34 644 71 78 24:
       "I allow callmebot to send me messages"
    2. CallMeBot te responderá con tu APIKEY personal.
    3. Agrega al archivo .env:
       CALLMEBOT_APIKEY=tu_apikey
       WHATSAPP_NOTIFY_PHONE=+573001234567  (con código de país)

    Corre en un hilo separado para no bloquear la respuesta al cliente.
    """
    apikey = getattr(settings, "CALLMEBOT_APIKEY", "")
    phone  = getattr(settings, "WHATSAPP_NOTIFY_PHONE", "")

    if not apikey or not phone:
        logger.info(
            "WhatsApp notification omitida — configura CALLMEBOT_APIKEY y "
            "WHATSAPP_NOTIFY_PHONE en .env para activarla."
        )
        return

    def _send():
        lead    = quote.lead
        wizard  = quote.wizard_data or {}
        total   = float(quote.estimated_total or 0)
        area    = quote.get_interest_area_display()

        lineas = [
            "🔔 *NUEVA COTIZACIÓN — Solution Copiers*",
            "",
            f"👤 *Cliente:* {lead.full_name}",
            f"🏢 *Empresa:* {lead.company_name or 'Particular'}",
            f"📱 *Teléfono:* {lead.phone}",
            f"📧 *Email:* {lead.email}",
            f"🌆 *Ciudad:* {lead.city}",
            "",
            f"📋 *Servicio:* {area}",
        ]

        if total > 0:
            lineas.append(f"💰 *Estimado:* ${total:,.0f} COP")

        # Detalle según tipo de cotización
        if quote.interest_area in ("rental", "sale"):
            qty = wizard.get("quantity", 1)
            pages = wizard.get("monthly_pages", 0)
            if qty:   lineas.append(f"🖨️ *Equipos:* {qty} unidad(es)")
            if pages: lineas.append(f"📄 *Páginas/mes:* {int(pages):,}")

        elif quote.interest_area == "consumables":
            product = wizard.get("consumable_product_name") or wizard.get("equipment_model")
            qty     = wizard.get("consumable_qty", 1)
            if product: lineas.append(f"🖨️ *Producto:* {product}")
            if qty:     lineas.append(f"📦 *Cantidad:* {qty} unidad(es)")

        elif quote.interest_area == "cabling":
            lp = wizard.get("logical_points", 0)
            ep = wizard.get("electrical_points", 0)
            if lp: lineas.append(f"🔌 *Puntos lógicos:* {lp}")
            if ep: lineas.append(f"⚡ *Puntos eléctricos:* {ep}")

        elif quote.interest_area in ("software", "web", "mobile", "database"):
            complejidad = wizard.get("complexity", "")
            desc = (wizard.get("project_description") or "")[:120]
            if complejidad: lineas.append(f"⚙️ *Complejidad:* {complejidad}")
            if desc:        lineas.append(f"📝 *Descripción:* {desc}…")

        if quote.client_message:
            lineas.append(f"💬 *Mensaje:* {quote.client_message[:150]}")

        lineas += [
            "",
            f"🆔 ID: {str(quote.public_id)[:8].upper()}",
            f"👉 Responde a este número: {lead.phone}",
        ]

        mensaje = "\n".join(lineas)
        phone_clean = phone.replace("+", "").replace(" ", "")
        url = (
            "https://api.callmebot.com/whatsapp.php"
            f"?phone={phone_clean}"
            f"&text={urllib.parse.quote(mensaje)}"
            f"&apikey={apikey}"
        )

        try:
            with urllib.request.urlopen(url, timeout=8) as resp:
                resultado = resp.read().decode("utf-8", errors="ignore")
                logger.info(
                    "WhatsApp enviado para cotización %s: %s",
                    quote.public_id, resultado[:80]
                )
        except Exception as exc:
            logger.warning("Error enviando WhatsApp: %s", exc)

    # Ejecutar en hilo separado — no bloquea la respuesta HTTP al cliente
    threading.Thread(target=_send, daemon=True).start()
