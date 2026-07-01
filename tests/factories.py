"""Factories para generar datos de prueba realistas."""
from decimal import Decimal

import factory
from factory.django import DjangoModelFactory
from faker import Faker

fake = Faker("es_CO")


class UserFactory(DjangoModelFactory):
    class Meta:
        model = "auth.User"

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda u: f"{u.username}@solutioncopiers.test")


class CopierCategoryFactory(DjangoModelFactory):
    class Meta:
        model = "catalog.CopierCategory"
        django_get_or_create = ("name",)

    name = factory.Iterator([
        "Fotocopiadoras Blanco y Negro",
        "Fotocopiadoras a Color",
        "Multifuncionales A3",
    ])
    description = factory.LazyFunction(lambda: fake.paragraph())
    icon = "printer"
    status = "published"


class CopierFactory(DjangoModelFactory):
    class Meta:
        model = "catalog.Copier"

    name = factory.Sequence(lambda n: f"Ricoh MP {2000 + n} — Multifuncional")
    brand = "Ricoh"
    model_number = factory.Sequence(lambda n: f"MP {2000 + n}")
    category = factory.SubFactory(CopierCategoryFactory)
    short_description = factory.LazyFunction(lambda: fake.sentence(nb_words=10))
    description = factory.LazyFunction(lambda: fake.paragraph(nb_sentences=5))
    toner_type = "bw"
    paper_size = "both"
    speed_ppm = 25
    monthly_duty_cycle = 75000
    available_for_rental = True
    monthly_rental_price = Decimal("350000")
    pages_included_monthly = 2500
    extra_page_cost = Decimal("45")
    status = "published"


class CablingServiceFactory(DjangoModelFactory):
    class Meta:
        model = "catalog.CablingService"

    name = factory.Iterator([
        "Puntos de Red Lógica Cat 6A",
        "Puntos Eléctricos Regulados",
        "Certificación Cat 6A",
    ])
    short_description = factory.LazyFunction(lambda: fake.sentence())
    description = factory.LazyFunction(lambda: fake.paragraph())
    base_price = Decimal("180000")
    status = "published"


class LeadFactory(DjangoModelFactory):
    class Meta:
        model = "leads.Lead"

    full_name = factory.LazyFunction(fake.name)
    email = factory.LazyAttribute(lambda l: f"{l.full_name.lower().replace(' ', '.')}@empresa.test")
    phone = "+57 300 123 4567"
    company_name = factory.LazyFunction(fake.company)
    city = "Medellín"
    gdpr_consent = True


class QuoteFactory(DjangoModelFactory):
    class Meta:
        model = "leads.Quote"

    lead = factory.SubFactory(LeadFactory)
    interest_area = "rental"
    estimated_total = Decimal("700000")
