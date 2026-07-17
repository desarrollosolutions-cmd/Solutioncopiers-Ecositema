"""
Configuración base compartida entre todos los entornos.

Filosofía: aquí solo va lo invariable. Lo que cambia (DEBUG, hosts, email)
se sobrescribe en development.py o production.py.
"""
from pathlib import Path
import environ

# ---------------------------------------------------------------------------
# RUTAS BASE
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# ENV LOADER
# ---------------------------------------------------------------------------
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
)
environ.Env.read_env(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# SEGURIDAD
# ---------------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# ---------------------------------------------------------------------------
# APLICACIONES
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.sites",
]

THIRD_PARTY_APPS = [
    "crispy_forms",
    "crispy_tailwind",
    "imagekit",
    "django_extensions",
    "django_cleanup.apps.CleanupConfig",
]

LOCAL_APPS = [
    "apps.core",
    "apps.catalog",
    "apps.services",
    "apps.leads",
    "apps.blog",
    "apps.seo",
    "apps.encuestas",
    "apps.dashboard",
    "apps.payments",
    "apps.whatsapp",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ---------------------------------------------------------------------------
# MIDDLEWARE
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.seo.middleware.DynamicRedirectMiddleware",
]

ROOT_URLCONF = "solution_copiers.urls"

# ---------------------------------------------------------------------------
# TEMPLATES
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site_settings",
                "apps.seo.context_processors.design_tokens",
            ],
        },
    },
]

WSGI_APPLICATION = "solution_copiers.wsgi.application"

# ---------------------------------------------------------------------------
# BASE DE DATOS — PostgreSQL obligatorio en todos los entornos
# ---------------------------------------------------------------------------
_db_url = env("DATABASE_URL")
if _db_url.startswith("sqlite"):
    raise RuntimeError(
        "SQLite no está permitido. Configura DATABASE_URL con una URL de PostgreSQL en .env"
    )

DATABASES = {
    "default": env.db("DATABASE_URL"),
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
DATABASES["default"]["CONN_MAX_AGE"] = 60

# ---------------------------------------------------------------------------
# HASHING DE CONTRASEÑAS — Argon2 primero (más robusto que PBKDF2)
# Requiere: pip install argon2-cffi
# ---------------------------------------------------------------------------
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",   # fallback para hashes existentes
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

# ---------------------------------------------------------------------------
# VALIDACIÓN DE CONTRASEÑAS
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# SESIONES Y COOKIES — Configuración segura explícita
# ---------------------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True       # JS no puede acceder a la cookie de sesión
SESSION_COOKIE_SAMESITE = "Lax"      # Protección CSRF básica en todos los entornos
CSRF_COOKIE_HTTPONLY    = False       # Django requiere False para leer el token en JS
CSRF_COOKIE_SAMESITE    = "Lax"
SESSION_ENGINE          = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE      = 43200      # 12 horas en segundos

# ---------------------------------------------------------------------------
# INTERNACIONALIZACIÓN
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "es"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("es", "Español"),
    ("en", "English"),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

# ---------------------------------------------------------------------------
# ARCHIVOS ESTÁTICOS Y MEDIA
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ---------------------------------------------------------------------------
# DEFAULTS
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SITE_ID = 1

# ---------------------------------------------------------------------------
# CRISPY FORMS
# ---------------------------------------------------------------------------
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

# ---------------------------------------------------------------------------
# EMAIL
# ---------------------------------------------------------------------------
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@solutioncopiers.com")
LEADS_NOTIFICATION_EMAIL = env(
    "LEADS_NOTIFICATION_EMAIL", default="ventas@solutioncopiers.com"
)
SITE_URL = env("SITE_URL", default="https://solutioncopiers.com")

# ---------------------------------------------------------------------------
# IA — ASISTENTE VIRTUAL
# Opción 1 (gratis):  GROQ_API_KEY  → regístrate en https://console.groq.com
# Opción 2 (pago):    ANTHROPIC_API_KEY → https://console.anthropic.com
# Si ambas están, se usa Groq primero.
# ---------------------------------------------------------------------------
GROQ_API_KEY      = env("GROQ_API_KEY",      default="")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")

# ---------------------------------------------------------------------------
# WHATSAPP NOTIFICATIONS — CallMeBot (notificaciones 1-a-1, sin riesgo de baneo)
# Para activar: envía "I allow callmebot to send me messages" al +34 644 71 78 24
# Recibirás tu APIKEY por WhatsApp. Guárdala en .env
# ---------------------------------------------------------------------------
CALLMEBOT_APIKEY = env("CALLMEBOT_APIKEY", default="")
WHATSAPP_NOTIFY_PHONE = env("WHATSAPP_NOTIFY_PHONE", default="")

# ---------------------------------------------------------------------------
# WOMPI — Pasarela de pagos Colombia
# Claves de prueba: https://docs.wompi.co/docs/colombia/
# Reemplazar con claves reales antes de producción.
# ---------------------------------------------------------------------------
WOMPI_PUBLIC_KEY    = env("WOMPI_PUBLIC_KEY",    default="pub_test_REPLACE_WITH_REAL_KEY")
WOMPI_PRIVATE_KEY   = env("WOMPI_PRIVATE_KEY",   default="prv_test_REPLACE_WITH_REAL_KEY")
WOMPI_INTEGRITY_KEY = env("WOMPI_INTEGRITY_KEY", default="test_integrity_REPLACE_ME")
WOMPI_EVENTS_KEY    = env("WOMPI_EVENTS_KEY",    default="test_events_REPLACE_ME")

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {module}:{lineno} — {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "apps.auth": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
