"""Vistas del Silo 1: Catalog."""
from __future__ import annotations

from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import cache_control
from django.views.generic import DetailView, ListView, TemplateView

from apps.core.mixins import BreadcrumbMixin, JsonLDMixin, SEOContextMixin

from .filters import CopierFilters
from .models import CablingService, Consumable, Copier, CopierCategory

_LIST_CACHE = method_decorator(cache_control(public=True, max_age=900), name="dispatch")   # 15 min
_DETAIL_CACHE = method_decorator(cache_control(public=True, max_age=600), name="dispatch")  # 10 min
_STATIC_CACHE = method_decorator(cache_control(public=True, max_age=1800), name="dispatch") # 30 min


class _CopierListBaseView(SEOContextMixin, BreadcrumbMixin, JsonLDMixin, ListView):
    model = Copier
    paginate_by = 12
    context_object_name = "copiers"
    for_rental: bool = True

    def get_queryset(self):
        if self.for_rental:
            base_qs = Copier.published.select_related("category").filter(
                available_for_rental=True
            )
        else:
            base_qs = Copier.published.select_related("category").filter(
                available_for_sale=True
            )

        return CopierFilters.apply_all(
            base_qs, self.request.GET, for_rental=self.for_rental
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = CopierCategory.published.all().order_by("order", "name")
        context["active_filters"] = {
            key: value for key, value in self.request.GET.items() if value
        }
        context["for_rental"] = self.for_rental
        return context


@_LIST_CACHE
class RentalListView(_CopierListBaseView):
    template_name = "catalog/rental_list.html"
    for_rental = True
    meta_title_default = "Alquiler de Impresoras en Colombia | Ricoh B2B — Medellín"
    meta_description_default = (
        "Alquiler de impresoras y fotocopiadoras Ricoh en Colombia — servicio "
        "técnico, insumos y repuestos incluidos. Sede Medellín, cobertura "
        "Bogotá, Cali, Barranquilla y todo el país."
    )
    meta_keywords_default = (
        "alquiler fotocopiadoras Colombia, alquiler impresoras Bogotá, "
        "arrendamiento fotocopiadora Medellín, renting impresoras Colombia, "
        "alquiler ricoh Colombia"
    )

    def get_breadcrumbs(self):
        return [
            ("Inicio", reverse("core:home")),
            ("Alquiler de Fotocopiadoras", ""),
        ]


@_LIST_CACHE
class RentalCategoryView(_CopierListBaseView):
    template_name = "catalog/rental_category.html"
    for_rental = True

    def dispatch(self, request, *args, **kwargs):
        self.category = get_object_or_404(
            CopierCategory.published, slug=kwargs.get("category_slug")
        )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(category=self.category)

    def get_seo_object(self):
        return self.category

    def get_breadcrumbs(self):
        return [
            ("Inicio", reverse("core:home")),
            ("Alquiler", reverse("catalog:rental_list")),
            (self.category.name, ""),
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_category"] = self.category
        return context


@_DETAIL_CACHE
class CopierDetailView(SEOContextMixin, BreadcrumbMixin, JsonLDMixin, DetailView):
    model = Copier
    template_name = "catalog/copier_detail.html"
    context_object_name = "copier"

    def get_queryset(self):
        return Copier.published.select_related("category").prefetch_related(
            "gallery_images", "consumables"
        )

    def get_breadcrumbs(self):
        copier = self.object
        if copier.available_for_rental:
            return [
                ("Inicio", reverse("core:home")),
                ("Alquiler", reverse("catalog:rental_list")),
                (copier.name, ""),
            ]
        return [
            ("Inicio", reverse("core:home")),
            ("Venta", reverse("catalog:sale_list")),
            (copier.name, ""),
        ]

    def extra_jsonld_data(self, context):
        copier = self.object
        data = {
            "@type": "Product",
            "brand": {"@type": "Brand", "name": copier.brand},
            "model": copier.model_number,
        }
        if copier.available_for_rental and copier.monthly_rental_price:
            data["offers"] = {
                "@type": "Offer",
                "priceCurrency": "COP",
                "price": str(copier.monthly_rental_price),
                "availability": "https://schema.org/InStock",
            }
        return data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["related_copiers"] = (
            Copier.published.filter(category=self.object.category)
            .exclude(pk=self.object.pk)[:4]
        )
        return context


@_LIST_CACHE
class SaleListView(_CopierListBaseView):
    template_name = "catalog/sale_list.html"
    for_rental = False
    meta_title_default = "Venta de Fotocopiadoras Ricoh en Colombia | Solution Copiers"
    meta_description_default = (
        "Compra fotocopiadoras Ricoh multifuncionales nuevas y reacondicionadas "
        "en Colombia. Sede Medellín — stock inmediato, garantía y soporte "
        "técnico certificado con despacho nacional."
    )
    meta_keywords_default = (
        "venta fotocopiadoras Colombia, comprar ricoh Colombia, "
        "venta impresoras Bogotá, fotocopiadoras ricoh Medellín, "
        "multifuncionales certificadas Colombia"
    )

    def get_breadcrumbs(self):
        return [
            ("Inicio", reverse("core:home")),
            ("Venta de Fotocopiadoras", ""),
        ]


@_STATIC_CACHE
class TechnicalServiceView(SEOContextMixin, BreadcrumbMixin, JsonLDMixin, TemplateView):
    template_name = "catalog/technical_service.html"
    meta_title_default = "Servicio Técnico Multifuncionales Colombia | SC"
    meta_description_default = (
        "Servicio técnico de multifuncionales e impresoras para empresas "
        "en Colombia. Técnicos certificados Ricoh, base Medellín, "
        "respuesta en 4 h, todas las marcas."
    )
    meta_keywords_default = (
        "servicio tecnico multifuncionales Colombia, mantenimiento fotocopiadoras, "
        "reparacion impresoras Medellín, tecnico ricoh certificado Colombia"
    )
    schema_type_default = "Service"

    def extra_jsonld_data(self, context):
        return {
            "serviceType": "Servicio técnico de impresoras y multifuncionales",
            "provider": {
                "@type": "Organization",
                "name": "Solution Copiers",
                "url": self.request.build_absolute_uri("/"),
            },
            "areaServed": [
                {"@type": "City", "name": "Medellín"},
                {"@type": "AdministrativeArea", "name": "Antioquia"},
                {"@type": "City", "name": "Bogotá"},
                {"@type": "City", "name": "Cali"},
                {"@type": "Country", "name": "Colombia"},
            ],
        }

    def get_breadcrumbs(self):
        return [("Inicio", reverse("core:home")), ("Servicio Técnico", "")]


@_LIST_CACHE
class ConsumablesListView(SEOContextMixin, BreadcrumbMixin, JsonLDMixin, ListView):
    model = Consumable
    template_name = "catalog/consumables_list.html"
    context_object_name = "consumables"
    paginate_by = 16
    meta_title_default = "Tóner e Insumos para Impresoras en Colombia | Solution Copiers"
    meta_description_default = (
        "Tóner original, tambores, fusores e insumos para impresoras en "
        "Colombia. Despacho nacional desde Medellín. Ricoh, HP, Epson, "
        "Kyocera y más marcas."
    )
    meta_keywords_default = (
        "toner ricoh Colombia, insumos impresoras Colombia, "
        "comprar toner Bogotá, repuestos fotocopiadora originales, "
        "consumibles ricoh Medellín"
    )
    schema_type_default = "Service"

    def extra_jsonld_data(self, context):
        return {
            "serviceType": "Venta de insumos y consumibles para impresoras",
            "provider": {
                "@type": "Organization",
                "name": "Solution Copiers",
                "url": self.request.build_absolute_uri("/"),
            },
            "areaServed": [
                {"@type": "City", "name": "Medellín"},
                {"@type": "Country", "name": "Colombia"},
            ],
        }

    paginate_by = 24

    def get_queryset(self):
        qs = Consumable.published.prefetch_related("compatible_models").order_by("order", "name")
        tipo = self.request.GET.get("tipo", "").strip()
        q    = self.request.GET.get("q", "").strip()
        if tipo:
            qs = qs.filter(consumable_type=tipo)
        if q:
            qs = qs.filter(name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tipo_actual"] = self.request.GET.get("tipo", "")
        context["q_actual"]    = self.request.GET.get("q", "")
        context["tipo_choices"] = Consumable.ConsumableType.choices
        return context

    def get_breadcrumbs(self):
        return [("Inicio", reverse("core:home")), ("Consumibles", "")]


@_DETAIL_CACHE
class ConsumableDetailView(SEOContextMixin, BreadcrumbMixin, JsonLDMixin, DetailView):
    model = Consumable
    template_name = "catalog/consumable_detail.html"
    context_object_name = "consumable"

    def get_queryset(self):
        return Consumable.published.prefetch_related("compatible_models")

    def get_breadcrumbs(self):
        return [
            ("Inicio", reverse("core:home")),
            ("Consumibles", reverse("catalog:consumables_list")),
            (self.object.name, ""),
        ]


@_STATIC_CACHE
class StructuredCablingView(SEOContextMixin, BreadcrumbMixin, JsonLDMixin, ListView):
    model = CablingService
    template_name = "catalog/structured_cabling.html"
    context_object_name = "cabling_services"
    meta_title_default = "Cableado Estructurado Colombia | Cat6A Certificado"
    meta_description_default = (
        "Instalación de cableado estructurado Cat6/6A y certificación de redes "
        "en Colombia. Base Medellín — Antioquia y principales ciudades del país. "
        "Puntos de red y eléctricos regulados."
    )
    meta_keywords_default = (
        "cableado estructurado Colombia, instalacion redes cat6 Bogotá, "
        "certificacion redes datos Colombia, cableado estructurado Medellín, "
        "infraestructura red empresarial Colombia"
    )
    schema_type_default = "Service"

    def extra_jsonld_data(self, context):
        return {
            "serviceType": "Instalación y certificación de cableado estructurado",
            "provider": {
                "@type": "Organization",
                "name": "Solution Copiers",
                "url": self.request.build_absolute_uri("/"),
            },
            "areaServed": [
                {"@type": "City", "name": "Medellín"},
                {"@type": "AdministrativeArea", "name": "Antioquia"},
                {"@type": "City", "name": "Bogotá"},
                {"@type": "City", "name": "Cali"},
                {"@type": "Country", "name": "Colombia"},
            ],
        }

    def get_queryset(self):
        return CablingService.published.order_by("order", "name")

    def get_breadcrumbs(self):
        return [("Inicio", reverse("core:home")), ("Cableado Estructurado", "")]


@_DETAIL_CACHE
class CablingDetailView(SEOContextMixin, BreadcrumbMixin, JsonLDMixin, DetailView):
    model = CablingService
    template_name = "catalog/cabling_detail.html"
    context_object_name = "service"

    def get_queryset(self):
        return CablingService.published.all()

    def get_breadcrumbs(self):
        return [
            ("Inicio", reverse("core:home")),
            ("Cableado", reverse("catalog:structured_cabling")),
            (self.object.name, ""),
        ]


class PublicSearchView(View):
    """Búsqueda global pública — devuelve JSON para el modal del navbar."""

    def get(self, request):
        q = request.GET.get("q", "").strip()[:100]
        data = {"q": q, "consumables": [], "copiers": []}

        if len(q) < 2:
            return JsonResponse(data)

        consumables = (
            Consumable.published
            .filter(Q(name__icontains=q) | Q(part_number__icontains=q))
            .order_by("order", "name")[:6]
        )
        for c in consumables:
            data["consumables"].append({
                "name":  c.name,
                "type":  c.get_consumable_type_display(),
                "url":   c.get_absolute_url(),
                "image": c.main_image.url if c.main_image else None,
                "price": str(int(c.price)) if c.price else None,
                "ref":   c.part_number or "",
            })

        copiers = (
            Copier.published
            .filter(Q(name__icontains=q) | Q(model_number__icontains=q))
            .order_by("order", "name")[:4]
        )
        for c in copiers:
            data["copiers"].append({
                "name":  c.name,
                "model": c.model_number,
                "url":   c.get_absolute_url(),
                "image": c.main_image.url if c.main_image else None,
            })

        return JsonResponse(data)
