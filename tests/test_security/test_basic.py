"""Tests básicos de seguridad."""
import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestSecurity:
    def test_admin_requiere_autenticacion(self, client):
        response = client.get("/panel-admin-sc/")
        assert response.status_code in (302, 301)

    def test_x_frame_options(self, client):
        response = client.get(reverse("core:home"))
        assert response.get("X-Frame-Options") in ("DENY", "SAMEORIGIN")
