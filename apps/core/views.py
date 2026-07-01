"""Vistas del módulo Core."""
from __future__ import annotations

import random

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, TemplateView

from apps.core.mixins import BreadcrumbMixin, JsonLDMixin, SEOContextMixin
from apps.core.models import Testimonial


class HomeView(SEOContextMixin, JsonLDMixin, TemplateView):
    """Home con Bento Grid."""

    template_name = "core/home.html"
    meta_title_default = "Alquiler de Fotocopiadoras en Colombia | Solution Copiers"
    meta_description_default = (
        "Alquiler de fotocopiadoras Ricoh, cableado estructurado Cat6A y "
        "software a la medida para empresas en Colombia. Sede Medellín, "
        "atendemos Bogotá, Cali, Barranquilla y todo el país."
    )
    meta_keywords_default = (
        "alquiler fotocopiadoras Colombia, fotocopiadoras Medellín, "
        "alquiler impresoras Bogotá, cableado estructurado Colombia, "
        "desarrollo software Colombia, integrador tecnológico B2B"
    )
    schema_type_default = "Organization"

    def get_context_data(self, **kwargs):
        from apps.catalog.models import CablingService, Consumable, Copier
        from apps.services.models import (
            CaseStudy, DatabaseService, MobileService,
            SoftwareService, Technology, WebService,
        )
        from apps.blog.models import Post

        context = super().get_context_data(**kwargs)

        context["featured_copiers"] = (
            Copier.published.filter(is_featured=True)
            .select_related("category")[:6]
        )

        # Pool amplio de consumibles → 8 aleatorios en cada carga
        _cons_pool = list(
            Consumable.published
            .order_by("consumable_type", "order")[:80]
        )
        context["featured_consumables"] = random.sample(_cons_pool, min(8, len(_cons_pool)))

        # Grupos de consumibles para mostrar categorías
        context["consumable_type_counts"] = {
            "toner": Consumable.published.filter(
                consumable_type__in=["toner_bn", "toner_color"]
            ).count(),
            "ink": Consumable.published.filter(consumable_type="ink").count(),
            "parts": Consumable.published.filter(
                consumable_type__in=["drum", "fuser", "roller", "blade", "developer", "chip", "kit", "other"]
            ).count(),
        }
        context["featured_cabling"] = CablingService.published.filter(
            is_featured=True
        ).order_by("order")[:3]

        context["featured_software"] = SoftwareService.published.filter(is_featured=True)[:2]
        context["featured_web"] = WebService.published.filter(is_featured=True)[:2]
        context["featured_mobile"] = MobileService.published.filter(is_featured=True)[:1]
        context["featured_database"] = DatabaseService.published.filter(is_featured=True)[:1]

        context["featured_cases"] = CaseStudy.published.filter(is_featured=True)[:3]
        context["testimonials"] = Testimonial.objects.filter(
            status="published", is_featured=True
        ).order_by("order")[:6]

        context["technologies"] = Technology.objects.all().order_by("category", "order")[:12]
        context["latest_posts"] = Post.published.select_related("category")[:3]

        return context

    def get_jsonld_data(self, context):
        """Genera un @graph completo: LocalBusiness + Corporation + WebSite + WebPage."""
        site = context.get("site_settings")
        request = self.request
        base_url = request.build_absolute_uri("/")
        canonical = request.build_absolute_uri()
        seo = context.get("seo", {})

        same_as = []
        if site:
            for attr in ("instagram_url", "facebook_url", "linkedin_url"):
                val = getattr(site, attr, "") or ""
                if val.startswith("http"):
                    same_as.append(val)

        org: dict = {
            "@type": ["LocalBusiness", "Corporation"],
            "@id": base_url + "#organization",
            "name": site.site_name if site else "Solution Copiers",
            "description": (
                "Integrador tecnológico B2B en Medellín especializado en alquiler "
                "de impresoras Ricoh, cableado estructurado Cat6A y desarrollo de "
                "software a la medida para empresas en Colombia."
            ),
            "url": base_url,
            "areaServed": [
                {"@type": "City", "name": "Medellín"},
                {"@type": "AdministrativeArea", "name": "Antioquia"},
                {"@type": "City", "name": "Bogotá"},
                {"@type": "City", "name": "Cali"},
                {"@type": "City", "name": "Barranquilla"},
                {"@type": "City", "name": "Bucaramanga"},
                {"@type": "City", "name": "Pereira"},
                {"@type": "Country", "name": "Colombia"},
            ],
            "knowsAbout": [
                "Alquiler de impresoras y fotocopiadoras Ricoh",
                "Servicio técnico de multifuncionales",
                "Insumos y repuestos originales para impresoras",
                "Instalación de cableado estructurado Cat6/6A",
                "Puntos de red lógica y eléctricos",
                "Certificación de redes de datos",
                "Desarrollo de software a la medida",
                "Aplicaciones web corporativas",
                "Diseño de bases de datos empresariales",
            ],
            "hasOfferCatalog": {
                "@type": "OfferCatalog",
                "name": "Catálogo de Servicios Solution Copiers",
                "itemListElement": [
                    {
                        "@type": "Offer",
                        "itemOffered": {
                            "@type": "Service",
                            "name": "Alquiler de Impresoras en Colombia",
                            "url": request.build_absolute_uri(
                                "/alquiler-fotocopiadoras-medellin/"
                            ),
                        },
                    },
                    {
                        "@type": "Offer",
                        "itemOffered": {
                            "@type": "Service",
                            "name": "Cableado Estructurado Colombia",
                            "url": request.build_absolute_uri(
                                "/cableado-estructurado-medellin/"
                            ),
                        },
                    },
                    {
                        "@type": "Offer",
                        "itemOffered": {
                            "@type": "Service",
                            "name": "Desarrollo de Software a la Medida Colombia",
                            "url": request.build_absolute_uri(
                                "/desarrollo-software-medellin/"
                            ),
                        },
                    },
                ],
            },
        }

        if site:
            if getattr(site, "phone_primary", ""):
                org["telephone"] = site.phone_primary
            if getattr(site, "email_contact", ""):
                org["email"] = site.email_contact
            addr_street = getattr(site, "address", "") or ""
            if addr_street:
                org["address"] = {
                    "@type": "PostalAddress",
                    "streetAddress": addr_street,
                    "addressLocality": getattr(site, "city", "Medellín") or "Medellín",
                    "addressRegion": "Antioquia",
                    "addressCountry": "CO",
                }

        if same_as:
            org["sameAs"] = same_as

        return {
            "@context": "https://schema.org",
            "@graph": [
                org,
                {
                    "@type": "WebSite",
                    "@id": base_url + "#website",
                    "url": base_url,
                    "name": "Solution Copiers",
                    "inLanguage": "es-CO",
                    "publisher": {"@id": base_url + "#organization"},
                },
                {
                    "@type": "WebPage",
                    "@id": canonical + "#webpage",
                    "url": canonical,
                    "name": seo.get("meta_title", "Solution Copiers"),
                    "description": seo.get("meta_description", ""),
                    "isPartOf": {"@id": base_url + "#website"},
                    "about": {"@id": base_url + "#organization"},
                    "inLanguage": "es-CO",
                },
            ],
        }


