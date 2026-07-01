"""
URLs raíz del proyecto Solution Copiers.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.contrib.sitemaps.views import sitemap

from apps.seo.sitemaps import sitemaps_dict
from apps.seo.views import robots_txt

# Rutas sin traducción (portales internos, admin, SEO técnico)
urlpatterns = [
    # --- Administración Django ---
    path("panel-admin-sc/", admin.site.urls),

    # --- Archivos técnicos SEO ---
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps_dict}, name="sitemap"),
    path("robots.txt", robots_txt, name="robots"),

    # --- Selector de idioma (POST set_language) ---
    path("i18n/", include("django.conf.urls.i18n")),

    # --- Panel de administración personalizado ---
    path("dashadmin/", include(("apps.dashboard.urls", "dashboard"), namespace="dashboard")),

    # --- Panel de asesoras ---
    path("panel/", include(("apps.dashboard.panel_urls", "panel"), namespace="panel")),

    # --- Portal de campo (mensajeros / técnicos) ---
    path("campo/", include(("apps.dashboard.campo_urls", "campo"), namespace="campo")),

    # --- Pagos y checkout público ---
    path("pago/", include(("apps.payments.urls", "payments"), namespace="payments")),

    # --- Encuesta (sin traducción) ---
    path("encuesta/", include(("apps.encuestas.urls", "encuestas"), namespace="encuestas")),
]

# Rutas públicas con prefijo de idioma (/en/... para inglés, sin prefijo para español)
urlpatterns += i18n_patterns(
    path("cotizador/", include(("apps.leads.urls", "leads"), namespace="leads")),
    path("blog/", include(("apps.blog.urls", "blog"), namespace="blog")),
    path("", include(("apps.catalog.urls", "catalog"), namespace="catalog")),
    path("", include(("apps.services.urls", "services"), namespace="services")),
    path("", include(("apps.core.urls", "core"), namespace="core")),
    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    try:
        import debug_toolbar
        urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
    except ImportError:
        pass

    try:
        urlpatterns += [path("__reload__/", include("django_browser_reload.urls"))]
    except Exception:
        pass

handler404 = "apps.core.views.error_404"
handler500 = "apps.core.views.error_500"
