"""Middleware de redirecciones dinámicas."""
import logging
from django.db.models import F
from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect

logger = logging.getLogger(__name__)


class DynamicRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if response.status_code == 404:
            try:
                from .models import RedirectRule
                rule = RedirectRule.objects.filter(
                    old_path=request.path, is_active=True
                ).first()
                if rule:
                    RedirectRule.objects.filter(pk=rule.pk).update(hits=F("hits") + 1)
                    if rule.redirect_type == 301:
                        return HttpResponsePermanentRedirect(rule.new_path)
                    return HttpResponseRedirect(rule.new_path)
            except Exception as exc:
                logger.warning("Error en redirect middleware: %s", exc)

        return response
