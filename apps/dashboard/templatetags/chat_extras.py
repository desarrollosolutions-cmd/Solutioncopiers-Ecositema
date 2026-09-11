from django import template

register = template.Library()


@register.simple_tag
def user_avatar(user):
    """Foto de perfil (data URI) de un usuario, o cadena vacía si no tiene / no aplica."""
    if not user or not getattr(user, "is_authenticated", False):
        return ""
    from apps.dashboard.models import UserProfile
    try:
        return user.profile.avatar_b64
    except UserProfile.DoesNotExist:
        return ""


@register.simple_tag
def vapid_public_key():
    """Llave pública VAPID para que el navegador pueda suscribirse a push."""
    from django.conf import settings
    return settings.VAPID_PUBLIC_KEY
