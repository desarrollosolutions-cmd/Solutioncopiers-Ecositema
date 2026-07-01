"""
Servicio de integración con Wompi.

Wompi Checkout Link — no requiere backend complejo:
  1. Construir URL de checkout con parámetros
  2. Redirigir al usuario a Wompi
  3. Wompi redirige de vuelta a redirect_url con ?id=<transaction_id>
  4. Webhook notifica el resultado final

Documentación: https://docs.wompi.co/docs/colombia/widget-checkout-colombia/
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from decimal import Decimal
from urllib.parse import urlencode

from django.conf import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

CHECKOUT_BASE_URL = "https://checkout.wompi.co/p/"


def _public_key() -> str:
    return getattr(settings, "WOMPI_PUBLIC_KEY", "pub_test_REPLACE_ME")


def _events_key() -> str:
    return getattr(settings, "WOMPI_EVENTS_KEY", "test_events_secret_REPLACE_ME")


def _integrity_key() -> str:
    return getattr(settings, "WOMPI_INTEGRITY_KEY", "test_integrity_REPLACE_ME")


# ---------------------------------------------------------------------------
# Generar URL de checkout
# ---------------------------------------------------------------------------

def build_checkout_url(
    *,
    reference: str,
    amount_in_cents: int,
    redirect_url: str,
    currency: str = "COP",
    customer_email: str = "",
    customer_full_name: str = "",
    customer_phone_number: str = "",
    customer_legal_id: str = "",
    customer_legal_id_type: str = "CC",
) -> str:
    """
    Construye la URL del widget de checkout de Wompi.

    El parámetro `signature:integrity` es obligatorio desde 2024.
    Se calcula como SHA256(reference + amount_in_cents + currency + integrity_key).
    """
    integrity = _compute_integrity(reference, amount_in_cents, currency)

    params: dict[str, str | int] = {
        "public-key":        _public_key(),
        "currency":          currency,
        "amount-in-cents":   amount_in_cents,
        "reference":         reference,
        "redirect-url":      redirect_url,
        "signature:integrity": integrity,
    }

    if customer_email:
        params["customer-data:email"]               = customer_email
    if customer_full_name:
        params["customer-data:full-name"]           = customer_full_name
    if customer_phone_number:
        params["customer-data:phone-number"]        = customer_phone_number
    if customer_legal_id:
        params["customer-data:legal-id"]            = customer_legal_id
        params["customer-data:legal-id-type"]       = customer_legal_id_type

    return CHECKOUT_BASE_URL + "?" + urlencode(params)


def _compute_integrity(reference: str, amount_in_cents: int, currency: str) -> str:
    """SHA256 de reference + amount_in_cents + currency + integrity_key (sin separadores)."""
    raw = f"{reference}{amount_in_cents}{currency}{_integrity_key()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Verificar firma de webhook
# ---------------------------------------------------------------------------

def verify_webhook_signature(payload_bytes: bytes, checksum: str, properties: list[str], data: dict) -> bool:
    """
    Wompi firma los webhooks con SHA256 de los valores de las properties
    listadas en signature.properties + timestamp + events_key.

    El checksum viene en payload["signature"]["checksum"].
    Las properties son algo como ["transaction.id", "transaction.status", "transaction.amount_in_cents"].

    Cálculo: SHA256(valor1 + valor2 + ... + timestamp + events_key)
    """
    try:
        # Extraer valores de las properties desde data
        values = []
        for prop_path in properties:
            parts = prop_path.split(".")
            val   = data
            for p in parts:
                val = val[p]
            values.append(str(val))

        # timestamp está al nivel raíz del payload
        import json as _json
        payload_dict = _json.loads(payload_bytes)
        timestamp    = str(payload_dict.get("timestamp", ""))

        concatenated = "".join(values) + timestamp + _events_key()
        expected     = hashlib.sha256(concatenated.encode("utf-8")).hexdigest()
        return hmac.compare_digest(expected, checksum)
    except Exception as exc:
        logger.warning("Wompi webhook signature check failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Consultar transacción por referencia (API REST — opcional)
# ---------------------------------------------------------------------------

def fetch_transaction_by_reference(reference: str) -> dict | None:
    """
    Consulta la última transacción por referencia usando la API pública de Wompi.
    Útil para confirmar estado después del redirect sin esperar el webhook.
    """
    import urllib.request, urllib.error

    private_key = getattr(settings, "WOMPI_PRIVATE_KEY", "")
    if not private_key:
        logger.warning("WOMPI_PRIVATE_KEY no configurado, no se puede consultar transacción.")
        return None

    is_sandbox = "test" in _public_key().lower()
    base = "https://sandbox.wompi.co/v1" if is_sandbox else "https://production.wompi.co/v1"
    url  = f"{base}/transactions?reference={reference}"

    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {private_key}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            items = body.get("data", [])
            # Devolver la transacción más reciente
            return items[0] if items else None
    except urllib.error.URLError as exc:
        logger.error("Wompi API error fetching transaction %s: %s", reference, exc)
        return None
