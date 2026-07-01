"""Tests del sistema de filtrado."""
from decimal import Decimal
import pytest

from apps.catalog.filters import CopierFilters
from apps.catalog.models import Copier
from tests.factories import CopierCategoryFactory, CopierFactory


@pytest.mark.django_db
class TestCopierFilters:
    @pytest.fixture
    def populated_db(self):
        cat_bw = CopierCategoryFactory(name="BW")
        cat_color = CopierCategoryFactory(name="Color")
        CopierFactory(category=cat_bw, toner_type="bw", speed_ppm=20, monthly_rental_price=Decimal("250000"))
        CopierFactory(category=cat_color, toner_type="color", speed_ppm=35, monthly_rental_price=Decimal("750000"))

    def test_filtro_toner_type(self, populated_db):
        result = CopierFilters.by_toner_type(Copier.published.all(), "bw")
        assert result.count() == 1

    def test_filtros_invalidos_se_ignoran(self, populated_db):
        result = CopierFilters.by_price_range(Copier.published.all(), "no-es-numero", "tampoco")
        assert result.count() == Copier.published.count()


@pytest.mark.django_db
class TestCatalogViews:
    def test_rental_list_renderiza_200(self, client):
        from django.urls import reverse
        response = client.get(reverse("catalog:rental_list"))
        assert response.status_code == 200
