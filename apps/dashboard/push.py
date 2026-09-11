"""Envío de notificaciones Web Push (VAPID) — funciona aunque el navegador
esté cerrado, mientras el usuario haya aceptado el permiso alguna vez.

Deliberadamente tolerante a fallos: si faltan las llaves VAPID, si
`pywebpush` no está instalado, o si el envío a una suscripción puntual
falla, esto nunca debe tumbar el flujo que llamó a Notification.push()."""
import json
import logging

logger = logging.getLogger("apps.push")


def send_web_push(user, title, body="", url=""):
    from django.conf import settings

    if not (settings.VAPID_PRIVATE_KEY and settings.VAPID_PUBLIC_KEY):
        return

    from apps.dashboard.models import PushSubscription
    subs = list(PushSubscription.objects.filter(user=user))
    if not subs:
        return

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning("pywebpush no está instalado; se omite el envío push.")
        return

    payload = json.dumps({
        "title": title,
        "body": body or "",
        "url": url or "/",
    })

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.VAPID_CLAIM_EMAIL},
                ttl=86400,
            )
        except WebPushException as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (404, 410):
                # Suscripción vencida o revocada por el navegador — ya no sirve.
                sub.delete()
            else:
                logger.warning("Push falló para %s: %s", user.username, e)
        except Exception:
            logger.warning("Push falló inesperadamente para %s", user.username, exc_info=True)
