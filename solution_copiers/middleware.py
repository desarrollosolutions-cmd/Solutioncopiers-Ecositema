"""
Middleware de cabeceras HTTP de seguridad.
Añade CSP, Permissions-Policy y otras cabeceras de hardening.
Solo activo en producción (cargado desde production.py).
"""
from __future__ import annotations

from django.conf import settings


class SecurityHeadersMiddleware:
    """
    Inyecta cabeceras de seguridad adicionales que Django no añade por defecto:
    - Content-Security-Policy
    - Permissions-Policy
    - Cross-Origin-Opener-Policy
    - Cross-Origin-Resource-Policy
    """

    def __init__(self, get_response):
        self.get_response    = get_response
        self.csp             = getattr(settings, "CONTENT_SECURITY_POLICY", "")
        self.permissions     = getattr(settings, "PERMISSIONS_POLICY", "")

    def __call__(self, request):
        response = self.get_response(request)

        if self.csp:
            response["Content-Security-Policy"] = self.csp

        if self.permissions:
            response["Permissions-Policy"] = self.permissions

        response["Cross-Origin-Opener-Policy"]   = "same-origin"
        response["Cross-Origin-Resource-Policy"]  = "same-origin"
        response["Cross-Origin-Embedder-Policy"]  = "require-corp"

        return response