class SolutionsHubView(SEOContextMixin, BreadcrumbMixin, JsonLDMixin, TemplateView):
    template_name = "core/solutions_hub.html"
    meta_title_default = "Soluciones Empresariales Integrales para Colombia | SC"
    meta_description_default = (
        "Hardware, redes y software en un solo aliado B2B para empresas en "
        "Colombia. Desde Medellín atendemos todo el país: impresoras, "
        "cableado Cat6A y software a la medida."
    )
    schema_type_default = "Service"

    def get_breadcrumbs(self):
        return [
            ("Inicio", reverse("core:home")),
            ("Soluciones Empresariales", ""),
        ]

    def get_context_data(self, **kwargs):
        from apps.catalog.models import CablingService, Copier
        from apps.services.models import CaseStudy, SoftwareService, WebService
        context = super().get_context_data(**kwargs)
        context["featured_copiers"] = Copier.published.filter(
            is_featured=True, available_for_rental=True
        ).select_related("category")[:3]
        context["featured_software"] = SoftwareService.published.filter(
            is_featured=True
        )[:3]
        context["featured_cabling"] = CablingService.published.filter(
            is_featured=True
        ).order_by("order")[:3]
        context["case_studies"] = CaseStudy.published.filter(
            is_featured=True
        )[:3]
        return context


