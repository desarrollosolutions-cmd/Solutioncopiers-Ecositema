"""Configuración endurecida para producción en Render.com + Supabase."""
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from .base import *  # noqa: F401, F403

DEBUG = False

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])  # noqa: F405
RENDER_EXTERNAL_HOSTNAME = env("RENDER_EXTERNAL_HOSTNAME", default=None)  # noqa: F405
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# ---------------------------------------------------------------------------
# HEADERS HTTP DE SEGURIDAD
# ---------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER          = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT              = True
SECURE_HSTS_SECONDS              = 31536000  # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS   = True
SECURE_HSTS_PRELOAD              = True
SECURE_CONTENT_TYPE_NOSNIFF      = True
SECURE_REFERRER_POLICY           = "strict-origin-when-cross-origin"
SECURE_BROWSER_XSS_FILTER        = True      # Legacy browsers

# Cookies en producción — siempre Secure
SESSION_COOKIE_SECURE  = True
CSRF_COOKIE_SECURE     = True
SESSION_COOKIE_SAMESITE = "Strict"   # Más restrictivo en producción
CSRF_COOKIE_SAMESITE    = "Strict"

X_FRAME_OPTIONS = "DENY"

CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS if host]

# ---------------------------------------------------------------------------
# CONTENT SECURITY POLICY (CSP)
# Aplicado via middleware SecurityHeadersMiddleware definido abajo.
# ---------------------------------------------------------------------------
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com "
        "https://checkout.wompi.co https://www.googletagmanager.com https://www.google-analytics.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "img-src 'self' data: https: blob:; "
    "connect-src 'self' https://api.groq.com https://api.anthropic.com "
        "https://sandbox.wompi.co https://production.wompi.co "
        "https://www.google-analytics.com; "
    "frame-src https://checkout.wompi.co; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self' https://checkout.wompi.co; "
    "upgrade-insecure-requests;"
)

PERMISSIONS_POLICY = (
    "accelerometer=(), "
    "camera=(), "
    "geolocation=(self), "
    "gyroscope=(), "
    "magnetometer=(), "
    "microphone=(), "
    "payment=(), "
    "usb=()"
)

# ---------------------------------------------------------------------------
# MIDDLEWARE adicional en producción — inyecta CSP y Permissions-Policy
# ---------------------------------------------------------------------------
MIDDLEWARE = [  # noqa: F405
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "solution_copiers.middleware.SecurityHeadersMiddleware",  # CSP + Permissions-Policy
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.seo.middleware.DynamicRedirectMiddleware",
]

# --- Email SMTP real ---
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")  # noqa: F405
EMAIL_PORT = env.int("EMAIL_PORT", default=587)  # noqa: F405
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)  # noqa: F405
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")  # noqa: F405
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")  # noqa: F405

# --- BD con connection pooling (Supabase pgbouncer) ---
DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405
DATABASES["default"]["OPTIONS"] = {"sslmode": "require"}  # noqa: F405
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True  # noqa: F405

# --- WhiteNoise ---
WHITENOISE_MAX_AGE = 31536000

# --- Sentry ---
SENTRY_DSN = env("SENTRY_DSN", default="")  # noqa: F405
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment="production",
    )
