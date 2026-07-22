"""
Suite de pruebas para el módulo WhatsApp CRM.

Cubre:
  1. Modelos — creación, propiedades, señales de save()
  2. Webhook — verificación Meta (GET), procesamiento payload (POST)
  3. Función _upsert_inbound_message — vinculación automática a Lead
  4. send_whatsapp_message — modo prototipo (sin token)
  5. Vistas del panel — inbox, detalle, simulador (requieren login)
  6. Vistas dashadmin — overview, etiquetas, asignación
  7. Control de acceso — anónimo, técnico de campo, asesora
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.leads.models import Lead
from apps.whatsapp.models import ConversationLabel, WhatsAppConversation, WhatsAppMessage
from apps.whatsapp.webhook import _upsert_inbound_message, send_whatsapp_message

User = get_user_model()


# ===========================================================================
# FIXTURES COMUNES
# ===========================================================================

def make_asesora(username="asesora1", password="test1234"):
    """Crea un usuario asesora (staff=False, no field_profile)."""
    u = User.objects.create_user(username=username, password=password, is_staff=False)
    return u


def make_admin(username="admin1", password="test1234"):
    u = User.objects.create_user(username=username, password=password, is_staff=True, is_superuser=True)
    return u


def make_lead(phone="573001234567", name="Cliente Test"):
    return Lead.objects.create(full_name=name, phone=phone)


def make_conversation(phone="573001234567", name="Test", asesora=None, status="new"):
    return WhatsAppConversation.objects.create(
        phone=phone,
        contact_name=name,
        assigned_to=asesora,
        status=status,
    )


def make_message(conv, body="Hola", direction="inbound"):
    return WhatsAppMessage.objects.create(
        conversation=conv,
        direction=direction,
        body=body,
        status="delivered" if direction == "inbound" else "sent",
    )


# ===========================================================================
# 1. MODELOS
# ===========================================================================

class ConversationLabelModelTest(TestCase):

    def test_create_label(self):
        lbl = ConversationLabel.objects.create(name="Cotización", color="#25D366")
        self.assertEqual(str(lbl), "Cotización")
        self.assertEqual(lbl.color, "#25D366")

    def test_default_color(self):
        lbl = ConversationLabel.objects.create(name="Soporte")
        self.assertEqual(lbl.color, "#3B82F6")


class WhatsAppConversationModelTest(TestCase):

    def test_create_conversation(self):
        conv = make_conversation()
        self.assertEqual(conv.status, "new")
        self.assertEqual(conv.unread_count, 0)
        self.assertIn("Test", str(conv))

    def test_mark_read_resets_counter(self):
        conv = make_conversation()
        conv.unread_count = 5
        conv.save()
        conv.mark_read()
        conv.refresh_from_db()
        self.assertEqual(conv.unread_count, 0)

    def test_str_uses_contact_name(self):
        conv = make_conversation(name="Carlos Gómez")
        self.assertIn("Carlos Gómez", str(conv))

    def test_str_falls_back_to_phone(self):
        conv = WhatsAppConversation.objects.create(phone="573009999999", contact_name="")
        self.assertIn("573009999999", str(conv))

    def test_labels_many_to_many(self):
        conv = make_conversation()
        lbl1 = ConversationLabel.objects.create(name="A")
        lbl2 = ConversationLabel.objects.create(name="B")
        conv.labels.add(lbl1, lbl2)
        self.assertEqual(conv.labels.count(), 2)

    def test_lead_link(self):
        lead = make_lead()
        conv = make_conversation()
        conv.lead = lead
        conv.save()
        self.assertEqual(conv.lead.full_name, "Cliente Test")


class WhatsAppMessageModelTest(TestCase):

    def setUp(self):
        self.conv = make_conversation()

    def test_inbound_message_increments_unread(self):
        make_message(self.conv, direction="inbound")
        self.conv.refresh_from_db()
        self.assertEqual(self.conv.unread_count, 1)

    def test_two_inbound_messages_increment_twice(self):
        make_message(self.conv, direction="inbound")
        make_message(self.conv, direction="inbound")
        self.conv.refresh_from_db()
        self.assertEqual(self.conv.unread_count, 2)

    def test_outbound_does_not_increment_unread(self):
        make_message(self.conv, direction="outbound")
        self.conv.refresh_from_db()
        self.assertEqual(self.conv.unread_count, 0)

    def test_message_updates_preview(self):
        make_message(self.conv, body="Mensaje de prueba", direction="inbound")
        self.conv.refresh_from_db()
        self.assertEqual(self.conv.last_message_preview, "Mensaje de prueba")

    def test_message_updates_last_message_at(self):
        self.assertIsNone(self.conv.last_message_at)
        make_message(self.conv, direction="inbound")
        self.conv.refresh_from_db()
        self.assertIsNotNone(self.conv.last_message_at)

    def test_preview_truncated_to_120_chars(self):
        long_body = "x" * 200
        make_message(self.conv, body=long_body, direction="inbound")
        self.conv.refresh_from_db()
        self.assertEqual(len(self.conv.last_message_preview), 120)

    def test_str_representation(self):
        msg = make_message(self.conv, body="Hola mundo")
        self.assertIn("Hola mundo", str(msg))
        self.assertIn("inbound", str(msg))


# ===========================================================================
# 2. WEBHOOK — verificación Meta (GET)
# ===========================================================================

class WebhookVerificationTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse("wa:webhook")

    @override_settings(WHATSAPP_VERIFY_TOKEN="token_prueba")
    def test_valid_verification_returns_challenge(self):
        resp = self.client.get(self.url, {
            "hub.mode":         "subscribe",
            "hub.verify_token": "token_prueba",
            "hub.challenge":    "RETO123",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b"RETO123")

    @override_settings(WHATSAPP_VERIFY_TOKEN="token_prueba")
    def test_wrong_token_returns_403(self):
        resp = self.client.get(self.url, {
            "hub.mode":         "subscribe",
            "hub.verify_token": "token_incorrecto",
            "hub.challenge":    "RETO123",
        })
        self.assertEqual(resp.status_code, 403)

    def test_missing_params_returns_403(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403)


# ===========================================================================
# 3. WEBHOOK — procesamiento de mensajes entrantes (POST)
# ===========================================================================

class WebhookPostTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse("wa:webhook")

    def _post_payload(self, payload: dict):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def _meta_payload(self, phone="573001234567", name="Juan Pérez", body="Hola"):
        return {
            "entry": [{
                "changes": [{
                    "value": {
                        "contacts": [{"wa_id": phone, "profile": {"name": name}}],
                        "messages": [{
                            "from": phone,
                            "id":   f"wamid.{phone}",
                            "type": "text",
                            "text": {"body": body},
                        }],
                    }
                }]
            }]
        }

    def test_valid_payload_returns_200(self):
        resp = self._post_payload(self._meta_payload())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})

    def test_creates_conversation_and_message(self):
        self._post_payload(self._meta_payload(phone="573001111111", body="Necesito info"))
        conv = WhatsAppConversation.objects.get(phone="573001111111")
        self.assertEqual(conv.contact_name, "Juan Pérez")
        self.assertEqual(conv.messages.count(), 1)
        self.assertEqual(conv.messages.first().body, "Necesito info")

    def test_second_message_reuses_conversation(self):
        phone = "573002222222"
        self._post_payload(self._meta_payload(phone=phone, body="Primer mensaje"))
        self._post_payload(self._meta_payload(phone=phone, body="Segundo mensaje"))
        self.assertEqual(WhatsAppConversation.objects.filter(phone=phone).count(), 1)
        conv = WhatsAppConversation.objects.get(phone=phone)
        self.assertEqual(conv.messages.count(), 2)

    def test_resolved_conversation_opens_new_one(self):
        phone = "573003333333"
        old_conv = WhatsAppConversation.objects.create(phone=phone, status="resolved")
        self._post_payload(self._meta_payload(phone=phone, body="Nueva consulta"))
        # Debe haber creado una segunda conversación (la resuelta se ignora)
        self.assertEqual(WhatsAppConversation.objects.filter(phone=phone).count(), 2)

    def test_invalid_json_returns_400(self):
        resp = self.client.post(self.url, data="no es json", content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_empty_entry_does_not_crash(self):
        resp = self._post_payload({"entry": []})
        self.assertEqual(resp.status_code, 200)

    def test_image_message_sets_correct_type(self):
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "contacts": [],
                        "messages": [{
                            "from": "573004444444",
                            "id":   "wamid.img1",
                            "type": "image",
                            "image": {"id": "img123"},
                        }],
                    }
                }]
            }]
        }
        self._post_payload(payload)
        msg = WhatsAppMessage.objects.filter(conversation__phone="573004444444").first()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.media_type, "image")


# ===========================================================================
# 4. _upsert_inbound_message — vinculación automática a Lead
# ===========================================================================

class UpsertInboundMessageTest(TestCase):

    def test_links_to_existing_lead_by_phone(self):
        # Lead con teléfono colombiano sin prefijo
        lead = Lead.objects.create(full_name="Ana García", phone="3009876543")
        conv = _upsert_inbound_message(
            phone="573009876543",
            contact_name="Ana",
            wa_message_id="",
            body="Hola",
        )
        self.assertIsNotNone(conv.lead)
        self.assertEqual(conv.lead.pk, lead.pk)

    def test_no_lead_creates_unlinked_conversation(self):
        conv = _upsert_inbound_message(
            phone="573008888888",
            contact_name="Desconocido",
            wa_message_id="",
            body="Info por favor",
        )
        self.assertIsNone(conv.lead)
        self.assertEqual(conv.status, "new")

    def test_sets_contact_name_on_first_message(self):
        conv = _upsert_inbound_message(
            phone="573007777777",
            contact_name="Pedro Ramírez",
            wa_message_id="",
            body="Buenos días",
        )
        self.assertEqual(conv.contact_name, "Pedro Ramírez")

    def test_updates_blank_contact_name(self):
        existing = WhatsAppConversation.objects.create(phone="573006666666", contact_name="")
        conv = _upsert_inbound_message(
            phone="573006666666",
            contact_name="Nuevo Nombre",
            wa_message_id="",
            body="Hola de nuevo",
        )
        conv.refresh_from_db()
        self.assertEqual(conv.contact_name, "Nuevo Nombre")

    def test_returns_same_conversation_on_repeat(self):
        c1 = _upsert_inbound_message("573005555555", "X", "", "msg1")
        c2 = _upsert_inbound_message("573005555555", "X", "", "msg2")
        self.assertEqual(c1.pk, c2.pk)


# ===========================================================================
# 5. send_whatsapp_message — modo prototipo
# ===========================================================================

class SendWhatsAppMessageTest(TestCase):

    def setUp(self):
        self.asesora = make_asesora()
        self.conv = make_conversation(asesora=self.asesora)

    @override_settings(WHATSAPP_TOKEN="", WHATSAPP_PHONE_ID="")
    def test_prototype_saves_message_to_db(self):
        msg = send_whatsapp_message(self.conv, "Hola desde el ERP", self.asesora)
        self.assertEqual(msg.direction, "outbound")
        self.assertEqual(msg.body, "Hola desde el ERP")
        self.assertEqual(msg.sent_by, self.asesora)
        self.assertEqual(msg.status, "sent")

    @override_settings(WHATSAPP_TOKEN="", WHATSAPP_PHONE_ID="")
    def test_prototype_does_not_call_meta_api(self):
        with patch("apps.whatsapp.webhook._send_to_meta") as mock_send:
            send_whatsapp_message(self.conv, "Test", self.asesora)
            mock_send.assert_not_called()

    @override_settings(WHATSAPP_TOKEN="TOKEN_REAL", WHATSAPP_PHONE_ID="12345")
    def test_with_token_calls_meta_api(self):
        with patch("apps.whatsapp.webhook._send_to_meta") as mock_send:
            send_whatsapp_message(self.conv, "Test real", self.asesora)
            mock_send.assert_called_once()

    @override_settings(WHATSAPP_TOKEN="", WHATSAPP_PHONE_ID="")
    def test_outbound_updates_conversation_preview(self):
        send_whatsapp_message(self.conv, "Respuesta del equipo", self.asesora)
        self.conv.refresh_from_db()
        self.assertEqual(self.conv.last_message_preview, "Respuesta del equipo")


# ===========================================================================
# 6. VISTAS DEL PANEL — control de acceso y comportamiento básico
# ===========================================================================

class PanelWAAccessTest(TestCase):

    def setUp(self):
        self.client   = Client()
        self.asesora  = make_asesora()
        self.inbox_url = reverse("wa:panel_inbox")
        self.sim_url   = reverse("wa:simulator")

    def test_anonymous_redirects_to_login(self):
        resp = self.client.get(self.inbox_url)
        self.assertIn("/acceso/", resp["Location"])

    def test_asesora_can_access_inbox(self):
        self.client.login(username="asesora1", password="test1234")
        resp = self.client.get(self.inbox_url)
        self.assertEqual(resp.status_code, 200)

    def test_asesora_can_access_simulator(self):
        self.client.login(username="asesora1", password="test1234")
        resp = self.client.get(self.sim_url)
        self.assertEqual(resp.status_code, 200)

    def test_inbox_shows_assigned_conversations(self):
        self.client.login(username="asesora1", password="test1234")
        conv = make_conversation(asesora=self.asesora, name="Mi cliente")
        resp = self.client.get(self.inbox_url)
        self.assertContains(resp, "Mi cliente")

    def test_inbox_mine_filter_hides_others(self):
        other = make_asesora("otra_asesora")
        self.client.login(username="asesora1", password="test1234")
        conv_other = make_conversation(asesora=other, name="Cliente de otra")
        resp = self.client.get(self.inbox_url + "?mine=1")
        self.assertNotContains(resp, "Cliente de otra")

    def test_inbox_mine_0_shows_all(self):
        other = make_asesora("otra2")
        self.client.login(username="asesora1", password="test1234")
        make_conversation(asesora=other, name="Cliente visible")
        resp = self.client.get(self.inbox_url + "?mine=0")
        self.assertContains(resp, "Cliente visible")


class PanelWAConversationViewTest(TestCase):

    def setUp(self):
        self.client  = Client()
        self.asesora = make_asesora()
        self.conv    = make_conversation(asesora=self.asesora, name="Pedro")
        self.url     = reverse("wa:panel_conversation", args=[self.conv.pk])
        self.client.login(username="asesora1", password="test1234")

    def test_get_shows_conversation(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Pedro")

    def test_get_marks_conversation_as_read(self):
        self.conv.unread_count = 3
        self.conv.save()
        self.client.get(self.url)
        self.conv.refresh_from_db()
        self.assertEqual(self.conv.unread_count, 0)

    def test_post_reply_creates_outbound_message(self):
        self.client.post(self.url, {"action": "reply", "body": "Hola Pedro"})
        msg = self.conv.messages.filter(direction="outbound").first()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.body, "Hola Pedro")
        self.assertEqual(msg.sent_by, self.asesora)

    def test_post_empty_reply_does_not_create_message(self):
        self.client.post(self.url, {"action": "reply", "body": "   "})
        self.assertEqual(self.conv.messages.count(), 0)

    def test_post_set_status(self):
        self.client.post(self.url, {"action": "set_status", "status": "open"})
        self.conv.refresh_from_db()
        self.assertEqual(self.conv.status, "open")

    def test_post_invalid_status_ignored(self):
        self.client.post(self.url, {"action": "set_status", "status": "INVALIDO"})
        self.conv.refresh_from_db()
        self.assertEqual(self.conv.status, "new")

    def test_post_assign(self):
        otra = make_asesora("otra3")
        self.client.post(self.url, {"action": "assign", "assigned_to": otra.pk})
        self.conv.refresh_from_db()
        self.assertEqual(self.conv.assigned_to, otra)

    def test_post_assign_empty_clears_assignee(self):
        self.client.post(self.url, {"action": "assign", "assigned_to": ""})
        self.conv.refresh_from_db()
        self.assertIsNone(self.conv.assigned_to)

    def test_post_set_labels(self):
        lbl = ConversationLabel.objects.create(name="VIP")
        self.client.post(self.url, {"action": "set_labels", "labels": [lbl.pk]})
        self.assertIn(lbl, self.conv.labels.all())

    def test_post_set_labels_empty_clears_all(self):
        lbl = ConversationLabel.objects.create(name="VIP2")
        self.conv.labels.add(lbl)
        self.client.post(self.url, {"action": "set_labels"})
        self.assertEqual(self.conv.labels.count(), 0)

    def test_post_link_lead(self):
        lead = make_lead()
        self.client.post(self.url, {"action": "link_lead", "lead_id": lead.pk})
        self.conv.refresh_from_db()
        self.assertEqual(self.conv.lead, lead)

    def test_shows_existing_messages(self):
        make_message(self.conv, body="Mensaje previo")
        resp = self.client.get(self.url)
        self.assertContains(resp, "Mensaje previo")


class PanelWASimulatorTest(TestCase):

    def setUp(self):
        self.client  = Client()
        self.asesora = make_asesora()
        self.url     = reverse("wa:simulator")
        self.client.login(username="asesora1", password="test1234")

    def test_get_renders_form(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Simular")

    def test_post_creates_conversation_and_redirects(self):
        resp = self.client.post(self.url, {
            "phone":        "573001234567",
            "contact_name": "Test Sim",
            "body":         "Mensaje de prueba",
        })
        self.assertEqual(resp.status_code, 302)
        conv = WhatsAppConversation.objects.get(phone="573001234567")
        self.assertEqual(conv.contact_name, "Test Sim")
        self.assertEqual(conv.messages.count(), 1)

    def test_post_without_body_redirects_to_simulator(self):
        resp = self.client.post(self.url, {"phone": "573001234567", "body": ""})
        self.assertRedirects(resp, self.url)
        self.assertEqual(WhatsAppConversation.objects.count(), 0)

    def test_post_links_to_existing_lead(self):
        lead = Lead.objects.create(full_name="Sim Cliente", phone="3001234567")
        self.client.post(self.url, {
            "phone":        "573001234567",
            "contact_name": "Sim",
            "body":         "Hola",
        })
        conv = WhatsAppConversation.objects.get(phone="573001234567")
        self.assertIsNotNone(conv.lead)


# ===========================================================================
# 7. VISTAS DASHADMIN
# ===========================================================================

class DashWAOverviewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin  = make_admin()
        self.url    = reverse("wa:dash_overview")
        self.client.login(username="admin1", password="test1234")

    def test_get_overview_ok(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_metrics_show_counts(self):
        make_conversation(status="new")
        make_conversation(status="open")
        resp = self.client.get(self.url)
        self.assertContains(resp, "2")   # total

    def test_filter_by_status(self):
        # Usar nombres únicos que no colisionen con las etiquetas de estado del dropdown
        make_conversation(status="new",  name="ContactoNuevo123")
        make_conversation(status="open", name="ContactoAbierto456")
        resp = self.client.get(self.url + "?status=new")
        self.assertContains(resp, "ContactoNuevo123")
        self.assertNotContains(resp, "ContactoAbierto456")

    def test_filter_by_q(self):
        make_conversation(name="Empresa ABC")
        make_conversation(name="Empresa XYZ")
        resp = self.client.get(self.url + "?q=ABC")
        self.assertContains(resp, "Empresa ABC")
        self.assertNotContains(resp, "Empresa XYZ")

    def test_anonymous_redirects(self):
        self.client.logout()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)


class DashWALabelsTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin  = make_admin()
        self.url    = reverse("wa:dash_labels")
        self.client.login(username="admin1", password="test1234")

    def test_get_labels_page(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_create_label(self):
        self.client.post(self.url, {"action": "create", "name": "Urgente", "color": "#EF4444"})
        lbl = ConversationLabel.objects.get(name="Urgente")
        self.assertEqual(lbl.color, "#EF4444")

    def test_create_label_without_name_ignored(self):
        self.client.post(self.url, {"action": "create", "name": "", "color": "#000"})
        self.assertEqual(ConversationLabel.objects.count(), 0)

    def test_delete_label(self):
        lbl = ConversationLabel.objects.create(name="Borrar")
        self.client.post(self.url, {"action": "delete", "pk": lbl.pk})
        self.assertFalse(ConversationLabel.objects.filter(pk=lbl.pk).exists())

    def test_edit_label(self):
        lbl = ConversationLabel.objects.create(name="Original", color="#000000")
        self.client.post(self.url, {
            "action": "edit", "pk": lbl.pk,
            "name": "Modificada", "color": "#FFFFFF",
        })
        lbl.refresh_from_db()
        self.assertEqual(lbl.name, "Modificada")
        self.assertEqual(lbl.color, "#FFFFFF")

    def test_delete_nonexistent_label_does_not_crash(self):
        resp = self.client.post(self.url, {"action": "delete", "pk": 99999})
        self.assertEqual(resp.status_code, 302)


class DashWAAssignTest(TestCase):

    def setUp(self):
        self.client  = Client()
        self.admin   = make_admin()
        self.asesora = make_asesora("asig1")
        self.conv    = make_conversation()
        self.url     = reverse("wa:dash_assign", args=[self.conv.pk])
        self.client.login(username="admin1", password="test1234")

    def test_assign_conversation(self):
        self.client.post(self.url, {"assigned_to": self.asesora.pk})
        self.conv.refresh_from_db()
        self.assertEqual(self.conv.assigned_to, self.asesora)

    def test_returns_json_ok(self):
        resp = self.client.post(self.url, {"assigned_to": self.asesora.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"ok": True})

    def test_clear_assignee(self):
        self.conv.assigned_to = self.asesora
        self.conv.save()
        self.client.post(self.url, {"assigned_to": ""})
        self.conv.refresh_from_db()
        self.assertIsNone(self.conv.assigned_to)

    def test_anonymous_cannot_assign(self):
        self.client.logout()
        resp = self.client.post(self.url, {"assigned_to": self.asesora.pk})
        self.assertEqual(resp.status_code, 302)
