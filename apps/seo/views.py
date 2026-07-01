"""Vistas auxiliares del módulo SEO."""
from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.cache import cache_page


@cache_page(60 * 60 * 24)
def robots_txt(request):
    sitemap_url = request.build_absolute_uri(reverse("sitemap"))
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /panel-admin-sc/",
        "Disallow: /cotizador/paso/",
        "Disallow: /cotizador/enviar/",
        "Disallow: /cotizador/api/",
        "Disallow: /media/private/",
        "",
        f"Sitemap: {sitemap_url}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")
