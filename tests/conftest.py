"""Fixtures globales de pytest para Solution Copiers."""
import pytest
from django.test import Client


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def design_tokens(db):
    from apps.seo.models import DesignTokens
    return DesignTokens.load()


@pytest.fixture
def site_settings(db):
    from apps.core.models import SiteSettings
    return SiteSettings.load()


@pytest.fixture(autouse=True)
def setup_baseline(design_tokens, site_settings):
    yield
