"""Modelos del Silo 1: Hardware e Infraestructura Física."""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.core.models import (
    FeatureableModel, MainImageModel, OrderableModel,
    PublishableModel, SEOModel, SluggableModel, TimeStampedModel,
)


class CopierCategory(
    TimeStampedModel, SluggableModel, SEOModel, OrderableModel, PublishableModel
):
    name = models.CharField(_("nombre"), max_length=120)
    description = models.TextField(_("descripción"))
    icon = models.CharField(_("ícono Lucide"), max_length=50, blank=True)

    class Meta:
        verbose_name = _("Categoría de fotocopiadora")
        verbose_name_plural = _("Categorías de fotocopiadoras")
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:rental_category", kwargs={"category_slug": self.slug})


class Copier(
    TimeStampedModel, SluggableModel, SEOModel, MainImageModel,
    PublishableModel, FeatureableModel, OrderableModel,
):
    class TonerType(models.TextChoices):
        BW = "bw", _("Blanco y negro")
        COLOR = "color", _("Color")
        BOTH = "both", _("Blanco y negro + Color")

    class PaperSize(models.TextChoices):
        A4 = "a4", _("A4 (Carta)")
        A3 = "a3", _("A3 (Tabloide)")
        BOTH = "both", _("A4 + A3")

    name = models.CharField(_("nombre"), max_length=160)
    brand = models.CharField(_("marca"), max_length=60, default="Ricoh")
    model_number = models.CharField(_("número de modelo"), max_length=80)
    category = models.ForeignKey(
        CopierCategory, on_delete=models.PROTECT, related_name="copiers",
    )

    short_description = models.CharField(_("descripción corta"), max_length=250)
    description = models.TextField(_("descripción completa"))

    toner_type = models.CharField(max_length=10, choices=TonerType.choices, default=TonerType.BW)
    paper_size = models.CharField(max_length=10, choices=PaperSize.choices, default=PaperSize.A4)
    speed_ppm = models.PositiveSmallIntegerField(_("velocidad (ppm)"))
    monthly_duty_cycle = models.PositiveIntegerField(_("ciclo mensual"), default=10000)
    has_scanner = models.BooleanField(_("incluye escáner"), default=True)
    has_duplex = models.BooleanField(_("impresión dúplex"), default=True)
    has_network = models.BooleanField(_("conexión de red"), default=True)
    has_wifi = models.BooleanField(_("WiFi"), default=False)

    available_for_rental = models.BooleanField(default=True)
    available_for_sale = models.BooleanField(default=False)
    monthly_rental_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )
    sale_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )
    pages_included_monthly = models.PositiveIntegerField(default=0)
    extra_page_cost = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
    )

    datasheet_pdf = models.FileField(upload_to="datasheets/", blank=True, null=True)

    class Meta:
        verbose_name = _("Fotocopiadora")
        verbose_name_plural = _("Fotocopiadoras")
        ordering = ["order", "name"]
        indexes = [
            models.Index(fields=["available_for_rental", "status"]),
            models.Index(fields=["available_for_sale", "status"]),
            models.Index(fields=["category", "status"]),
        ]

    def __str__(self):
        return f"{self.brand} {self.model_number} — {self.name}"

    def get_absolute_url(self):
        if self.available_for_rental:
            return reverse("catalog:copier_detail_rental", kwargs={"slug": self.slug})
        return reverse("catalog:copier_detail_sale", kwargs={"slug": self.slug})

    @property
    def monthly_rental_price_formatted(self) -> str:
        if not self.monthly_rental_price:
            return _("Cotizar")
        return f"${self.monthly_rental_price:,.0f} COP / mes"


class CopierImage(TimeStampedModel, OrderableModel):
    copier = models.ForeignKey(Copier, on_delete=models.CASCADE, related_name="gallery_images")
    image = models.ImageField(upload_to="copiers/gallery/")
    alt_text = models.CharField(max_length=200, blank=True)
    caption = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = _("Imagen de galería")
        ordering = ["order"]


