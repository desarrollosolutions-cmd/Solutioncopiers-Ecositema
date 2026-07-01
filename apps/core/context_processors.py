"""Context processors."""
from .models import SiteSettings


def site_settings(request):
    """Inyecta SiteSettings en todos los templates."""
    return {"site_settings": SiteSettings.load()}
