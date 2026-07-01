"""
Modelos abstractos (mixins) reutilizables en todo el proyecto.
"""
from __future__ import annotations

from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from imagekit.models import ImageSpecField, ProcessedImageField
from imagekit.processors import ResizeToFill, ResizeToFit
from unidecode import unidecode

from .managers import PublishedManager


# ===========================================================================
# 1. TIMESTAMPS
# ===========================================================================
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(_("creado el"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("actualizado el"), auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


# ===========================================================================
# 2. SLUGGABLE
# ===========================================================================
class SluggableModel(models.Model):
    slug = models.SlugField(
        _("slug"), max_length=220, unique=True, db_index=True,
        help_text=_("Se genera automáticamente desde el nombre si se deja vacío."),
    )

    slug_source_field: str = "name"

    class Meta:
        abstract = True

    def _generate_unique_slug(self) -> str:
        source_value = getattr(self, self.slug_source_field, "") or ""
        base_slug = slugify(unidecode(source_value))[:200]
        if not base_slug:
            base_slug = "item"

        slug_candidate = base_slug
        ModelClass = self.__class__
        counter = 1

        while (
            ModelClass.objects.filter(slug=slug_candidate)
            .exclude(pk=self.pk)
            .exists()
        ):
            slug_candidate = f"{base_slug}-{counter}"
            counter += 1

        return slug_candidate


# ===========================================================================
# 3. SEO MIXIN
# ===========================================================================
class SEOModel(models.Model):
    class SchemaType(models.TextChoices):
        PRODUCT = "Product", _("Producto")
        SERVICE = "Service", _("Servicio")
        ARTICLE = "Article", _("Artículo")
        ORGANIZATION = "Organization", _("Organización")
        WEBPAGE = "WebPage", _("Página web genérica")
        FAQ = "FAQPage", _("Página de preguntas frecuentes")

    meta_title = models.CharField(_("título SEO"), max_length=70, blank=True)
    meta_description = models.CharField(_("descripción SEO"), max_length=170, blank=True)
    meta_keywords = models.CharField(_("keywords SEO"), max_length=255, blank=True)
    og_image = ProcessedImageField(
        verbose_name=_("imagen Open Graph"),
        upload_to="seo/og/",
        processors=[ResizeToFill(1200, 630)],
        format="WEBP", options={"quality": 85},
        blank=True, null=True,
    )
    canonical_url = models.URLField(_("URL canónica"), blank=True)
    schema_type = models.CharField(
        _("tipo de schema.org"), max_length=30,
        choices=SchemaType.choices, default=SchemaType.WEBPAGE,
    )
    noindex = models.BooleanField(_("excluir de buscadores"), default=False)

    class Meta:
        abstract = True

    def get_meta_title(self) -> str:
        if self.meta_title:
            return self.meta_title
        for fallback_field in ("name", "title", "headline"):
            value = getattr(self, fallback_field, None)
            if value:
                return str(value)[:70]
        return "Solution Copiers"

    def get_meta_description(self) -> str:
        if self.meta_description:
            return self.meta_description
        for fallback_field in ("description", "summary", "excerpt", "content", "short_description"):
            value = getattr(self, fallback_field, None)
            if value:
                from django.utils.html import strip_tags
                clean = strip_tags(str(value))
                return clean[:160].rsplit(" ", 1)[0] + "..."
        return _(
            "Solution Copiers — Integrador tecnológico B2B en Medellín. "
            "Alquiler de fotocopiadoras Ricoh, cableado estructurado y "
            "desarrollo de software a la medida."
        )

    def get_canonical_url(self, request=None) -> str:
        if self.canonical_url:
            return self.canonical_url
        try:
            path = self.get_absolute_url()
            if request:
                return request.build_absolute_uri(path)
            return path
        except (AttributeError, NotImplementedError):
            return ""


# ===========================================================================
# 4. PUBLISHABLE
# ===========================================================================
class PublishableModel(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Borrador")
        PUBLISHED = "published", _("Publicado")
        ARCHIVED = "archived", _("Archivado")

    status = models.CharField(
        _("estado"), max_length=10,
        choices=Status.choices, default=Status.DRAFT, db_index=True,
    )
    published_at = models.DateTimeField(_("publicado el"), blank=True, null=True, db_index=True)

    objects = models.Manager()
    published = PublishedManager()

    class Meta:
        abstract = True

    @property
    def is_published(self) -> bool:
        return self.status == self.Status.PUBLISHED


# ===========================================================================
# 5. ORDERABLE
# ===========================================================================
class OrderableModel(models.Model):
    order = models.PositiveIntegerField(_("orden"), default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ["order"]


# ===========================================================================
# 6. FEATUREABLE
# ===========================================================================
class FeatureableModel(models.Model):
    is_featured = models.BooleanField(_("destacado"), default=False, db_index=True)

    class Meta:
        abstract = True


# ===========================================================================
# 7. IMAGE MIXIN
# ===========================================================================
class MainImageModel(models.Model):
    main_image = ProcessedImageField(
        verbose_name=_("imagen principal"),
        upload_to="content/originals/",
        processors=[ResizeToFit(2400, 2400)],
        format="WEBP", options={"quality": 90},
        blank=True, null=True,
    )
    main_image_alt = models.CharField(_("texto alternativo"), max_length=200, blank=True)

    image_thumbnail = ImageSpecField(
        source="main_image",
        processors=[ResizeToFill(400, 300)],
        format="WEBP", options={"quality": 80},
    )
    image_card = ImageSpecField(
        source="main_image",
        processors=[ResizeToFill(800, 600)],
        format="WEBP", options={"quality": 82},
    )
    image_hero = ImageSpecField(
        source="main_image",
        processors=[ResizeToFill(1920, 1080)],
        format="WEBP", options={"quality": 85},
    )

    class Meta:
        abstract = True


# ===========================================================================
# 8. MODELOS CONCRETOS INSTITUCIONALES
# ===========================================================================
class SiteSettings(TimeStampedModel):
    """Configuración global del sitio editable desde admin (singleton)."""

    site_name = models.CharField(_("nombre del sitio"), max_length=100)
    tagline = models.CharField(_("tagline"), max_length=200)
    default_meta_description = models.CharField(_("meta description por defecto"), max_length=170)
    default_og_image = ProcessedImageField(
        upload_to="seo/defaults/",
        processors=[ResizeToFill(1200, 630)],
        format="WEBP", options={"quality": 85},
        blank=True, null=True,
    )
    phone_primary = models.CharField(_("teléfono principal"), max_length=30)
    phone_whatsapp = models.CharField(_("WhatsApp"), max_length=30, blank=True)
    email_contact = models.EmailField(_("email de contacto"))
    email_sales = models.EmailField(_("email de ventas"))
    address = models.CharField(_("dirección"), max_length=255)
    city = models.CharField(_("ciudad"), max_length=80, default="Medellín")
    google_maps_url = models.URLField(_("Google Maps URL"), blank=True)
    instagram_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    google_analytics_id = models.CharField(max_length=50, blank=True)
    google_tag_manager_id = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name = _("Configuración del sitio")
        verbose_name_plural = _("Configuración del sitio")

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                "site_name": "Solution Copiers",
                "tagline": "Infraestructura tecnológica para tu empresa",
                "default_meta_description": (
                    "Integrador tecnológico B2B en Medellín. Alquiler de "
                    "fotocopiadoras Ricoh, cableado estructurado y desarrollo "
                    "de software."
                ),
                "phone_primary": "+57 604 000 0000",
                "phone_whatsapp": "+573000000000",
                "email_contact": "contacto@solutioncopiers.com",
                "email_sales": "ventas@solutioncopiers.com",
                "address": "Medellín, Antioquia, Colombia",
            },
        )
        return obj


class Testimonial(TimeStampedModel, PublishableModel, OrderableModel, FeatureableModel):
    """Testimonios de clientes."""

    author_name = models.CharField(_("nombre del cliente"), max_length=120)
    author_role = models.CharField(_("cargo"), max_length=120, blank=True)
    author_company = models.CharField(_("empresa"), max_length=120, blank=True)
    author_photo = ProcessedImageField(
        upload_to="testimonials/",
        processors=[ResizeToFill(200, 200)],
        format="WEBP", options={"quality": 85},
        blank=True, null=True,
    )
    quote = models.TextField(_("testimonio"))
    rating = models.PositiveSmallIntegerField(_("calificación"), default=5)

    class Meta:
        verbose_name = _("Testimonio")
        verbose_name_plural = _("Testimonios")
        ordering = ["order", "-created_at"]

    def __str__(self):
        return f"{self.author_name} — {self.author_company}"
