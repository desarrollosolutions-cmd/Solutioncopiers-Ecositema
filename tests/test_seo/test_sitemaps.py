"""Tests del sitemap y robots."""
import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestSitemap:
    def test_sitemap_xml_responde_200(self, client):
        response = client.get(reverse("sitemap"))
        assert response.status_code == 200

    def test_robots_txt_responde_200(self, client):
        response = client.get(reverse("robots"))
        assert response.status_code == 200
