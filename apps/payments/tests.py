"""
Suite de pruebas para el módulo de pagos y contabilidad.

Cubre:
  1. Modelos: cálculos de totales, retenciones, propiedades
  2. Servicios: Wompi — integridad, firma webhook
  3. Vistas públicas: carrito, checkout, confirmación, webhook
  4. Vistas CRM: facturas, pedidos, contabilidad, exportaciones CSV
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Consumable
from apps.leads.models import Lead
from apps.payments.models import Invoice, InvoiceItem, Order, OrderItem, Payment
from apps.payments.services import _compute_integrity, build_checkout_url, verify_webhook_signature

User = get_user_model()


# ===========================================================================
# Fixtures / helpers
# ===========================================================================

WOMPI_INTEGRITY_TEST = "test_integrity_key_for_suite"
WOMPI_EVENTS_TEST    = "test_events_key_for_suite"


def make_consumable(name="Tóner Test", price="100000.00", slug="toner-test") -> Consumable:
    """Crea un consumible publicado apto para ser encontrado por Consumable.published."""
    return Consumable.objects.create(
        name         = name,
        slug         = slug,
        price        = Decimal(price),
        in_stock     = True,
        status       = "published",
        published_at = timezone.now(),
    )


def make_order(**kwargs) -> Order:
    defaults = dict(
        buyer_name  = "Juan Pérez",
        buyer_email = "juan@empresa.co",
        buyer_phone = "3001234567",
        buyer_city  = "Medellín",
        subtotal    = Decimal("100000.00"),
        tax_amount  = Decimal("19000.00"),
        total       = Decimal("119000.00"),
    )
    defaults.update(kwargs)
    return Order.objects.create(**defaults)


def make_invoice(client_name="Empresa SA", total=Decimal("119000.00"), **kwargs) -> Invoice:
    defaults = dict(
        client_name = client_name,
        status      = Invoice.Status.ISSUED,
        issue_date  = timezone.localdate(),
        subtotal    = Decimal("100000.00"),
        tax_base    = Decimal("100000.00"),
        tax_amount  = Decimal("19000.00"),
        total       = total,
    )
    defaults.update(kwargs)
    return Invoice.objects.create(**defaults)


def make_invoice_with_items(unit_price=Decimal("100000.00"), quantity=1) -> Invoice:
    inv = Invoice.objects.create(client_name="Cliente Test", status=Invoice.Status.DRAFT)
    InvoiceItem.objects.create(
        invoice    = inv,
        description = "Tóner B/N",
        quantity   = quantity,
        unit_price = unit_price,
    )
    return inv


def _build_webhook_payload(reference: str, status: str, amount_in_cents: int) -> tuple[bytes, str]:
    """
    Construye un payload de webhook Wompi con firma válida.
    Devuelve (payload_bytes, checksum).
    """
    timestamp = "1700000000"
    txn = {
        "id":             "test-txn-001",
        "status":         status,
        "amount_in_cents": amount_in_cents,
        "reference":      reference,
        "payment_method_type": "CARD",
    }
    properties = ["transaction.id", "transaction.status", "transaction.amount_in_cents"]
    values     = [txn["id"], txn["status"], str(txn["amount_in_cents"])]
    concatenated = "".join(values) + timestamp + WOMPI_EVENTS_TEST
    checksum  = hashlib.sha256(concatenated.encode()).hexdigest()

    payload = {
        "event": "transaction.updated",
        "timestamp": timestamp,
        "signature": {"checksum": checksum, "properties": properties},
        "data": {"transaction": txn},
    }
    return json.dumps(payload).encode(), checksum


# ===========================================================================
# 1. MODELOS
# ===========================================================================

class OrderRefTest(TestCase):
    def test_ref_format(self):
        order = make_order()
        self.assertRegex(order.reference, r"^SC-[0-9A-F]{8}$")

    def test_refs_son_unicos(self):
        refs = {make_order(buyer_email=f"u{i}@x.co").reference for i in range(10)}
        self.assertEqual(len(refs), 10)


class OrderAmountCentsTest(TestCase):
    def test_amount_in_cents(self):
        order = make_order(total=Decimal("119000.00"))
        self.assertEqual(order.amount_in_cents, 11900000)

    def test_amount_in_cents_fraccion(self):
        order = make_order(total=Decimal("50000.50"))
        self.assertEqual(order.amount_in_cents, 5000050)


class OrderRecalculateTotalsTest(TestCase):
    def test_recalcula_subtotal_iva_total(self):
        consumable = make_consumable(price="100000.00")
        order = Order.objects.create(
            buyer_name="Test", buyer_email="t@t.co", buyer_city="Medellín"
        )
        OrderItem.objects.create(
            order        = order,
            consumable   = consumable,
            quantity     = 2,
            unit_price   = Decimal("100000.00"),
            product_name = "Tóner Test",
        )
        order.recalculate_totals()

        self.assertEqual(order.subtotal,   Decimal("200000.00"))
        self.assertEqual(order.tax_amount, Decimal("38000.00"))
        self.assertEqual(order.total,      Decimal("238000.00"))


class OrderItemLineTotalTest(TestCase):
    def test_line_total(self):
        consumable = make_consumable()
        order = make_order()
        item = OrderItem(
            order        = order,
            consumable   = consumable,
            quantity     = 3,
            unit_price   = Decimal("50000.00"),
            product_name = "Tóner",
        )
        self.assertEqual(item.line_total, Decimal("150000.00"))


class InvoiceNumberTest(TestCase):
    def test_sin_consecutivo(self):
        inv = Invoice.objects.create(client_name="X")
        self.assertTrue(inv.invoice_number.startswith("BORR-"))

    def test_con_consecutivo(self):
        inv = Invoice.objects.create(
            client_name      = "X",
            dian_prefix      = "FV",
            dian_consecutive = 42,
        )
        self.assertEqual(inv.invoice_number, "FV-00042")


class InvoiceIsOverdueTest(TestCase):
    def test_no_vencida_sin_fecha(self):
        inv = Invoice.objects.create(client_name="X")
        self.assertFalse(inv.is_overdue)

    def test_vencida(self):
        from datetime import date, timedelta
        inv = Invoice.objects.create(
            client_name = "X",
            status      = Invoice.Status.ISSUED,
            due_date    = date.today() - timedelta(days=1),
        )
        self.assertTrue(inv.is_overdue)

    def test_pagada_no_vencida(self):
        from datetime import date, timedelta
        inv = Invoice.objects.create(
            client_name = "X",
            status      = Invoice.Status.PAID,
            due_date    = date.today() - timedelta(days=5),
        )
        self.assertFalse(inv.is_overdue)


class InvoiceRecalculateSinRetencioneTest(TestCase):
    def test_totales_basicos(self):
        inv = make_invoice_with_items(unit_price=Decimal("100000.00"), quantity=1)
        inv.recalculate_totals()

        self.assertEqual(inv.subtotal,    Decimal("100000.00"))
        self.assertEqual(inv.tax_base,    Decimal("100000.00"))
        self.assertEqual(inv.tax_amount,  Decimal("19000.00"))
        self.assertEqual(inv.total,       Decimal("119000.00"))
        self.assertEqual(inv.retention_fuente, Decimal("0.00"))
        self.assertEqual(inv.retention_ica,    Decimal("0.00"))
        self.assertEqual(inv.retention_iva,    Decimal("0.00"))
        self.assertEqual(inv.net_received,     Decimal("119000.00"))

    def test_descuento(self):
        inv = make_invoice_with_items(unit_price=Decimal("100000.00"))
        inv.discount_amount = Decimal("10000.00")
        inv.recalculate_totals()

        self.assertEqual(inv.tax_base,   Decimal("90000.00"))
        self.assertEqual(inv.tax_amount, Decimal("17100.00"))
        self.assertEqual(inv.total,      Decimal("107100.00"))


class InvoiceReteFuenteTest(TestCase):
    def test_rtefuente_2_5_pct(self):
        inv = make_invoice_with_items(unit_price=Decimal("100000.00"))
        inv.retention_fuente_pct = Decimal("2.50")
        inv.recalculate_totals()

        # 2.5% de 119000 = 2975
        self.assertEqual(inv.retention_fuente, Decimal("2975.00"))
        self.assertEqual(inv.net_received,     Decimal("116025.00"))

    def test_rtefuente_3_5_pct(self):
        inv = make_invoice_with_items(unit_price=Decimal("100000.00"))
        inv.retention_fuente_pct = Decimal("3.50")
        inv.recalculate_totals()

        # 3.5% de 119000 = 4165
        self.assertEqual(inv.retention_fuente, Decimal("4165.00"))

    def test_sin_retefuente(self):
        inv = make_invoice_with_items(unit_price=Decimal("100000.00"))
        inv.retention_fuente_pct = Decimal("0.00")
        inv.recalculate_totals()
        self.assertEqual(inv.retention_fuente, Decimal("0.00"))


class InvoiceReteICATest(TestCase):
    def test_reteica_medellin_9_66_milesimas(self):
        """
        ReteICA Medellín comercio: 9.66‰ sobre base sin IVA.
        Base = 100000, ReteICA = 100000 * 9.66 / 1000 = 966
        """
        inv = make_invoice_with_items(unit_price=Decimal("100000.00"))
        inv.retention_ica_pct = Decimal("9.66")
        inv.recalculate_totals()

        self.assertEqual(inv.retention_ica, Decimal("966.00"))
        self.assertEqual(inv.net_received, Decimal("119000.00") - Decimal("966.00"))

    def test_reteica_zero(self):
        inv = make_invoice_with_items(unit_price=Decimal("100000.00"))
        inv.retention_ica_pct = Decimal("0.00")
        inv.recalculate_totals()
        self.assertEqual(inv.retention_ica, Decimal("0.00"))


class InvoiceReteIVATest(TestCase):
    def test_reteiva_15_pct_del_iva(self):
        """
        ReteIVA: 15% del IVA.
        IVA = 19000, ReteIVA = 19000 * 0.15 = 2850
        """
        inv = make_invoice_with_items(unit_price=Decimal("100000.00"))
        inv.retention_iva_pct = Decimal("15.00")
        inv.recalculate_totals()

        self.assertEqual(inv.retention_iva, Decimal("2850.00"))
        self.assertEqual(inv.net_received, Decimal("119000.00") - Decimal("2850.00"))


class InvoiceTresRetencionesTest(TestCase):
    def test_tres_retenciones_simultaneas(self):
        """
        Escenario gran contribuyente — aplica las 3 retenciones:
          RteFuente 2.5%  sobre total  (119000) = 2975
          ReteICA   9.66‰ sobre base   (100000) = 966
          ReteIVA   15%   sobre IVA    (19000)  = 2850
          Total retenciones = 6791
          Neto = 119000 - 6791 = 112209
        """
        inv = make_invoice_with_items(unit_price=Decimal("100000.00"))
        inv.retention_fuente_pct = Decimal("2.50")
        inv.retention_ica_pct    = Decimal("9.66")
        inv.retention_iva_pct    = Decimal("15.00")
        inv.recalculate_totals()

        self.assertEqual(inv.retention_fuente, Decimal("2975.00"))
        self.assertEqual(inv.retention_ica,    Decimal("966.00"))
        self.assertEqual(inv.retention_iva,    Decimal("2850.00"))
        self.assertEqual(inv.total_retenciones, Decimal("6791.00"))
        self.assertEqual(inv.net_received,      Decimal("112209.00"))


class InvoiceItemPropertiesTest(TestCase):
    def test_line_total_sin_descuento(self):
        inv  = Invoice.objects.create(client_name="X")
        item = InvoiceItem(
            invoice     = inv,
            description = "Tóner",
            quantity    = Decimal("2"),
            unit_price  = Decimal("50000.00"),
        )
        self.assertEqual(item.line_subtotal, Decimal("100000.00"))
        self.assertEqual(item.line_discount, Decimal("0.00"))
        self.assertEqual(item.line_total,    Decimal("100000.00"))
        self.assertEqual(item.line_tax,      Decimal("19000.00"))

    def test_line_total_con_descuento(self):
        inv  = Invoice.objects.create(client_name="X")
        item = InvoiceItem(
            invoice      = inv,
            description  = "Tóner",
            quantity     = Decimal("1"),
            unit_price   = Decimal("100000.00"),
            discount_pct = Decimal("10.00"),
        )
        self.assertEqual(item.line_discount, Decimal("10000.00"))
        self.assertEqual(item.line_total,    Decimal("90000.00"))


class PaymentAmountCopTest(TestCase):
    def test_amount_cop(self):
        pay = Payment(
            reference       = "SC-TEST0001",
            amount_in_cents = 11900000,
        )
        self.assertEqual(pay.amount_cop, Decimal("119000.00"))


# ===========================================================================
# 2. SERVICIOS WOMPI
# ===========================================================================

@override_settings(
    WOMPI_INTEGRITY_KEY=WOMPI_INTEGRITY_TEST,
    WOMPI_PUBLIC_KEY="pub_test_TESTKEY",
)
class IntegrityTest(TestCase):
    def test_sha256_correcto(self):
        reference       = "SC-ABCD1234"
        amount_in_cents = 11900000
        currency        = "COP"

        raw      = f"{reference}{amount_in_cents}{currency}{WOMPI_INTEGRITY_TEST}"
        expected = hashlib.sha256(raw.encode()).hexdigest()
        result   = _compute_integrity(reference, amount_in_cents, currency)

        self.assertEqual(result, expected)

    def test_distinto_reference_distinto_hash(self):
        h1 = _compute_integrity("SC-AAA00001", 10000, "COP")
        h2 = _compute_integrity("SC-BBB00002", 10000, "COP")
        self.assertNotEqual(h1, h2)

    def test_build_checkout_url_contiene_params(self):
        url = build_checkout_url(
            reference        = "SC-ABCD1234",
            amount_in_cents  = 11900000,
            redirect_url     = "https://example.com/confirmacion/",
            customer_email   = "test@test.co",
            customer_full_name = "Juan Test",
        )
        self.assertIn("checkout.wompi.co/p/", url)
        self.assertIn("reference=SC-ABCD1234", url)
        self.assertIn("amount-in-cents=11900000", url)
        self.assertIn("currency=COP", url)
        self.assertIn("signature%3Aintegrity=", url)
        self.assertIn("customer-data%3Aemail=test%40test.co", url)


@override_settings(WOMPI_EVENTS_KEY=WOMPI_EVENTS_TEST)
class WebhookSignatureTest(TestCase):
    def _make_signature_components(self, txn_id, status, amount):
        timestamp  = "1700000000"
        properties = ["transaction.id", "transaction.status", "transaction.amount_in_cents"]
        values     = [txn_id, status, str(amount)]
        concatenated = "".join(values) + timestamp + WOMPI_EVENTS_TEST
        checksum   = hashlib.sha256(concatenated.encode()).hexdigest()
        return timestamp, properties, checksum

    def test_firma_valida(self):
        timestamp, properties, checksum = self._make_signature_components(
            "abc123", "APPROVED", 5000000
        )
        payload = json.dumps({
            "timestamp": timestamp,
            "data": {
                "transaction": {
                    "id":             "abc123",
                    "status":         "APPROVED",
                    "amount_in_cents": 5000000,
                }
            }
        }).encode()
        data = json.loads(payload)["data"]
        ok   = verify_webhook_signature(payload, checksum, properties, data)
        self.assertTrue(ok)

    def test_firma_invalida(self):
        timestamp, properties, checksum = self._make_signature_components(
            "abc123", "APPROVED", 5000000
        )
        payload = json.dumps({
            "timestamp": timestamp,
            "data": {
                "transaction": {
                    "id":             "abc123",
                    "status":         "APPROVED",
                    "amount_in_cents": 5000000,
                }
            }
        }).encode()
        data = json.loads(payload)["data"]
        ok   = verify_webhook_signature(payload, "firma_incorrecta", properties, data)
        self.assertFalse(ok)

    def test_payload_malformado_retorna_false(self):
        ok = verify_webhook_signature(
            b"no-es-json", "cualquier_checksum", [], {}
        )
        self.assertFalse(ok)


# ===========================================================================
# 3. VISTAS PÚBLICAS — carrito
# ===========================================================================

class CartAddViewTest(TestCase):
    def setUp(self):
        self.client      = Client()
        self.consumable  = make_consumable()
        self.url_add     = reverse("payments:cart_add")
        self.url_cart    = reverse("payments:cart")

    def test_agregar_producto_valido(self):
        resp = self.client.post(self.url_add, {"consumable_id": self.consumable.pk, "quantity": 2})
        self.assertRedirects(resp, self.url_cart)
        cart = self.client.session.get("sc_cart", {})
        key  = str(self.consumable.pk)
        self.assertIn(key, cart)
        self.assertEqual(cart[key]["quantity"], 2)

    def test_agregar_producto_inexistente(self):
        resp = self.client.post(self.url_add, {"consumable_id": 99999, "quantity": 1})
        self.assertEqual(resp.status_code, 302)

    def test_agregar_producto_ajax(self):
        resp = self.client.post(
            self.url_add,
            {"consumable_id": self.consumable.pk, "quantity": 1},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data["ok"])
        self.assertEqual(data["cart_count"], 1)

    def test_acumula_cantidad_mismo_producto(self):
        self.client.post(self.url_add, {"consumable_id": self.consumable.pk, "quantity": 1})
        self.client.post(self.url_add, {"consumable_id": self.consumable.pk, "quantity": 2})
        cart = self.client.session.get("sc_cart", {})
        self.assertEqual(cart[str(self.consumable.pk)]["quantity"], 3)


class CartUpdateViewTest(TestCase):
    def setUp(self):
        self.client     = Client()
        self.consumable = make_consumable()
        self.client.post(reverse("payments:cart_add"), {"consumable_id": self.consumable.pk, "quantity": 3})

    def test_actualizar_cantidad(self):
        self.client.post(reverse("payments:cart_update"), {
            "consumable_id": self.consumable.pk,
            "quantity": 5,
        })
        cart = self.client.session.get("sc_cart", {})
        self.assertEqual(cart[str(self.consumable.pk)]["quantity"], 5)

    def test_cantidad_cero_elimina_item(self):
        self.client.post(reverse("payments:cart_update"), {
            "consumable_id": self.consumable.pk,
            "quantity": 0,
        })
        cart = self.client.session.get("sc_cart", {})
        self.assertNotIn(str(self.consumable.pk), cart)


class CartViewTest(TestCase):
    def setUp(self):
        self.client     = Client()
        self.consumable = make_consumable(price="50000.00")
        self.client.post(reverse("payments:cart_add"), {"consumable_id": self.consumable.pk, "quantity": 2})

    def test_muestra_carrito(self):
        resp = self.client.get(reverse("payments:cart"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Tóner Test")

    def test_carrito_vacio_muestra_pagina(self):
        empty_client = Client()
        resp = empty_client.get(reverse("payments:cart"))
        self.assertEqual(resp.status_code, 200)


# ===========================================================================
# 4. VISTAS PÚBLICAS — checkout
# ===========================================================================

class CheckoutViewTest(TestCase):
    def setUp(self):
        self.client     = Client()
        self.consumable = make_consumable(price="100000.00")

    def test_checkout_get_carrito_vacio_redirige(self):
        resp = self.client.get(reverse("payments:checkout"))
        self.assertEqual(resp.status_code, 302)

    def test_checkout_get_con_items(self):
        self.client.post(reverse("payments:cart_add"), {"consumable_id": self.consumable.pk, "quantity": 1})
        resp = self.client.get(reverse("payments:checkout"))
        self.assertEqual(resp.status_code, 200)

    def test_checkout_post_crea_order(self):
        self.client.post(reverse("payments:cart_add"), {"consumable_id": self.consumable.pk, "quantity": 1})
        resp = self.client.post(reverse("payments:checkout"), {
            "buyer_name":    "Ana García",
            "buyer_email":   "ana@empresa.co",
            "buyer_phone":   "3109876543",
            "buyer_city":    "Medellín",
            "buyer_address": "Calle 50 # 45-23",
        })
        # Redirige a URL de Wompi (checkout.wompi.co)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("checkout.wompi.co", resp["Location"])

        order = Order.objects.get(buyer_email="ana@empresa.co")
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.total, Decimal("119000.00"))

    def test_checkout_post_crea_lead_nuevo(self):
        self.assertFalse(Lead.objects.filter(email="nuevo@empresa.co").exists())
        self.client.post(reverse("payments:cart_add"), {"consumable_id": self.consumable.pk, "quantity": 1})
        self.client.post(reverse("payments:checkout"), {
            "buyer_name":  "Cliente Nuevo",
            "buyer_email": "nuevo@empresa.co",
            "buyer_city":  "Cali",
        })
        self.assertTrue(Lead.objects.filter(email="nuevo@empresa.co").exists())

    def test_checkout_post_vincula_lead_existente(self):
        lead = Lead.objects.create(full_name="Existente", email="existente@empresa.co")
        self.client.post(reverse("payments:cart_add"), {"consumable_id": self.consumable.pk, "quantity": 1})
        self.client.post(reverse("payments:checkout"), {
            "buyer_name":  "Existente",
            "buyer_email": "existente@empresa.co",
            "buyer_city":  "Medellín",
        })
        order = Order.objects.get(buyer_email="existente@empresa.co")
        self.assertEqual(order.lead_id, lead.pk)

    def test_checkout_post_crea_payment_pendiente(self):
        self.client.post(reverse("payments:cart_add"), {"consumable_id": self.consumable.pk, "quantity": 1})
        self.client.post(reverse("payments:checkout"), {
            "buyer_name":  "Pago Test",
            "buyer_email": "pago@test.co",
            "buyer_city":  "Medellín",
        })
        order = Order.objects.get(buyer_email="pago@test.co")
        self.assertEqual(order.payments.count(), 1)
        self.assertEqual(order.payments.first().status, Payment.Status.PENDING)

    def test_checkout_post_limpia_carrito(self):
        self.client.post(reverse("payments:cart_add"), {"consumable_id": self.consumable.pk, "quantity": 1})
        self.client.post(reverse("payments:checkout"), {
            "buyer_name":  "Clean Test",
            "buyer_email": "clean@test.co",
            "buyer_city":  "Medellín",
        })
        cart = self.client.session.get("sc_cart", {})
        self.assertEqual(len(cart), 0)


# ===========================================================================
# 5. CONFIRMACIÓN DE PEDIDO
# ===========================================================================

class OrderConfirmationViewTest(TestCase):
    def test_muestra_pedido_pendiente(self):
        order = make_order()
        url   = reverse("payments:order_confirmation", kwargs={"reference": order.reference})
        resp  = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, order.reference)

    def test_pedido_inexistente_404(self):
        url  = reverse("payments:order_confirmation", kwargs={"reference": "SC-NOEXIST"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)


# ===========================================================================
# 6. WEBHOOK WOMPI
# ===========================================================================

@override_settings(WOMPI_EVENTS_KEY=WOMPI_EVENTS_TEST)
class WompiWebhookTest(TestCase):
    url = "/pago/webhook/wompi/"

    def setUp(self):
        self.order = make_order()
        Payment.objects.create(
            order           = self.order,
            reference       = self.order.reference,
            amount_in_cents = self.order.amount_in_cents,
        )

    def test_json_invalido_retorna_400(self):
        resp = self.client.post(
            self.url, data=b"no-es-json",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_firma_invalida_retorna_401(self):
        payload_bytes, _ = _build_webhook_payload(
            self.order.reference, "APPROVED", self.order.amount_in_cents
        )
        tampered = json.loads(payload_bytes)
        tampered["signature"]["checksum"] = "firma_falsa"
        resp = self.client.post(
            self.url, data=json.dumps(tampered).encode(),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_approved_actualiza_order_a_paid(self):
        payload_bytes, _ = _build_webhook_payload(
            self.order.reference, "APPROVED", self.order.amount_in_cents
        )
        resp = self.client.post(
            self.url, data=payload_bytes, content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)

    def test_approved_actualiza_payment_a_approved(self):
        payload_bytes, _ = _build_webhook_payload(
            self.order.reference, "APPROVED", self.order.amount_in_cents
        )
        self.client.post(self.url, data=payload_bytes, content_type="application/json")
        pay = Payment.objects.get(reference=self.order.reference)
        self.assertEqual(pay.status, Payment.Status.APPROVED)

    def test_approved_genera_factura_automatica(self):
        payload_bytes, _ = _build_webhook_payload(
            self.order.reference, "APPROVED", self.order.amount_in_cents
        )
        self.client.post(self.url, data=payload_bytes, content_type="application/json")
        self.order.refresh_from_db()
        self.assertTrue(hasattr(self.order, "invoice") and self.order.invoice is not None)

    def test_declined_actualiza_order_a_failed(self):
        payload_bytes, _ = _build_webhook_payload(
            self.order.reference, "DECLINED", self.order.amount_in_cents
        )
        self.client.post(self.url, data=payload_bytes, content_type="application/json")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.FAILED)

    def test_voided_cancela_order(self):
        payload_bytes, _ = _build_webhook_payload(
            self.order.reference, "VOIDED", self.order.amount_in_cents
        )
        self.client.post(self.url, data=payload_bytes, content_type="application/json")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)

    def test_webhook_idempotente_order_ya_pagado(self):
        """Si el pedido ya está pagado, un segundo APPROVED no falla."""
        self.order.status = Order.Status.PAID
        self.order.save()
        payload_bytes, _ = _build_webhook_payload(
            self.order.reference, "APPROVED", self.order.amount_in_cents
        )
        resp = self.client.post(self.url, data=payload_bytes, content_type="application/json")
        self.assertEqual(resp.status_code, 200)

    def test_referencia_inexistente_no_falla(self):
        """Un webhook con referencia que no existe responde 200 (no genera excepción)."""
        payload_bytes, _ = _build_webhook_payload(
            "SC-NOEXIST0", "APPROVED", 5000000
        )
        resp = self.client.post(self.url, data=payload_bytes, content_type="application/json")
        self.assertEqual(resp.status_code, 200)


# ===========================================================================
# 7. VISTAS CRM — autenticación
# ===========================================================================

class CRMAuthTest(TestCase):
    """Todas las vistas del CRM deben exigir login."""

    def test_invoice_list_sin_auth_redirige(self):
        resp = self.client.get(reverse("dashboard:invoice_list"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/dashadmin/acceso/", resp["Location"])

    def test_order_list_sin_auth_redirige(self):
        resp = self.client.get(reverse("dashboard:order_list"))
        self.assertEqual(resp.status_code, 302)

    def test_ar_dashboard_sin_auth_redirige(self):
        resp = self.client.get(reverse("dashboard:ar_dashboard"))
        self.assertEqual(resp.status_code, 302)

    def test_contabilidad_sin_auth_redirige(self):
        resp = self.client.get(reverse("dashboard:contabilidad"))
        self.assertEqual(resp.status_code, 302)


class CRMViewsConAuthTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="testadmin", password="Test1234!", email="admin@test.co"
        )
        self.client.login(username="testadmin", password="Test1234!")

    def test_invoice_list_ok(self):
        resp = self.client.get(reverse("dashboard:invoice_list"))
        self.assertEqual(resp.status_code, 200)

    def test_invoice_create_get_ok(self):
        resp = self.client.get(reverse("dashboard:invoice_create"))
        self.assertEqual(resp.status_code, 200)

    def test_order_list_ok(self):
        resp = self.client.get(reverse("dashboard:order_list"))
        self.assertEqual(resp.status_code, 200)

    def test_ar_dashboard_ok(self):
        resp = self.client.get(reverse("dashboard:ar_dashboard"))
        self.assertEqual(resp.status_code, 200)

    def test_contabilidad_ok(self):
        resp = self.client.get(reverse("dashboard:contabilidad"))
        self.assertEqual(resp.status_code, 200)

    def test_libro_ventas_ok(self):
        resp = self.client.get(reverse("dashboard:libro_ventas"))
        self.assertEqual(resp.status_code, 200)

    def test_iva_report_ok(self):
        resp = self.client.get(reverse("dashboard:iva_report"))
        self.assertEqual(resp.status_code, 200)

    def test_retenciones_ok(self):
        resp = self.client.get(reverse("dashboard:retenciones"))
        self.assertEqual(resp.status_code, 200)

    def test_invoice_detail_ok(self):
        inv  = make_invoice()
        resp = self.client.get(reverse("dashboard:invoice_detail", kwargs={"pk": inv.pk}))
        self.assertEqual(resp.status_code, 200)

    def test_order_detail_ok(self):
        order = make_order()
        resp  = self.client.get(
            reverse("dashboard:order_detail", kwargs={"reference": order.reference})
        )
        self.assertEqual(resp.status_code, 200)

    def test_invoice_detail_inexistente_404(self):
        resp = self.client.get(reverse("dashboard:invoice_detail", kwargs={"pk": 99999}))
        self.assertEqual(resp.status_code, 404)

    def test_order_detail_inexistente_404(self):
        resp = self.client.get(
            reverse("dashboard:order_detail", kwargs={"reference": "SC-NOEXIST"})
        )
        self.assertEqual(resp.status_code, 404)


# ===========================================================================
# 8. EXPORTACIONES CSV
# ===========================================================================

class LibroVentasCSVTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="csvadmin", password="Test1234!", email="csv@test.co"
        )
        self.client.login(username="csvadmin", password="Test1234!")
        # Crear algunas facturas emitidas
        for i in range(3):
            make_invoice(
                client_name      = f"Empresa {i}",
                total            = Decimal("119000.00"),
                dian_prefix      = "FV",
                dian_consecutive = i + 1,
                issue_date       = timezone.localdate(),
            )

    def test_csv_content_type(self):
        url  = reverse("dashboard:libro_ventas") + "?export=csv"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp["Content-Type"])

    def test_csv_tiene_cabeceras(self):
        url  = reverse("dashboard:libro_ventas") + "?export=csv"
        resp = self.client.get(url)
        content = resp.content.decode("utf-8-sig")
        self.assertIn("Nro. Factura", content)
        self.assertIn("Cliente", content)
        self.assertIn("IVA", content)

    def test_csv_incluye_facturas(self):
        url  = reverse("dashboard:libro_ventas") + "?export=csv"
        resp = self.client.get(url)
        content = resp.content.decode("utf-8-sig")
        self.assertIn("Empresa 0", content)


class RetencionesSufridasCSVTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="retadmin", password="Test1234!", email="ret@test.co"
        )
        self.client.login(username="retadmin", password="Test1234!")
        inv = make_invoice_with_items(unit_price=Decimal("100000.00"))
        inv.retention_fuente_pct = Decimal("2.50")
        inv.retention_ica_pct    = Decimal("9.66")
        inv.recalculate_totals()
        inv.save()

    def test_csv_content_type(self):
        url  = reverse("dashboard:retenciones") + "?export=csv"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp["Content-Type"])

    def test_csv_tiene_cabeceras(self):
        url  = reverse("dashboard:retenciones") + "?export=csv"
        resp = self.client.get(url)
        content = resp.content.decode("utf-8-sig")
        self.assertIn("RteFuente", content)
        self.assertIn("RteICA", content)


# ===========================================================================
# 9. CONTABILIDAD BIMESTRAL — IVA report
# ===========================================================================

class IVAReportBimestresTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="ivaadmin", password="Test1234!", email="iva@test.co"
        )
        self.client.login(username="ivaadmin", password="Test1234!")

    def test_muestra_6_bimestres(self):
        resp = self.client.get(reverse("dashboard:iva_report"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["datos_bimestres"]), 6)

    def test_filtro_por_año(self):
        resp = self.client.get(reverse("dashboard:iva_report") + "?year=2025")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["year"], 2025)

    def test_año_actual_por_defecto(self):
        resp = self.client.get(reverse("dashboard:iva_report"))
        self.assertEqual(resp.context["year"], timezone.localdate().year)


# ===========================================================================
# 10. INVOICE CREATE (POST CRM)
# ===========================================================================

class InvoiceCreatePostTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="invadmin", password="Test1234!", email="inv@test.co"
        )
        self.client.login(username="invadmin", password="Test1234!")

    def test_crear_factura_manual(self):
        resp = self.client.post(reverse("dashboard:invoice_create"), {
            "client_name":       "Cliente Prueba SA",
            "client_nit":        "900123456-1",
            "client_email":      "cliente@prueba.co",
            "client_city":       "Bogotá",
            "payment_method":    "42",
            "item_description":  "Mantenimiento impresora",
            "item_quantity":     "1",
            "item_price":        "200000",
            "notes":             "",
        })
        # Redirige al detalle si se creó correctamente
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Invoice.objects.filter(client_nit="900123456-1").exists())

    def test_invoice_status_update(self):
        inv  = make_invoice()
        resp = self.client.post(
            reverse("dashboard:invoice_status", kwargs={"pk": inv.pk}),
            {"status": "paid"},
        )
        self.assertEqual(resp.status_code, 302)
        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.PAID)