class Consumable(
    TimeStampedModel, SluggableModel, SEOModel, MainImageModel,
    PublishableModel, OrderableModel, FeatureableModel,
):
    class ConsumableType(models.TextChoices):
        TONER_BN = "toner_bn", _("Tóner B/N")
        TONER_COLOR = "toner_color", _("Tóner Color")
        INK = "ink", _("Tinta / Botella")
        DRUM = "drum", _("Tambor / Cilindro")
        FUSER = "fuser", _("Banda fusora / Fusor")
        DEVELOPER = "developer", _("Revelador")
        ROLLER = "roller", _("Rodillo")
        BLADE = "blade", _("Cuchilla")
        CHIP = "chip", _("Chip")
        KIT = "kit", _("Kit de mantenimiento")
        OTHER = "other", _("Otro repuesto")

    name = models.CharField(_("nombre"), max_length=200)
    short_description = models.CharField(_("descripción corta"), max_length=300, blank=True)
    consumable_type = models.CharField(
        _("tipo"), max_length=20, choices=ConsumableType.choices, default=ConsumableType.TONER_BN
    )
    brand = models.CharField(_("marca"), max_length=60, default="Ricoh")
    part_number = models.CharField(_("código / referencia"), max_length=100, blank=True)
    compatible_models = models.ManyToManyField(Copier, related_name="consumables", blank=True)
    yield_pages = models.PositiveIntegerField(_("rendimiento (páginas)"), null=True, blank=True)
    description = models.TextField(_("descripción"), blank=True)

    # Tres niveles de precio según tipo de cliente
    price = models.DecimalField(
        _("precio público (nivel 1)"), max_digits=12, decimal_places=2, null=True, blank=True
    )
    price_business = models.DecimalField(
        _("precio empresa (nivel 2)"), max_digits=12, decimal_places=2, null=True, blank=True
    )
    price_wholesale = models.DecimalField(
        _("precio mayorista (nivel 3)"), max_digits=12, decimal_places=2, null=True, blank=True
    )
    price_on_request = models.BooleanField(_("precio bajo solicitud"), default=False)
    in_stock = models.BooleanField(_("en stock"), default=True)
    stock_quantity = models.PositiveIntegerField(_("cantidad en stock"), default=0)

    class Meta:
        verbose_name = _("Consumible")
        verbose_name_plural = _("Consumibles")
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.name} ({self.part_number or 'sin código'})"

    def get_absolute_url(self):
        return reverse("catalog:consumable_detail", kwargs={"slug": self.slug})


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        IN         = "in",         _("Entrada")
        OUT        = "out",        _("Salida")
        ADJUSTMENT = "adjustment", _("Ajuste manual")

    consumable    = models.ForeignKey(Consumable, on_delete=models.CASCADE, related_name="movements", verbose_name=_("consumible"))
    movement_type = models.CharField(_("tipo"), max_length=15, choices=MovementType.choices)
    quantity      = models.IntegerField(_("cantidad"))  # positivo = entrada, negativo = salida
    notes         = models.CharField(_("notas"), max_length=300, blank=True)
    created_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="stock_movements", verbose_name=_("registrado por")
    )
    created_at    = models.DateTimeField(_("fecha"), auto_now_add=True)

    class Meta:
        verbose_name         = _("Movimiento de stock")
        verbose_name_plural  = _("Movimientos de stock")
        ordering             = ["-created_at"]

    def __str__(self):
        return f"{self.get_movement_type_display()} {self.quantity:+d} — {self.consumable.name}"


class CopierUnit(TimeStampedModel):
    """Unidad física individual de una fotocopiadora en inventario."""

    class UnitStatus(models.TextChoices):
        AVAILABLE   = "available",   _("Disponible")
        IN_FIELD    = "in_field",    _("En campo (cliente)")
        MAINTENANCE = "maintenance", _("En mantenimiento")
        RETIRED     = "retired",     _("Dado de baja")

    class Condition(models.TextChoices):
        NEW       = "new",       _("Nuevo")
        EXCELLENT = "excellent", _("Excelente")
        GOOD      = "good",      _("Bueno")
        FAIR      = "fair",      _("Regular")
        POOR      = "poor",      _("Deteriorado")

    copier          = models.ForeignKey(
        Copier, on_delete=models.PROTECT,
        related_name="units", verbose_name=_("modelo"),
    )
    serial_number   = models.CharField(_("serial"), max_length=80, unique=True)
    status          = models.CharField(
        _("estado"), max_length=15,
        choices=UnitStatus.choices, default=UnitStatus.AVAILABLE, db_index=True,
    )
    condition       = models.CharField(
        _("condición"), max_length=15,
        choices=Condition.choices, default=Condition.GOOD,
    )
    acquisition_date = models.DateField(_("fecha de adquisición"), null=True, blank=True)
    location_notes  = models.CharField(_("ubicación / notas"), max_length=300, blank=True)
    current_meter   = models.PositiveIntegerField(
        _("contador actual (páginas)"), default=0,
        help_text=_("Último contador conocido del equipo."),
    )

    class Meta:
        verbose_name = _("Unidad de equipo")
        verbose_name_plural = _("Unidades de equipos")
        ordering = ["status", "copier__brand", "serial_number"]

    def __str__(self):
        return f"{self.copier.brand} {self.copier.model_number} — SN: {self.serial_number}"


class CablingService(
    TimeStampedModel, SluggableModel, SEOModel, MainImageModel,
    PublishableModel, OrderableModel, FeatureableModel,
):
    name = models.CharField(max_length=160)
    icon = models.CharField(max_length=50, blank=True)
    short_description = models.CharField(max_length=250)
    description = models.TextField()
    features = models.JSONField(default=list, blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    requires_quote = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Servicio de cableado")
        verbose_name_plural = _("Servicios de cableado")
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:cabling_detail", kwargs={"slug": self.slug})
