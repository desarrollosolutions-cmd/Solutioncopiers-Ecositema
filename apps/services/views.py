"""Vistas del Silo 2: Software."""
from __future__ import annotations

from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_control
from django.views.generic import DetailView, ListView

from apps.core.mixins import BreadcrumbMixin, JsonLDMixin, SEOContextMixin

_LIST_CACHE = method_decorator(cache_control(public=True, max_age=1800), name="dispatch")
_DETAIL_CACHE = method_decorator(cache_control(public=True, max_age=600), name="dispatch")

from .models import (
    CaseStudy, DatabaseService, MobileService,
    SoftwareService, Technology, WebService,
)


class _ServicePillarBaseView(SEOContextMixin, BreadcrumbMixin, JsonLDMixin, ListView):
    paginate_by = 12
    context_object_name = "services"
    schema_type_default = "Service"

    def get_queryset(self):
        return self.model.published.prefetch_related("technologies").order_by("order", "name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["related_cases"] = CaseStudy.published.filter(is_featured=True)[:3]
        context["technologies"] = Technology.objects.all()[:12]
        return context


@_LIST_CACHE
class SoftwareDevelopmentView(_ServicePillarBaseView):
    model = SoftwareService
    template_name = "services/software_development.html"
    meta_title_default = "Desarrollo de Software a la Medida en Colombia"
    meta_description_default = (
        "Desarrollo de software a la medida en Colombia: ERPs, CRMs, "
        "apps web corporativas y bases de datos. Fábrica de software "
        "en Medellín, clientes en todo el país."
    )
    meta_keywords_default = (
        "desarrollo software a la medida Colombia, fábrica software Bogotá, "
        "erp crm Colombia, aplicaciones web empresariales Colombia, "
        "desarrollo software Medellín"
    )

    def extra_jsonld_data(self, context):
        return {
            "serviceType": "Desarrollo de software a la medida",
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

    def get_breadcrumbs(self):
        return [("Inicio", reverse("core:home")), ("Desarrollo de Software", "")]


@_DETAIL_CACHE
class SoftwareServiceDetailView(SEOContextMixin, BreadcrumbMixin, JsonLDMixin, DetailView):
    model = SoftwareService
    template_name = "services/software_detail.html"
    context_object_name = "service"

    def get_queryset(self):
        return SoftwareService.published.prefetch_related("technologies")

    def get_breadcrumbs(self):
        return [
            ("Inicio", reverse("core:home")),
            ("Software", reverse("services:software_development")),
            (self.object.name, ""),
        ]


@_LIST_CACHE
class WebDesignView(_ServicePillarBaseView):
    model = WebService
    template_name = "services/web_design.html"
    meta_title_default = "Diseño de Páginas Web en Colombia | Corporativo"
    meta_description_default = (
        "Diseño y desarrollo de páginas web corporativas, e-commerce y landing "
        "pages para empresas en Colombia. Estudio digital en Medellín, "
        "proyectos en todo el país."
    )
    meta_keywords_default = (
        "diseño páginas web Colombia, agencia web Colombia, "
        "desarrollo web corporativo Bogotá, ecommerce Colombia, "
        "diseño web Medellín"
    )

    def extra_jsonld_data(self, context):
        return {
            "serviceType": "Diseño y desarrollo de páginas web",
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

    def get_breadcrumbs(self):
        return [("Inicio", reverse("core:home")), ("Diseño Web", "")]


@_DETAIL_CACHE
class WebDesignDetailView(SEOContextMixin, BreadcrumbMixin, JsonLDMixin, DetailView):
    model = WebService
    template_name = "services/web_design_detail.html"
    context_object_name = "service"

    def get_queryset(self):
        return WebService.published.prefetch_related("technologies")

    def get_breadcrumbs(self):
        return [
            ("Inicio", reverse("core:home")),
            ("Diseño Web", reverse("services:web_design")),
            (self.object.name, ""),
        ]


@_LIST_CACHE
class MobileAppsView(_ServicePillarBaseView):
    model = MobileService
    template_name = "services/mobile_apps.html"
    meta_title_default = "Desarrollo Apps Móviles Colombia | iOS & Android"
    meta_description_default = (
        "Desarrollo de aplicaciones móviles iOS, Android y multiplataforma "
        "para empresas en Colombia. Equipo en Medellín, clientes "
        "en todo el país. React Native, Flutter y nativas."
    )
    meta_keywords_default = (
        "desarrollo apps móviles Colombia, aplicaciones empresariales Colombia, "
        "flutter react native Colombia, apps android ios Bogotá, "
        "desarrollo móvil Medellín"
    )

    def extra_jsonld_data(self, context):
        return {
            "serviceType": "Desarrollo de aplicaciones móviles",
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

    def get_breadcrumbs(self):
        return [("Inicio", reverse("core:home")), ("Apps Móviles", "")]


@_DETAIL_CACHE
class MobileAppDetailView(SEOContextMixin, BreadcrumbMixin, JsonLDMixin, DetailView):
    model = MobileService
    template_name = "services/mobile_app_detail.html"
    context_object_name = "service"

    def get_queryset(self):
        return MobileService.published.prefetch_related("technologies")

    def get_breadcrumbs(self):
        return [
            ("Inicio", reverse("core:home")),
            ("Apps Móviles", reverse("services:mobile_apps")),
            (self.object.name, ""),
        ]


@_LIST_CACHE
class DatabaseServicesView(_ServicePillarBaseView):
    model = DatabaseService
    template_name = "services/database_services.html"
    meta_title_default = "Bases de Datos Empresariales Colombia | Cloud"
    meta_description_default = (
        "Diseño de bases de datos empresariales y migración cloud para empresas "
        "en Colombia. Equipo técnico en Medellín. PostgreSQL, MongoDB, AWS, GCP."
    )
    meta_keywords_default = (
        "bases de datos empresariales Colombia, migración cloud Colombia, "
        "postgresql mongodb Colombia, arquitectura datos Bogotá, "
        "diseño datos Medellín"
    )

    def extra_jsonld_data(self, context):
        return {
            "serviceType": "Diseño y migración de bases de datos empresariales",
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

    def get_breadcrumbs(self):
        return [("Inicio", reverse("core:home")), ("Bases de Datos", "")]


@_DETAIL_CACHE
class DatabaseServiceDetailView(SEOContextMixin, BreadcrumbMixin, JsonLDMixin, DetailView):
    model = DatabaseService
    template_name = "services/database_detail.html"
    context_object_name = "service"

    def get_queryset(self):
        return DatabaseService.published.prefetch_related("technologies")

    def get_breadcrumbs(self):
        return [
            ("Inicio", reverse("core:home")),
            ("Bases de Datos", reverse("services:database_services")),
            (self.object.name, ""),
        ]