_SOLUTION_META = {
    "oficina-llave-en-mano": {
        "title": "Oficina Llave en Mano Colombia | Infraestructura IT Completa",
        "description": (
            "Equipamos tu oficina desde cero: cableado estructurado Cat6A, "
            "fotocopiadoras Ricoh en alquiler, WiFi empresarial y software. "
            "Un solo proveedor, cero fricciones, operativo en 4-6 semanas."
        ),
        "label": "Oficina Llave en Mano",
    },
    "transformacion-digital-pymes": {
        "title": "Transformación Digital para Pymes en Colombia | Solution Copiers",
        "description": (
            "Acompañamos a pymes colombianas en su transformación digital: "
            "automatización de procesos, software a la medida, apps móviles "
            "y presencia web. Resultados medibles desde la primera fase."
        ),
        "label": "Transformación Digital Pymes",
    },
}


class SolutionDetailView(SEOContextMixin, BreadcrumbMixin, JsonLDMixin, TemplateView):
    template_name = "core/solution_detail.html"

    def _meta(self):
        return _SOLUTION_META.get(self.kwargs.get("slug", ""), {})

    @property
    def meta_title_default(self):
        return self._meta().get("title", "Solución Empresarial | Solution Copiers")

    @property
    def meta_description_default(self):
        return self._meta().get(
            "description",
            "Soluciones integrales de tecnología para empresas en Medellín.",
        )

    def get_breadcrumbs(self):
        label = self._meta().get(
            "label",
            self.kwargs.get("slug", "").replace("-", " ").title(),
        )
        return [
            ("Inicio", reverse("core:home")),
            ("Soluciones Empresariales", reverse("core:solutions_hub")),
            (label, ""),
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["slug"] = self.kwargs.get("slug", "")
        return context


class AboutView(SEOContextMixin, BreadcrumbMixin, TemplateView):
    template_name = "core/about.html"
    meta_title_default = "Sobre Nosotros | Solution Copiers — Medellín, Colombia"
    meta_description_default = (
        "Conoce a Solution Copiers: el integrador tecnológico B2B que "
        "combina infraestructura física y software para empresas."
    )

    def get_breadcrumbs(self):
        return [("Inicio", reverse("core:home")), ("Sobre Nosotros", "")]


class ContactView(SEOContextMixin, BreadcrumbMixin, FormView):
    template_name = "core/contact.html"
    meta_title_default = "Contacto | Solution Copiers Colombia"
    meta_description_default = (
        "Contáctanos para alquiler de fotocopiadoras, cableado o software. "
        "Atención corporativa en Colombia — sede Medellín, cobertura nacional."
    )

    def get_form_class(self):
        from apps.leads.forms import ContactForm
        return ContactForm

    def get_breadcrumbs(self):
        return [("Inicio", reverse("core:home")), ("Contacto", "")]

    def form_valid(self, form):
        from apps.leads.services import send_contact_message_email
        send_contact_message_email(form.cleaned_data)
        messages.success(
            self.request,
            "¡Mensaje enviado! Te contactaremos en menos de 24 horas hábiles.",
        )
        return redirect(reverse("core:contact"))

    def form_invalid(self, form):
        messages.error(
            self.request,
            "Por favor corrige los errores indicados.",
        )
        return super().form_invalid(form)


class PrivacyView(SEOContextMixin, TemplateView):
    template_name = "core/legal/privacy.html"
    meta_title_default = "Política de Privacidad | Solution Copiers"


class TermsView(SEOContextMixin, TemplateView):
    template_name = "core/legal/terms.html"
    meta_title_default = "Términos y Condiciones | Solution Copiers"


def error_404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    return render(request, "errors/500.html", status=500)


# ===========================================================================
# ASISTENTE VIRTUAL PÚBLICO — para visitantes del sitio web
# ===========================================================================

_SYSTEM_PUBLIC = """Eres el asistente virtual de **Solution Copiers**, una empresa \
colombiana ubicada en Medellín (Antioquia) que ofrece soluciones tecnológicas B2B \
integrales. Respondes ÚNICAMENTE en español, de forma amable, clara y profesional. \
Eres conciso: respuestas cortas y directas, sin párrafos largos.

=== QUIÉNES SOMOS ===
Solution Copiers es un integrador tecnológico B2B con sede en Medellín. Llevamos \
años ayudando a empresas en Colombia a optimizar sus procesos con tecnología confiable.

=== SERVICIOS PRINCIPALES ===

1. ALQUILER DE FOTOCOPIADORAS RICOH
   - Equipos multifuncionales Ricoh para oficinas, colegios, empresas y copistería
   - Planes de alquiler flexibles (mensual) incluyen mantenimiento preventivo y correctivo
   - Suministro de tóner e insumos incluido en muchos planes
   - Cobertura: Medellín, Antioquia y principales ciudades de Colombia
   - Para cotizar: el cliente llena el formulario en el sitio web o nos contacta

2. VENTA DE CONSUMIBLES E INSUMOS
   - Tóneres B/N y color, tintas, tambores, fusores, rodillos, chips y más
   - Compatibles con Ricoh, HP, Samsung, Lexmark, Canon, Epson y otras marcas
   - Entrega a domicilio en Medellín
   - Precios competitivos al detal y al por mayor

3. CABLEADO ESTRUCTURADO
   - Instalación de redes LAN/WAN, fibra óptica, redes WiFi empresariales
   - Certificación de cableado, rack y patch panels
   - Proyectos para oficinas, bodegas, colegios y centros comerciales

4. DESARROLLO DE SOFTWARE Y WEB
   - Aplicaciones web a la medida (Django, Python)
   - Sitios web corporativos, e-commerce, landing pages
   - Aplicaciones móviles
   - Sistemas de gestión internos (ERP/CRM simplificados)

=== PROCESO PARA SOLICITAR COTIZACIÓN ===
1. El cliente puede llenar el formulario en /cotizador/ (botón "Solicitar cotización" en el sitio)
2. O escribir al WhatsApp / email de la empresa
3. Un asesor responde en menos de 24 horas hábiles

=== CONTACTO ===
- Formulario web: /cotizador/
- Email ventas: ventas@solutioncopiers.com
- Ubicación: Medellín, Antioquia, Colombia

=== INSTRUCCIONES IMPORTANTES ===
- NO inventes precios exactos. Para cotizaciones específicas, dirige siempre al formulario /cotizador/ o al correo ventas@solutioncopiers.com
- Si preguntan por un equipo específico o plan, explica las características generales y guía al formulario
- Si alguien quiere hablar con un asesor humano, dales el email ventas@solutioncopiers.com
- Sé proactivo: si el cliente describe su necesidad, sugiere cuál servicio le conviene
- Mantén un tono cálido y profesional, como un asesor de ventas experimentado
"""


class PublicAssistantView(View):
    """Endpoint AJAX del asistente para visitantes del sitio público. Sin autenticación."""

    # Límite simple de mensajes por sesión para evitar abuso
    MAX_MESSAGES_PER_SESSION = 30

    def post(self, request):
        import json
        from apps.dashboard.views import _call_ai

        # Control de límite por sesión
        count = request.session.get("ai_msg_count", 0)
        if count >= self.MAX_MESSAGES_PER_SESSION:
            return JsonResponse({
                "response": "Has alcanzado el límite de mensajes de esta sesión. "
                            "Para continuar, escríbenos a ventas@solutioncopiers.com"
            })

        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "JSON inválido"}, status=400)

        user_message = (body.get("message") or "").strip()[:800]
        if not user_message:
            return JsonResponse({"error": "Mensaje vacío"}, status=400)

        history = body.get("history", [])
        response_text = _call_ai(_SYSTEM_PUBLIC, history, user_message)

        # Incrementa contador de sesión
        request.session["ai_msg_count"] = count + 1
        request.session.modified = True

        return JsonResponse({"response": response_text})
