"""Modelos del Silo 2: Software y Servicios Digitales."""
from __future__ import annotations

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.core.models import (
    FeatureableModel, MainImageModel, OrderableModel,
    PublishableModel, SEOModel, SluggableModel, TimeStampedModel,
)


class Technology(TimeStampedModel, OrderableModel):
    class Category(models.TextChoices):
        BACKEND = "backend", _("Backend")
        FRONTEND = "frontend", _("Frontend")
        MOBILE = "mobile", _("Móvil")
        DATABASE = "database", _("Base de datos")
        CLOUD = "cloud", _("Cloud / Infraestructura")
        DEVOPS = "devops", _("DevOps")

    name = models.CharField(max_length=80)
    category = models.CharField(max_length=20, choices=Category.choices)
    logo = models.FileField(upload_to="tech/", blank=True, null=True)
    proficiency_level = models.PositiveSmallIntegerField(default=80)

    class Meta:
        verbose_name = _("Tecnología")
        verbose_name_plural = _("Tecnologías")
        ordering = ["category", "order", "name"]

    def __str__(self):
        return self.name


class DigitalServiceBase(
    TimeStampedModel, SluggableModel, SEOModel, MainImageModel,
    PublishableModel, OrderableModel, FeatureableModel,
):
    name = models.CharField(max_length=160)
    icon = models.CharField(max_length=50, blank=True)
    tagline = models.CharField(max_length=200, blank=True)
    short_description = models.CharField(max_length=250)
    description = models.TextField()
    benefits = models.JSONField(default=list, blank=True)
    deliverables = models.JSONField(default=list, blank=True)
    estimated_duration = models.CharField(max_length=80, blank=True)
    starting_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    technologies = models.ManyToManyField(Technology, blank=True, related_name="%(class)s_services")

    class Meta:
        abstract = True
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class SoftwareService(DigitalServiceBase):
    class SoftwareType(models.TextChoices):
        CUSTOM = "custom", _("Software a la medida")
        ERP = "erp", _("ERP")
        CRM = "crm", _("CRM")
        API_INTEGRATION = "api", _("Integración de APIs")
        AUTOMATION = "automation", _("Automatización")

    software_type = models.CharField(max_length=20, choices=SoftwareType.choices, default=SoftwareType.CUSTOM)

    class Meta:
        verbose_name = _("Servicio de software")
        ordering = ["order", "name"]

    def get_absolute_url(self):
        return reverse("services:software_detail", kwargs={"slug": self.slug})


class WebService(DigitalServiceBase):
    class WebType(models.TextChoices):
        CORPORATE = "corporate", _("Sitio corporativo")
        ECOMMERCE = "ecommerce", _("E-commerce")
        LANDING = "landing", _("Landing page")
        WEBAPP = "webapp", _("Aplicación web")

    web_type = models.CharField(max_length=20, choices=WebType.choices, default=WebType.CORPORATE)

    class Meta:
        verbose_name = _("Servicio web")
        ordering = ["order", "name"]

    def get_absolute_url(self):
        return reverse("services:web_design_detail", kwargs={"slug": self.slug})


class MobileService(DigitalServiceBase):
    class MobileType(models.TextChoices):
        NATIVE_IOS = "ios", _("Nativa iOS")
        NATIVE_ANDROID = "android", _("Nativa Android")
        NATIVE_BOTH = "native_both", _("Nativa iOS + Android")
        HYBRID = "hybrid", _("Híbrida (Flutter / React Native)")
        PWA = "pwa", _("PWA")

    mobile_type = models.CharField(max_length=20, choices=MobileType.choices, default=MobileType.HYBRID)

    class Meta:
        verbose_name = _("Servicio móvil")
        ordering = ["order", "name"]

    def get_absolute_url(self):
        return reverse("services:mobile_app_detail", kwargs={"slug": self.slug})


class DatabaseService(DigitalServiceBase):
    class DatabaseType(models.TextChoices):
        DESIGN = "design", _("Diseño y modelado")
        MIGRATION = "migration", _("Migración a cloud")
        OPTIMIZATION = "optimization", _("Optimización")
        ADMIN = "admin", _("Administración")

    database_type = models.CharField(max_length=20, choices=DatabaseType.choices, default=DatabaseType.DESIGN)
    engines_supported = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = _("Servicio de base de datos")
        ordering = ["order", "name"]

    def get_absolute_url(self):
        return reverse("services:database_detail", kwargs={"slug": self.slug})


class CaseStudy(
    TimeStampedModel, SluggableModel, SEOModel, MainImageModel,
    PublishableModel, OrderableModel, FeatureableModel,
):
    title = models.CharField(max_length=200)
    client_name = models.CharField(max_length=150)
    client_industry = models.CharField(max_length=100)
    challenge = models.TextField()
    solution = models.TextField()
    results = models.TextField()
    results_metrics = models.JSONField(default=list, blank=True)
    technologies_used = models.ManyToManyField(Technology, blank=True)
    project_url = models.URLField(blank=True)

    slug_source_field = "title"

    class Meta:
        verbose_name = _("Caso de éxito")
        verbose_name_plural = _("Casos de éxito")
        ordering = ["order", "-created_at"]

    def __str__(self):
        return f"{self.title} — {self.client_name}"

    def get_absolute_url(self):
        return reverse("core:home")  # placeholder
