"""Context processors."""
from .city_data import CITY_PAGES
from .models import SiteSettings


def site_settings(request):
    """Inyecta SiteSettings y los links de cobertura por ciudad en todos los templates."""
    presencial = sorted(
        ((slug, data["name"]) for slug, data in CITY_PAGES.items() if data["tier"] == "presencial"),
        key=lambda pair: CITY_PAGES[pair[0]]["order"],
    )
    return {
        "site_settings": SiteSettings.load(),
        "city_footer_links": presencial,
    }
