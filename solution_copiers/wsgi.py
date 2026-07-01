"""WSGI config for solution_copiers project."""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "solution_copiers.settings.development"
)

application = get_wsgi_application()
