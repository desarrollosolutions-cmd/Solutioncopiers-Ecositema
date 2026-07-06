"""Configuración endurecida para producción en Railway + Neon PostgreSQL."""
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from .base import *  # noqa: F401, F403

DEBUG = False

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])  # noqa: F405

# Render
RENDER_EXTERNAL_HOSTNAME = env("RENDER_EXTERNAL_HOSTNAME", default=None)  # noqa: F405
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# Railway
RAILWAY_PUBLIC_DOMAIN = env("RAILWAY_PUBLIC_DOMAIN", default=None)  # noqa: F405
if RAILWAY_PUBLIC_DOMAIN:
    ALLOWED_HOSTS.append(RAILWAY_PUBLIC_DOMAIN)

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
SESSION_COOKIE_SAMESITE = "Lax"      # Strict bloquea cookies al abrir links desde apps externas (WhatsApp, email)
CSRF_COOKIE_SAMESITE    = "Lax"

X_FRAME_OPTIONS = "DENY"

CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS if host]
if RAILWAY_PUBLIC_DOMAIN:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RAILWAY_PUBLIC_DOMAIN}")

# ---------------------------------------------------------------------------
# CONTENT SECURITY POLICY (CSP)
# Aplicado via middleware SecurityHeadersMiddleware definido abajo.
# ---------------------------------------------------------------------------
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://unpkg.com "
        "https://checkout.wompi.co https://www.googletagmanager.com https://www.google-analytics.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com; "
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
    "django.middleware.gzip.GZipMiddleware",
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

# ---------------------------------------------------------------------------
# CLOUDFLARE R2 — Almacenamiento de media files
# ---------------------------------------------------------------------------
R2_ACCOUNT_ID        = env("R2_ACCOUNT_ID",        default="")
R2_ACCESS_KEY_ID     = env("R2_ACCESS_KEY_ID",      default="")
R2_SECRET_ACCESS_KEY = env("R2_SECRET_ACCESS_KEY",  default="")
R2_BUCKET_NAME       = env("R2_BUCKET_NAME",        default="")
R2_CUSTOM_DOMAIN     = env("R2_CUSTOM_DOMAIN",      default="")

if R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME:
    STORAGES["default"] = {  # noqa: F405
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "access_key":    R2_ACCESS_KEY_ID,
            "secret_key":    R2_SECRET_ACCESS_KEY,
            "bucket_name":   R2_BUCKET_NAME,
            "endpoint_url":  f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            "region_name":   "auto",
            "custom_domain": R2_CUSTOM_DOMAIN or None,
            "file_overwrite": False,
            "object_parameters": {"CacheControl": "max-age=86400"},
            "querystring_auth": False,
        },
    }

# --- BD con connection pooling (Neon) ---
DATABASES["default"]["CONN_MAX_AGE"] = 60  # noqa: F405
DATABASES["default"]["OPTIONS"] = {"sslmode": "require"}  # noqa: F405
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True  # noqa: F405

# --- WhiteNoise ---
WHITENOISE_MAX_AGE = 31536000

# Media servida vía WhiteNoise (build.sh copia media/ → staticfiles/media/)
# Usar R2 cuando esté configurado (ya se activa arriba con las vars R2_*)
if not (R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME):
    MEDIA_URL = "/static/media/"

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
