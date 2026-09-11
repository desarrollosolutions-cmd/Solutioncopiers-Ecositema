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
