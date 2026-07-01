"""Modelos del módulo SEO: redirecciones y Design Tokens."""
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFill

from apps.core.models import TimeStampedModel


HEX_VALIDATOR = RegexValidator(
    regex=r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$",
    message=_("Debe ser un color HEX válido (ej: #1A2B3C)."),
)


class RedirectRule(TimeStampedModel):
    class RedirectType(models.IntegerChoices):
        PERMANENT = 301, _("301 Permanente")
        TEMPORARY = 302, _("302 Temporal")

    old_path = models.CharField(_("ruta antigua"), max_length=500, unique=True)
    new_path = models.CharField(_("ruta nueva"), max_length=500)
    redirect_type = models.IntegerField(choices=RedirectType.choices, default=RedirectType.PERMANENT)
    is_active = models.BooleanField(default=True)
    hits = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _("Regla de redirección")
        verbose_name_plural = _("Reglas de redirección")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["old_path", "is_active"])]

    def __str__(self):
        return f"{self.old_path} → {self.new_path} ({self.redirect_type})"


class DesignTokens(TimeStampedModel):
    """Design Tokens corporativos editables desde admin (singleton)."""

    name = models.CharField(_("nombre del tema"), max_length=80, default="Solution Copiers Corporate")

    # === PALETA CORPORATIVA ===
    color_primary = models.CharField(
        _("color primario (Rojo intenso)"), max_length=7,
        default="#C4121A", validators=[HEX_VALIDATOR],
    )
    color_primary_dark = models.CharField(
        _("primario oscuro (Vinotinto)"), max_length=7,
        default="#5A0B0B", validators=[HEX_VALIDATOR],
    )
    color_primary_light = models.CharField(
        _("primario claro (Rojo medio)"), max_length=7,
        default="#D94048", validators=[HEX_VALIDATOR],
    )
    color_accent = models.CharField(
        _("color de acento (Dorado cálido)"), max_length=7,
        default="#C47A0A", validators=[HEX_VALIDATOR],
    )
    color_accent_dark = models.CharField(
        _("acento oscuro"), max_length=7,
        default="#9A5E06", validators=[HEX_VALIDATOR],
    )
    color_success = models.CharField(default="#2E7D32", max_length=7, validators=[HEX_VALIDATOR])
    color_warning = models.CharField(default="#E89A3C", max_length=7, validators=[HEX_VALIDATOR])
    color_danger = models.CharField(default="#C4121A", max_length=7, validators=[HEX_VALIDATOR])

    # === NEUTROS ===
    color_bg = models.CharField(_("fondo principal"), max_length=7, default="#FFFFFF", validators=[HEX_VALIDATOR])
    color_bg_alt = models.CharField(_("fondo alternativo"), max_length=7, default="#FBF5F5", validators=[HEX_VALIDATOR])
    color_surface = models.CharField(_("superficie de cards"), max_length=7, default="#FFFFFF", validators=[HEX_VALIDATOR])
    color_text_primary = models.CharField(_("texto principal"), max_length=7, default="#1C0B0B", validators=[HEX_VALIDATOR])
    color_text_secondary = models.CharField(_("texto secundario"), max_length=7, default="#6B5252", validators=[HEX_VALIDATOR])
    color_text_muted = models.CharField(_("texto atenuado"), max_length=7, default="#9C8080", validators=[HEX_VALIDATOR])
    color_border = models.CharField(_("bordes"), max_length=7, default="#EDD5D5", validators=[HEX_VALIDATOR])

    # === TIPOGRAFÍA ===
    font_display = models.CharField(_("fuente display"), max_length=100,
                                     default="'Fraunces', Georgia, serif")
    font_body = models.CharField(_("fuente cuerpo"), max_length=100,
                                  default="'Inter', system-ui, sans-serif")
    font_mono = models.CharField(_("fuente monoespaciada"), max_length=100,
                                  default="'JetBrains Mono', 'Fira Code', monospace")
    google_fonts_url = models.URLField(
        _("URL de Google Fonts"), blank=True,
        default=("https://fonts.googleapis.com/css2?"
                 "family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700"
                 "&family=Inter:wght@400;500;600;700&display=swap"),
    )

    # === SPACING ===
    spacing_base = models.PositiveSmallIntegerField(_("unidad base de spacing (px)"), default=4)
    border_radius_base = models.PositiveSmallIntegerField(_("radio borde base"), default=12)
    border_radius_lg = models.PositiveSmallIntegerField(_("radio grande"), default=24)

    # === GLASSMORPHISM ===
    glass_blur_amount = models.PositiveSmallIntegerField(_("intensidad blur"), default=16)
    glass_opacity = models.DecimalField(_("opacidad cristal"), max_digits=3, decimal_places=2, default=0.7)

    # === SOMBRAS ===
    shadow_card = models.CharField(max_length=200, default="0 1px 3px rgba(28, 11, 11, 0.06), 0 4px 20px rgba(28, 11, 11, 0.07)")
    shadow_card_hover = models.CharField(max_length=200, default="0 4px 8px rgba(28, 11, 11, 0.08), 0 16px 40px rgba(196, 18, 26, 0.14)")

    # === ANIMACIONES ===
    animations_enabled = models.BooleanField(_("animaciones activas"), default=True)
    animation_duration_base = models.DecimalField(max_digits=3, decimal_places=2, default=0.6)
    parallax_enabled = models.BooleanField(_("parallax activo"), default=True)
    smooth_scroll_enabled = models.BooleanField(_("smooth scroll"), default=True)

    class Meta:
        verbose_name = _("Design Tokens")
        verbose_name_plural = _("Design Tokens")

    def __str__(self):
        return f"Design Tokens — {self.name}"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def to_css_variables(self) -> str:
        return f"""
        :root {{
            --color-primary: {self.color_primary};
            --color-primary-dark: {self.color_primary_dark};
            --color-primary-light: {self.color_primary_light};
            --color-accent: {self.color_accent};
            --color-accent-dark: {self.color_accent_dark};
            --color-success: {self.color_success};
            --color-warning: {self.color_warning};
            --color-danger: {self.color_danger};
            --color-bg: {self.color_bg};
            --color-bg-alt: {self.color_bg_alt};
            --color-surface: {self.color_surface};
            --color-text-primary: {self.color_text_primary};
            --color-text-secondary: {self.color_text_secondary};
            --color-text-muted: {self.color_text_muted};
            --color-border: {self.color_border};
            --font-display: {self.font_display};
            --font-body: {self.font_body};
            --font-mono: {self.font_mono};
            --spacing-base: {self.spacing_base}px;
            --radius-base: {self.border_radius_base}px;
            --radius-lg: {self.border_radius_lg}px;
            --glass-blur: {self.glass_blur_amount}px;
            --glass-opacity: {self.glass_opacity};
            --shadow-card: {self.shadow_card};
            --shadow-card-hover: {self.shadow_card_hover};
            --duration-base: {self.animation_duration_base}s;
        }}
        """
