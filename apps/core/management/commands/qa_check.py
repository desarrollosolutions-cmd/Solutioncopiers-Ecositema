"""Comando de QA rápido."""
from django.core.management.base import BaseCommand
from django.urls import reverse
from django.test import Client


class Command(BaseCommand):
    help = "Ejecuta checks de QA rápidos."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("🔍 Iniciando QA check...\n"))

        passed = 0
        failed = 0

        checks = [
            ("Settings validation", self._check_settings),
            ("URLs críticas responden", self._check_critical_urls),
            ("Sitemap accesible", self._check_sitemap),
            ("Robots.txt válido", self._check_robots),
            ("DesignTokens existe", self._check_design_tokens),
            ("SiteSettings existe", self._check_site_settings),
        ]

        for name, check in checks:
            try:
                check()
                self.stdout.write(self.style.SUCCESS(f"  ✓ {name}"))
                passed += 1
            except AssertionError as e:
                self.stdout.write(self.style.ERROR(f"  ✗ {name}: {e}"))
                failed += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  ⚠ {name}: {e}"))
                failed += 1

        self.stdout.write("\n" + "=" * 50)
        if failed == 0:
            self.stdout.write(self.style.SUCCESS(
                f"✅ TODOS LOS CHECKS PASARON ({passed}/{passed})"
            ))
        else:
            self.stdout.write(self.style.ERROR(
                f"❌ {failed} CHECKS FALLARON ({passed}/{passed + failed})"
            ))

    def _check_settings(self):
        from django.conf import settings
        assert settings.SECRET_KEY, "SECRET_KEY vacía"
        assert hasattr(settings, "DATABASES"), "DATABASES no configurada"

    def _check_critical_urls(self):
        client = Client()
        critical = [
            "core:home",
            "catalog:rental_list",
            "services:software_development",
            "leads:wizard",
        ]
        for url_name in critical:
            response = client.get(reverse(url_name))
            assert response.status_code == 200, (
                f"{url_name} devolvió {response.status_code}"
            )

    def _check_sitemap(self):
        client = Client()
        response = client.get(reverse("sitemap"))
        assert response.status_code == 200, "Sitemap no accesible"

    def _check_robots(self):
        client = Client()
        response = client.get(reverse("robots"))
        assert response.status_code == 200, "Robots.txt no accesible"

    def _check_design_tokens(self):
        from apps.seo.models import DesignTokens
        assert DesignTokens.objects.exists(), "DesignTokens no inicializado"

    def _check_site_settings(self):
        from apps.core.models import SiteSettings
        assert SiteSettings.objects.exists(), "SiteSettings no inicializado"
