"""Tests de servicios de cotización."""
from decimal import Decimal
import pytest

from apps.leads.services import QuoteCalculator, LeadCreator
from tests.factories import CopierFactory


@pytest.mark.django_db
class TestQuoteCalculator:
    def test_calculate_rental_basico(self):
        copier = CopierFactory(
            monthly_rental_price=Decimal("350000"),
            pages_included_monthly=2500,
            extra_page_cost=Decimal("45"),
        )
        result = QuoteCalculator.calculate_rental({
            "copier_id": copier.id, "quantity": 1, "monthly_pages": 2000,
        })
        assert result == Decimal("350000")

    def test_calculate_cabling(self):
        result = QuoteCalculator.calculate_cabling({
            "logical_points": 10, "electrical_points": 5,
        })
        assert result == Decimal("2900000")

    def test_calculate_software_por_complejidad(self):
        low = QuoteCalculator.calculate_software({"complexity": "low"})
        high = QuoteCalculator.calculate_software({"complexity": "high"})
        assert low < high


@pytest.mark.django_db
class TestLeadCreator:
    def test_create_from_wizard_crea_lead_y_quote(self):
        from apps.leads.models import Lead, Quote

        copier = CopierFactory()
        quote = LeadCreator.create_from_wizard(
            contact_data={
                "full_name": "Test", "email": "test@empresa.test",
                "phone": "+57 300 123 4567", "city": "Medellín",
                "gdpr_consent": True,
            },
            quote_data={"interest_area": "rental"},
            wizard_data={"copier_id": copier.id, "quantity": 1, "monthly_pages": 2000},
        )
        assert Lead.objects.count() == 1
        assert Quote.objects.count() == 1
