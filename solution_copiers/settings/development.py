"""Configuración exclusiva de desarrollo local."""
from .base import *  # noqa: F401, F403

DEBUG = True

INSTALLED_APPS += [  # noqa: F405
    "django_browser_reload",
]

MIDDLEWARE = [
    *MIDDLEWARE,  # noqa: F405
    "django_browser_reload.middleware.BrowserReloadMiddleware",
]

# Email en consola para no enviar correos reales en dev
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Evita requerir manifest pre-compilado de estáticos en desarrollo
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Permitir cualquier host en desarrollo
ALLOWED_HOSTS = ["*"]
