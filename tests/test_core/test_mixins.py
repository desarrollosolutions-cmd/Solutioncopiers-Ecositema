"""Tests de los mixins."""
import pytest
from tests.factories import CopierFactory


@pytest.mark.django_db
class TestSluggableModel:
    def test_slug_se_genera_automaticamente(self):
        copier = CopierFactory(name="Ricoh MP 2554 Multifuncional")
        assert copier.slug
        assert "ricoh-mp-2554" in copier.slug

    def test_slug_evita_colisiones(self):
        a = CopierFactory(name="Equipo Idéntico")
        b = CopierFactory(name="Equipo Idéntico")
        assert a.slug != b.slug


@pytest.mark.django_db
class TestSEOModel:
    def test_get_meta_title_usa_meta_title_si_existe(self):
        c = CopierFactory(meta_title="Mi Título SEO")
        assert c.get_meta_title() == "Mi Título SEO"

    def test_get_meta_title_fallback_a_name(self):
        c = CopierFactory(meta_title="", name="Ricoh MP 2554")
        assert c.get_meta_title() == "Ricoh MP 2554"


@pytest.mark.django_db
class TestPublishableModel:
    def test_manager_published_filtra_drafts(self):
        from apps.catalog.models import Copier
        CopierFactory(status="draft")
        CopierFactory(status="published")
        CopierFactory(status="published")
        assert Copier.objects.count() == 3
        assert Copier.published.count() == 2
