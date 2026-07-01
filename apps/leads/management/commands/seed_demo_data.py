"""Comando para poblar la BD con datos demo realistas."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.blog.models import Category as BlogCategory
from apps.blog.models import Post, Tag
from apps.catalog.models import CablingService, Consumable, Copier, CopierCategory
from apps.core.models import SiteSettings, Testimonial
from apps.services.models import (
    CaseStudy, DatabaseService, MobileService,
    SoftwareService, Technology, WebService,
)


class Command(BaseCommand):
    help = "Pobla la base de datos con un catálogo demo completo."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Borra datos existentes.")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write(self.style.WARNING("[!] Borrando datos existentes..."))
            Post.objects.all().delete()
            Tag.objects.all().delete()
            BlogCategory.objects.all().delete()
            Copier.objects.all().delete()
            CopierCategory.objects.all().delete()
            Consumable.objects.all().delete()
            CablingService.objects.all().delete()
            SoftwareService.objects.all().delete()
            WebService.objects.all().delete()
            MobileService.objects.all().delete()
            DatabaseService.objects.all().delete()
            Technology.objects.all().delete()
            CaseStudy.objects.all().delete()
            Testimonial.objects.all().delete()

        self.stdout.write(self.style.NOTICE("[*] Poblando base de datos...\n"))

        self._create_site_settings()
        self._create_design_tokens()
        self._create_copier_categories()
        self._create_copiers()
        self._create_consumables()
        self._create_cabling_services()
        self._create_technologies()
        self._create_software_services()
        self._create_web_services()
        self._create_mobile_services()
        self._create_database_services()
        self._create_case_studies()
        self._create_testimonials()
        self._create_blog()

        self.stdout.write(self.style.SUCCESS("\n[OK] Seeding completado con exito!"))

    def _create_site_settings(self):
        obj = SiteSettings.load()
        obj.site_name = "Solution Copiers"
        obj.tagline = "Distribuidor Autorizado Ricoh en Medellín. Alquiler, venta y servicio técnico de fotocopiadoras para empresas en toda Colombia."
        obj.default_meta_description = (
            "Alquiler y venta de fotocopiadoras en Medellín. Distribuidor Autorizado Ricoh con "
            "mantenimiento incluido, tóner y soporte técnico. Sin inversión inicial."
        )
        obj.phone_primary = "(604) 322 22 76"
        obj.phone_whatsapp = "+573122520659"
        obj.email_contact = "comercial@solutioncopiers.com"
        obj.email_sales = "comercial@solutioncopiers.com"
        obj.address = "CL 53 N 79 145 P 1, Medellín, Antioquia"
        obj.city = "Medellín"
        obj.instagram_url = "https://www.instagram.com/solutioncopiers/"
        obj.facebook_url = "https://www.facebook.com/solutioncopiers2/"
        obj.save()
        self.stdout.write("  [OK] Configuracion del sitio")

    def _create_design_tokens(self):
        from apps.seo.models import DesignTokens
        DesignTokens.load()
        self.stdout.write("  [OK] Design Tokens")

    def _create_copier_categories(self):
        categories = [
            {"name": "Fotocopiadoras Blanco y Negro", "description": "Multifuncionales láser para impresión B/N de alto volumen.", "icon": "printer", "order": 1},
            {"name": "Fotocopiadoras a Color", "description": "Equipos profesionales para impresión color de alta calidad.", "icon": "palette", "order": 2},
            {"name": "Multifuncionales A3", "description": "Equipos formato grande tabloide para presentaciones y planos.", "icon": "file-image", "order": 3},
        ]
        for data in categories:
            CopierCategory.objects.update_or_create(
                name=data["name"],
                defaults={**data, "status": "published", "published_at": timezone.now()},
            )
        self.stdout.write(f"  [OK] {len(categories)} categorías de fotocopiadoras")

    def _create_copiers(self):
        cat_bw = CopierCategory.objects.get(name="Fotocopiadoras Blanco y Negro")
        cat_color = CopierCategory.objects.get(name="Fotocopiadoras a Color")
        cat_a3 = CopierCategory.objects.get(name="Multifuncionales A3")

        copiers_data = [
            # --- B/N ---
            {"name": "Ricoh MP 2554 — Multifuncional B/N", "model_number": "MP 2554", "category": cat_bw,
             "short_description": "Multifuncional laser B/N de 25 ppm. Ideal para grupos de trabajo de 10 a 25 personas.",
             "description": "<p>Transforme la productividad de su oficina con el Ricoh MP 2554. Imprime grandes cantidades de documentos de forma profesional con excelente calidad de impresion. Incluye escaneo, copia y red de fabrica.</p>",
             "toner_type": "bw", "paper_size": "both", "speed_ppm": 25, "monthly_duty_cycle": 75000,
             "pages_included_monthly": 2500, "extra_page_cost": Decimal("45"),
             "is_featured": True, "order": 1},
            {"name": "Ricoh MP 2555SP — Multifuncional B/N", "model_number": "MP 2555SP", "category": cat_bw,
             "short_description": "Multifuncional laser B/N de 25 ppm con ADF de alta capacidad y red gigabit.",
             "description": "<p>El MP 2555SP combina velocidad y versatilidad para oficinas con volumen documental medio-alto. Duplex automatico y alimentador de documentos incluidos.</p>",
             "toner_type": "bw", "paper_size": "both", "speed_ppm": 25, "monthly_duty_cycle": 85000,
             "pages_included_monthly": 3000, "extra_page_cost": Decimal("42"),
             "is_featured": True, "order": 2},
            {"name": "Ricoh MP 3055SP — Alto Volumen B/N", "model_number": "MP 3055SP", "category": cat_bw,
             "short_description": "Multifuncional laser B/N de 30 ppm para oficinas medianas y grandes.",
             "description": "<p>Mayor velocidad de impresion para equipos con alto trafico documental. Ciclo mensual de 100.000 paginas con gestion de papel flexible.</p>",
             "toner_type": "bw", "paper_size": "both", "speed_ppm": 30, "monthly_duty_cycle": 100000,
             "pages_included_monthly": 4000, "extra_page_cost": Decimal("40"),
             "is_featured": True, "order": 3},
            {"name": "Ricoh MP 3054 — B/N con finisher opcional", "model_number": "MP 3054", "category": cat_bw,
             "short_description": "Multifuncional laser B/N de 30 ppm compatible con finisher de grapado.",
             "description": "<p>Solucion completa para documentacion corporativa. Compatible con modulo finisher para grapado y perforacion automatica de documentos.</p>",
             "toner_type": "bw", "paper_size": "both", "speed_ppm": 30, "monthly_duty_cycle": 100000,
             "pages_included_monthly": 4000, "extra_page_cost": Decimal("40"),
             "order": 4},
            {"name": "Ricoh MP 4055SP — B/N Alta Produccion", "model_number": "MP 4055SP", "category": cat_bw,
             "short_description": "Multifuncional laser B/N de 40 ppm para entornos de alta produccion documental.",
             "description": "<p>Velocidad y fiabilidad para departamentos con volumenes superiores a 8.000 paginas mensuales. Panel intuitivo y conectividad avanzada.</p>",
             "toner_type": "bw", "paper_size": "both", "speed_ppm": 40, "monthly_duty_cycle": 150000,
             "pages_included_monthly": 6000, "extra_page_cost": Decimal("38"),
             "is_featured": True, "order": 5},
            {"name": "Ricoh MP 4002 — B/N Compacto de Alta Velocidad", "model_number": "MP 4002", "category": cat_bw,
             "short_description": "Compacto y rapido: 40 ppm en formato reducido para espacios ajustados.",
             "description": "<p>Diseno compacto sin sacrificar velocidad. Ideal para colegios y empresas que necesitan alto rendimiento en espacios reducidos.</p>",
             "toner_type": "bw", "paper_size": "both", "speed_ppm": 40, "monthly_duty_cycle": 120000,
             "pages_included_monthly": 5000, "extra_page_cost": Decimal("39"),
             "order": 6},
            {"name": "Ricoh Ricoh IM 430F — B/N Ultima Generacion", "model_number": "IM 430F", "category": cat_bw,
             "short_description": "Multifuncional inteligente B/N de 43 ppm con Smart Operation Panel.",
             "description": "<p>La serie IM representa la nueva generacion Ricoh: pantalla tactil de 9 pulgadas, conectividad en la nube e impresion movil integrada de fabrica.</p>",
             "toner_type": "bw", "paper_size": "both", "speed_ppm": 43, "monthly_duty_cycle": 150000,
             "has_wifi": True, "pages_included_monthly": 6000, "extra_page_cost": Decimal("37"),
             "is_featured": True, "order": 7},
            # --- COLOR ---
            {"name": "Ricoh MP C2004 — Color Compacto", "model_number": "MP C2004", "category": cat_color,
             "short_description": "Multifuncional color de 20 ppm. Solucion color accesible para oficinas que inician.",
             "description": "<p>El punto de entrada perfecto para empresas que quieren impresion color profesional sin una inversion inicial elevada. Incluye impresion, copia, escan y fax.</p>",
             "toner_type": "both", "paper_size": "a4", "speed_ppm": 20, "monthly_duty_cycle": 55000,
             "pages_included_monthly": 1500, "extra_page_cost": Decimal("165"),
             "is_featured": True, "order": 8},
            {"name": "Ricoh MP C3003 — Color 30 ppm", "model_number": "MP C3003", "category": cat_color,
             "short_description": "Multifuncional color de 30 ppm para oficinas medianas con necesidades de color frecuente.",
             "description": "<p>Equilibrio perfecto entre velocidad, calidad de color y costo por pagina. Panel tactil intuitivo y conectividad de red completa incluida.</p>",
             "toner_type": "both", "paper_size": "both", "speed_ppm": 30, "monthly_duty_cycle": 110000,
             "pages_included_monthly": 2500, "extra_page_cost": Decimal("155"),
             "is_featured": True, "order": 9},
            {"name": "Ricoh MP C3004 — Color con ADF", "model_number": "MP C3004", "category": cat_color,
             "short_description": "Multifuncional color de 30 ppm con alimentador automatico de 100 hojas.",
             "description": "<p>Version avanzada del C3003 con mayor capacidad de papel y ADF de alto rendimiento. Ideal para juridicos, contabilidades y departamentos con alto volumen de escaneo.</p>",
             "toner_type": "both", "paper_size": "both", "speed_ppm": 30, "monthly_duty_cycle": 110000,
             "pages_included_monthly": 2500, "extra_page_cost": Decimal("155"),
             "order": 10},
            {"name": "Ricoh IMC 2500 — Color Inteligente", "model_number": "IMC 2500", "category": cat_color,
             "short_description": "Nueva generacion color de 25 ppm con Smart Operation Panel y nube integrada.",
             "description": "<p>La serie IMC ofrece conectividad inteligente con Google Drive, Dropbox y OneDrive de fabrica. Impresion movil sin configuracion y pantalla tactil de 10.1 pulgadas.</p>",
             "toner_type": "both", "paper_size": "both", "speed_ppm": 25, "monthly_duty_cycle": 85000,
             "has_wifi": True, "pages_included_monthly": 2000, "extra_page_cost": Decimal("170"),
             "is_featured": True, "order": 11},
            # --- A3 #
            {"name": "Ricoh MP C4503 — A3 Color 45 ppm", "model_number": "MPC 4503", "category": cat_a3,
             "short_description": "Multifuncional A3 color de 45 ppm para produccion documental de alto volumen.",
             "description": "<p>Velocidad y calidad profesional para colegios, imprentas internas y empresas con produccion documental masiva. Formato A3/Tabloide con calidad de 1.200 dpi.</p>",
             "toner_type": "both", "paper_size": "both", "speed_ppm": 45, "monthly_duty_cycle": 200000,
             "pages_included_monthly": 6000, "extra_page_cost": Decimal("148"),
             "is_featured": True, "order": 12},
        ]

        for data in copiers_data:
            Copier.objects.update_or_create(
                model_number=data["model_number"],
                defaults={
                    **data, "status": "published", "published_at": timezone.now(),
                    "available_for_rental": True, "main_image_alt": data["name"],
                },
            )
        self.stdout.write(f"  [OK] {len(copiers_data)} fotocopiadoras Ricoh")

    def _create_consumables(self):
        consumables = [
            # Toneres B/N
            {"name": "Toner Ricoh MP 2554 / MP 2555SP — Negro Original", "consumable_type": "toner",
             "part_number": "841679", "yield_pages": 12000, "price": Decimal("98000"),
             "description": "Toner negro original Ricoh para serie MP 2554 / 2555SP / 3054 / 3055SP. Rendimiento de 12.000 paginas al 5% de cobertura."},
            {"name": "Toner Ricoh MP 3054 / MP 3055SP — Negro Original", "consumable_type": "toner",
             "part_number": "842042", "yield_pages": 14000, "price": Decimal("110000"),
             "description": "Toner negro original Ricoh para serie MP 3054 / 3055SP / 4054 / 4055SP."},
            {"name": "Toner Ricoh IM 430F — Negro Original", "consumable_type": "toner",
             "part_number": "842311", "yield_pages": 25000, "price": Decimal("145000"),
             "description": "Toner negro original de alta capacidad para Ricoh IM 430F / IM 550F. Hasta 25.000 paginas."},
            # Toneres Color
            {"name": "Toner Ricoh MP C2004 — Negro", "consumable_type": "toner",
             "part_number": "841727", "yield_pages": 10000, "price": Decimal("120000"),
             "description": "Toner negro original para Ricoh MP C2004 / C2504."},
            {"name": "Toner Ricoh MP C3003 / C3004 — Negro", "consumable_type": "toner",
             "part_number": "841651", "yield_pages": 23000, "price": Decimal("158000"),
             "description": "Toner negro original de alta capacidad para Ricoh MP C3003 / C3004 / C3503 / C3504."},
            {"name": "Toner Ricoh MP C3003 / C3004 — Cyan", "consumable_type": "toner",
             "part_number": "841652", "yield_pages": 18000, "price": Decimal("175000"),
             "description": "Toner cyan original para Ricoh MP C3003 / C3004 / C3503 / C3504."},
            {"name": "Toner Ricoh MP C3003 / C3004 — Magenta", "consumable_type": "toner",
             "part_number": "841653", "yield_pages": 18000, "price": Decimal("175000"),
             "description": "Toner magenta original para Ricoh MP C3003 / C3004 / C3503 / C3504."},
            {"name": "Toner Ricoh MP C3003 / C3004 — Amarillo", "consumable_type": "toner",
             "part_number": "841654", "yield_pages": 18000, "price": Decimal("175000"),
             "description": "Toner amarillo original para Ricoh MP C3003 / C3004 / C3503 / C3504."},
            {"name": "Toner Ricoh IMC 2500 — Negro", "consumable_type": "toner",
             "part_number": "842312", "yield_pages": 17000, "price": Decimal("148000"),
             "description": "Toner negro de alta capacidad para Ricoh IMC 2500 / IMC 3000 / IMC 3500."},
            {"name": "Toner Ricoh IMC 2500 — Cyan", "consumable_type": "toner",
             "part_number": "842313", "yield_pages": 11500, "price": Decimal("202000"),
             "description": "Toner cyan original para Ricoh IMC 2500 / IMC 3000 / IMC 3500."},
            # Cilindros / Drums
            {"name": "Cilindro (Drum) Ricoh MP 2554 / 3054", "consumable_type": "drum",
             "part_number": "D009-2310", "yield_pages": 90000, "price": Decimal("65000"),
             "description": "Unidad de tambor de imagen para Ricoh serie MP 2554 / 2555SP / 3054 / 3055SP."},
            {"name": "Cilindro (Drum) Ricoh MP C3003 / C3004", "consumable_type": "drum",
             "part_number": "D1442207", "yield_pages": 75000, "price": Decimal("96000"),
             "description": "Tambor de imagen color para Ricoh MP C3003 / C3004 / C3503 / C3504."},
            {"name": "Cilindro (Drum) Ricoh MP C2004", "consumable_type": "drum",
             "part_number": "D2412207", "yield_pages": 50000, "price": Decimal("33000"),
             "description": "Tambor de imagen para Ricoh MP C2004 / C2504."},
            # Fusores
            {"name": "Fusor Ricoh MP 3054 / 4055SP", "consumable_type": "fuser",
             "part_number": "D147-4000", "yield_pages": 120000, "price": Decimal("450000"),
             "description": "Unidad fusora para Ricoh MP 3054 / 3055SP / 4054 / 4055SP. Incluye kit de instalacion."},
        ]
        for data in consumables:
            Consumable.objects.update_or_create(
                part_number=data["part_number"],
                defaults={**data, "status": "published", "published_at": timezone.now()},
            )
        self.stdout.write(f"  [OK] {len(consumables)} consumibles")

    def _create_cabling_services(self):
        services = [
            {"name": "Puntos de Red Lógica Cat 6A", "icon": "network",
             "short_description": "Instalación profesional de puntos de red certificados.",
             "description": "<p>Instalación, etiquetado y certificación de puntos Cat 6A.</p>",
             "features": ["Cable certificado Cat 6A", "Conectores RJ45 categoría 6A", "Etiquetado profesional", "Garantía de 25 años"],
             "base_price": Decimal("180000"), "is_featured": True, "order": 1},
            {"name": "Puntos Eléctricos Regulados", "icon": "zap",
             "short_description": "Tomas reguladas dedicadas para equipos críticos.",
             "description": "<p>Circuitos eléctricos regulados para servidores y equipos de cómputo.</p>",
             "features": ["Cableado #12 AWG", "Tomas color naranja", "Tablero independiente", "Polo a tierra dedicado"],
             "base_price": Decimal("220000"), "order": 2},
            {"name": "Certificación de Red Cat 6A", "icon": "shield-check",
             "short_description": "Certificación profesional con Fluke DSX-5000.",
             "description": "<p>Certificación punto por punto con equipos Fluke calibrados.</p>",
             "features": ["Equipo Fluke DSX-5000", "Reporte PDF por punto", "Garantía documentada", "Cumplimiento TIA-568"],
             "requires_quote": True, "order": 3},
        ]
        for data in services:
            CablingService.objects.update_or_create(
                name=data["name"],
                defaults={**data, "status": "published", "published_at": timezone.now()},
            )
        self.stdout.write(f"  [OK] {len(services)} servicios de cableado")

    def _create_technologies(self):
        techs = [
            ("Python", "backend", 95), ("Django", "backend", 95), ("Node.js", "backend", 85),
            ("React", "frontend", 90), ("Vue.js", "frontend", 80), ("Tailwind CSS", "frontend", 90),
            ("Flutter", "mobile", 85), ("React Native", "mobile", 80), ("Swift", "mobile", 75),
            ("PostgreSQL", "database", 95), ("MySQL", "database", 90), ("MongoDB", "database", 80),
            ("AWS", "cloud", 85), ("Google Cloud", "cloud", 80),
            ("Docker", "devops", 90), ("GitHub Actions", "devops", 85),
        ]
        for i, (name, cat, level) in enumerate(techs):
            Technology.objects.update_or_create(
                name=name,
                defaults={"category": cat, "proficiency_level": level, "order": i},
            )
        self.stdout.write(f"  [OK] {len(techs)} tecnologías")

    def _create_software_services(self):
        services = [
            {"name": "Software a la Medida", "software_type": "custom",
             "tagline": "Soluciones únicas para necesidades únicas.",
             "short_description": "Desarrollamos sistemas a la medida exacta de tu operación.",
             "description": "<p>Analizamos tus procesos y construimos software diseñado específicamente para tu negocio.</p>",
             "benefits": ["Adaptado 100% a tu operación", "Sin licencias por usuario", "Código propio", "Soporte continuo"],
             "deliverables": ["Análisis funcional", "Diseño de arquitectura", "Desarrollo iterativo", "Documentación", "3 meses de garantía"],
             "estimated_duration": "8-16 semanas", "starting_price": Decimal("25000000"),
             "is_featured": True, "order": 1},
            {"name": "ERP para PyMEs", "software_type": "erp",
             "tagline": "Centraliza tu operación en una sola plataforma.",
             "short_description": "ERP modular: ventas, inventario, finanzas y RRHH en un solo lugar.",
             "description": "<p>Sistema ERP modular adaptable al tamaño de tu empresa.</p>",
             "benefits": ["Módulos según tu necesidad", "Escalable", "Reportes en tiempo real", "Integración DIAN"],
             "estimated_duration": "12-20 semanas", "starting_price": Decimal("45000000"),
             "is_featured": True, "order": 2},
        ]
        python = Technology.objects.get(name="Python")
        django_tech = Technology.objects.get(name="Django")
        postgres = Technology.objects.get(name="PostgreSQL")

        for data in services:
            obj, _ = SoftwareService.objects.update_or_create(
                name=data["name"],
                defaults={**data, "status": "published", "published_at": timezone.now()},
            )
            obj.technologies.set([python, django_tech, postgres])
        self.stdout.write(f"  [OK] {len(services)} servicios de software")

    def _create_web_services(self):
        services = [
            {"name": "Sitios Web Corporativos", "web_type": "corporate",
             "tagline": "Tu marca con la presencia que merece.",
             "short_description": "Sitios corporativos rápidos, seguros y optimizados para SEO.",
             "description": "<p>Diseñamos y desarrollamos sitios corporativos modernos.</p>",
             "benefits": ["Diseño UI/UX a la medida", "SEO técnico avanzado", "Performance 90+", "CMS amigable"],
             "estimated_duration": "4-8 semanas", "starting_price": Decimal("8000000"),
             "is_featured": True, "order": 1},
            {"name": "Tiendas E-commerce", "web_type": "ecommerce",
             "tagline": "Vende en línea desde el día uno.",
             "short_description": "E-commerce robusto integrado con pasarelas locales.",
             "description": "<p>Plataformas e-commerce listas para escalar con Wompi, ePayco, MercadoPago.</p>",
             "benefits": ["Pasarelas Colombia", "Carrito persistente", "Panel intuitivo", "Mobile optimizado"],
             "estimated_duration": "6-12 semanas", "starting_price": Decimal("15000000"),
             "is_featured": True, "order": 2},
        ]
        for data in services:
            WebService.objects.update_or_create(
                name=data["name"],
                defaults={**data, "status": "published", "published_at": timezone.now()},
            )
        self.stdout.write(f"  [OK] {len(services)} servicios web")

    def _create_mobile_services(self):
        services = [
            {"name": "Apps Híbridas Flutter", "mobile_type": "hybrid",
             "tagline": "Una app, dos sistemas operativos.",
             "short_description": "Apps móviles iOS y Android con un solo código base.",
             "description": "<p>Desarrollo eficiente con Flutter: tiempos reducidos y mantenimiento simple.</p>",
             "benefits": ["iOS + Android en paralelo", "Performance casi nativa", "Menor costo", "Hot reload"],
             "estimated_duration": "10-16 semanas", "starting_price": Decimal("30000000"),
             "is_featured": True, "order": 1},
        ]
        for data in services:
            MobileService.objects.update_or_create(
                name=data["name"],
                defaults={**data, "status": "published", "published_at": timezone.now()},
            )
        self.stdout.write(f"  [OK] {len(services)} servicios móviles")

    def _create_database_services(self):
        services = [
            {"name": "Migración de Bases de Datos a Cloud", "database_type": "migration",
             "tagline": "De on-premise a AWS, GCP o Azure.",
             "short_description": "Migración segura y sin pérdida de datos a infraestructura cloud.",
             "description": "<p>Planificamos y ejecutamos migraciones con cero downtime.</p>",
             "benefits": ["Cero pérdida de datos", "Plan de rollback", "Migración por etapas", "Capacitación"],
             "engines_supported": ["PostgreSQL", "MySQL", "Oracle", "SQL Server"],
             "estimated_duration": "4-8 semanas", "starting_price": Decimal("12000000"),
             "is_featured": True, "order": 1},
        ]
        for data in services:
            DatabaseService.objects.update_or_create(
                name=data["name"],
                defaults={**data, "status": "published", "published_at": timezone.now()},
            )
        self.stdout.write(f"  [OK] {len(services)} servicios de bases de datos")

    def _create_case_studies(self):
        cases = [
            {"title": "Bufete Jurídico optimiza impresión y reduce costos 40%",
             "client_name": "Bufete Asociados SAS", "client_industry": "Servicios Legales",
             "challenge": "Costos de impresión descontrolados y equipos obsoletos en 3 oficinas.",
             "solution": "Plan integral de alquiler con 6 equipos Ricoh + software de control.",
             "results": "Reducción del 40% en costos mensuales y visibilidad total del consumo.",
             "results_metrics": [
                 {"label": "Reducción de costos", "value": "40%"},
                 {"label": "Equipos consolidados", "value": "6"},
                 {"label": "Oficinas integradas", "value": "3"},
             ],
             "is_featured": True, "order": 1},
            {"title": "Constructora digitaliza gestión con ERP a medida",
             "client_name": "Construcciones del Valle", "client_industry": "Construcción",
             "challenge": "Procesos manuales en Excel para gestión de obras y materiales.",
             "solution": "ERP a medida con módulos de obras, inventario y nómina con DIAN.",
             "results": "Automatización del 80% de procesos administrativos.",
             "results_metrics": [
                 {"label": "Procesos automatizados", "value": "80%"},
                 {"label": "Tiempo ahorrado", "value": "120h/mes"},
             ],
             "is_featured": True, "order": 2},
        ]
        for data in cases:
            CaseStudy.objects.update_or_create(
                title=data["title"],
                defaults={**data, "status": "published", "published_at": timezone.now()},
            )
        self.stdout.write(f"  [OK] {len(cases)} casos de éxito")

    def _create_testimonials(self):
        testimonials = [
            {"author_name": "Carolina Restrepo", "author_role": "Gerente Administrativa",
             "author_company": "Constructora Andes S.A.S.",
             "quote": "Llevamos 3 anos con Solution Copiers y nunca hemos parado por falta de servicio. Llaman antes de que el toner se acabe y el mantenimiento preventivo es impecable.",
             "rating": 5, "is_featured": True, "order": 1},
            {"author_name": "Carlos Henao", "author_role": "Rector",
             "author_company": "Institucion Educativa Los Alpes",
             "quote": "Para un colegio el volumen de impresion es enorme. Con Solution Copiers cambiamos 6 impresoras viejas por 2 Ricoh en alquiler y ahorramos mas del 30% mensual.",
             "rating": 5, "is_featured": True, "order": 2},
            {"author_name": "Lucia Montoya", "author_role": "Directora Administrativa",
             "author_company": "Distribuciones Textiles S.A.S.",
             "quote": "Empezamos con 2 equipos y ya vamos por 6. El servicio tecnico siempre responde el mismo dia. Nunca mas equipos propios: con esto nos quitamos un dolor de cabeza enorme.",
             "rating": 5, "is_featured": True, "order": 3},
            {"author_name": "Felipe Osorio", "author_role": "Gerente General",
             "author_company": "Juridica Osorio y Asociados",
             "quote": "En un bufete la impresion es critica. Con Solution Copiers tenemos garantizado que el equipo funciona. Si falla, estan en menos de 24 horas. Responsabilidad total.",
             "rating": 5, "is_featured": True, "order": 4},
            {"author_name": "Marcela Giraldo", "author_role": "Coordinadora de Compras",
             "author_company": "Industrias Metalicas del Abura",
             "quote": "El toner nos llega antes de que se acabe. El mantenimiento preventivo es puntual. Y cuando hay un problema lo resuelven sin excusas. Eso es lo que uno busca.",
             "rating": 5, "is_featured": True, "order": 5},
            {"author_name": "Andres Gomez", "author_role": "Director de Operaciones",
             "author_company": "Clinica Dental Sonrisas",
             "quote": "Pasamos de gastar una fortuna en toner e impresoras de escritorio a pagar una cuota fija mensual. El ahorro fue inmediato y el servicio mucho mejor.",
             "rating": 5, "is_featured": True, "order": 6},
        ]
        for data in testimonials:
            Testimonial.objects.update_or_create(
                author_name=data["author_name"],
                author_company=data["author_company"],
                defaults={**data, "status": "published", "published_at": timezone.now()},
            )
        self.stdout.write(f"  [OK] {len(testimonials)} testimoniales")

    def _create_blog(self):
        User = get_user_model()
        author = User.objects.filter(is_superuser=True).first()

        categories = [
            {"name": "Fotocopiadoras y Equipos", "silo": "hardware",
             "description": "Guias practicas sobre alquiler, venta, mantenimiento y consumibles de fotocopiadoras para empresas en Colombia."},
            {"name": "Infraestructura Empresarial", "silo": "hardware",
             "description": "Cableado estructurado, redes y todo lo que necesita la infraestructura tecnologica de tu oficina."},
            {"name": "Soluciones Digitales", "silo": "software",
             "description": "Software a la medida, diseno web y aplicaciones moviles para empresas colombianas."},
        ]
        cat_objs = {}
        for data in categories:
            obj, _ = BlogCategory.objects.update_or_create(
                name=data["name"],
                defaults={**data},
            )
            cat_objs[data["name"]] = obj

        tags_map = {}
        for tag_name in ["Ricoh", "Fotocopiadoras", "Alquiler", "Mantenimiento",
                         "Cableado estructurado", "Software a la medida", "Medellin", "Pymes"]:
            tag_obj, _ = Tag.objects.get_or_create(name=tag_name)
            tags_map[tag_name] = tag_obj

        cat_foto = cat_objs["Fotocopiadoras y Equipos"]
        cat_infra = cat_objs["Infraestructura Empresarial"]
        cat_soft = cat_objs["Soluciones Digitales"]

        posts = [
            {
                "title": "Cuanto cuesta alquilar una fotocopiadora en Medellin en 2025",
                "excerpt": (
                    "Comparamos los planes de alquiler disponibles en Medellin, "
                    "los costos reales por pagina y que modelo Ricoh se adapta al "
                    "volumen de impresion de tu empresa."
                ),
                "content": """<p>Si estas evaluando si alquilar o comprar una fotocopiadora para tu empresa en Medellin, la respuesta corta es: <strong>alquilar casi siempre sale mas rentable</strong>. Aqui te explicamos por que y cuanto cuesta realmente.</p>

<h2>Que incluye el modelo de alquiler</h2>
<p>Un plan de alquiler con Solution Copiers incluye el equipo, instalacion, mantenimiento preventivo, correctivo, repuestos y toner. Pagas una cuota mensual fija y te olvidas de los imprevistos. Sin inversion inicial, sin sorpresas.</p>

<h2>Rangos de precio segun volumen (2025)</h2>
<ul>
  <li><strong>Hasta 2.500 paginas/mes:</strong> desde $280.000 COP/mes — oficinas pequenas de 5 a 15 personas.</li>
  <li><strong>2.500 a 5.000 paginas/mes:</strong> desde $380.000 COP/mes — empresas medianas con impresion frecuente.</li>
  <li><strong>5.000 a 10.000 paginas/mes:</strong> desde $550.000 COP/mes — oficinas con alto volumen documental.</li>
  <li><strong>Color hasta 3.000 paginas/mes:</strong> desde $600.000 COP/mes — color profesional para colegios y agencias.</li>
</ul>

<h2>Por que alquilar en lugar de comprar</h2>
<p>Comprar un equipo Ricoh nuevo representa una inversion inicial de entre $8 y $25 millones de pesos, mas los costos de mantenimiento, repuestos y toner que corren por tu cuenta. Con el alquiler, ese capital queda libre para tu operacion y el servicio tecnico esta garantizado.</p>

<h2>Como saber que modelo necesitas</h2>
<p>El factor clave es el <strong>volumen mensual de paginas</strong>. Si imprimes menos de 3.000 paginas al mes, un equipo B/N como el Ricoh MP 2554 o MP 2555SP es suficiente. Si superas las 5.000 o necesitas color, el Ricoh MP C3003 o el IMC 2500 son los mas solicitados.</p>

<p>Solicita tu cotizacion personalizada en nuestro <a href="/cotizador/">cotizador en linea</a> y recibe una propuesta en menos de 24 horas.</p>""",
                "category": cat_foto,
                "tags": [tags_map["Ricoh"], tags_map["Fotocopiadoras"], tags_map["Alquiler"], tags_map["Medellin"]],
                "reading_time_min": 4,
                "is_featured": True,
                "main_image_alt": "Fotocopiadora Ricoh multifuncional en oficina de Medellin",
            },
            {
                "title": "Mantenimiento preventivo vs correctivo en fotocopiadoras: que diferencia hay",
                "excerpt": (
                    "Muchas empresas solo llaman al tecnico cuando la maquina falla. "
                    "Te explicamos por que el mantenimiento preventivo ahorra mas dinero "
                    "y como funciona el servicio de Solution Copiers."
                ),
                "content": """<p>La pregunta que mas nos hacen los gerentes administrativos: <em>si el equipo funciona bien, para que llamar al tecnico?</em> La respuesta tiene que ver con costos y continuidad operativa.</p>

<h2>Mantenimiento preventivo: antes de que falle</h2>
<p>El mantenimiento preventivo es una visita programada donde el tecnico limpia, calibra y revisa todos los componentes del equipo antes de que generen una falla. Se cambian piezas con desgaste visible antes de que rompan.</p>
<p><strong>Beneficios reales:</strong></p>
<ul>
  <li>Reduce en un 70% las paradas imprevistas del equipo.</li>
  <li>Extiende la vida util de rodillos, fusores y tambores.</li>
  <li>Mantiene la calidad de impresion en niveles optimos.</li>
  <li>Evita que un fallo menor se convierta en una reparacion costosa.</li>
</ul>

<h2>Mantenimiento correctivo: cuando ya fallo</h2>
<p>El mantenimiento correctivo es la intervencion de emergencia cuando el equipo presenta una averia: atascos repetidos, manchas en impresion, error en pantalla o fallo total. El objetivo es restaurar el funcionamiento lo antes posible.</p>
<p>En Solution Copiers garantizamos atencion en menos de <strong>24 horas en Medellin</strong> para correctivos. El diagnostico en sitio es sin costo adicional.</p>

<h2>Cual conviene mas para tu empresa</h2>
<p>Ambos son necesarios. La diferencia esta en que el preventivo lo controlas tu (es programado) y el correctivo lo genera el equipo (es imprevisto). Un buen contrato de alquiler con Solution Copiers incluye ambos sin costo adicional.</p>

<h2>Lo que cubre nuestro plan de alquiler</h2>
<ul>
  <li>Mantenimiento preventivo programado</li>
  <li>Mantenimiento correctivo ilimitado</li>
  <li>Repuestos originales o genericos de excelente calidad</li>
  <li>Toner segun el plan contratado</li>
  <li>Soporte telefonico y visita tecnica incluida</li>
</ul>

<p>Si tienes equipos propios y buscas un contrato de mantenimiento independiente, tambien lo hacemos. <a href="/contacto/">Contactanos</a> y cotizamos.</p>""",
                "category": cat_foto,
                "tags": [tags_map["Ricoh"], tags_map["Mantenimiento"], tags_map["Fotocopiadoras"]],
                "reading_time_min": 5,
                "is_featured": True,
                "main_image_alt": "Tecnico de Solution Copiers haciendo mantenimiento preventivo a fotocopiadora Ricoh",
            },
            {
                "title": "Ricoh MP 3055 vs Ricoh IM 430: que modelo Ricoh elegir para tu empresa",
                "excerpt": (
                    "Comparamos dos de los modelos B/N mas vendidos en Medellin: "
                    "el clasico MP 3055SP y el nuevo IM 430F. Cual conviene segun tu volumen."
                ),
                "content": """<p>En Solution Copiers rentamos ambos modelos con frecuencia y la pregunta que nos hacen constantemente es: <em>cual me conviene?</em> La respuesta depende del volumen, el presupuesto y si valoras las funciones inteligentes.</p>

<h2>Ricoh MP 3055SP — el referente de la gama media</h2>
<p>El MP 3055SP es uno de los modelos mas solicitados para empresas de 20 a 60 personas. Imprime a 30 ppm, tiene duplex automatico, ADF de 100 hojas y soporte de papel A4 y A3. Ciclo mensual recomendado: hasta 100.000 paginas.</p>
<p><strong>Para quien es ideal:</strong> colegios, juridicos, empresas de servicios, contabilidades.</p>

<h2>Ricoh IM 430F — la nueva generacion</h2>
<p>El IM 430F es 43 ppm, mas rapido que el MP 3055SP, con pantalla tactil de 9 pulgadas, impresion movil (AirPrint, Mopria), conexion WiFi de fabrica e integracion directa con Google Drive, OneDrive y Dropbox.</p>
<p><strong>Para quien es ideal:</strong> empresas con trabajo hibrido, equipos que imprimen desde movil, oficinas que quieren reducir pasos en flujos documentales.</p>

<h2>Comparativa rapida</h2>
<ul>
  <li><strong>Velocidad:</strong> IM 430F gana (43 vs 30 ppm)</li>
  <li><strong>Conectividad:</strong> IM 430F gana (WiFi, nube de fabrica)</li>
  <li><strong>Costo mensual:</strong> MP 3055SP es generalmente mas economico</li>
  <li><strong>Formato de papel:</strong> ambos soportan A4 y A3</li>
  <li><strong>Fiabilidad:</strong> ambos son equipos Ricoh con garantia igual</li>
</ul>

<h2>Nuestra recomendacion</h2>
<p>Si el presupuesto es la prioridad y el volumen no supera las 5.000 paginas al mes, el MP 3055SP es suficiente. Si la empresa tiene trabajo hibrido o quiere simplificar flujos de documentos, el IM 430F vale la diferencia de precio.</p>

<p>¿Quieres ver ambos modelos y cotizar? <a href="/alquiler-fotocopiadoras-medellin/">Ver catalogo completo</a>.</p>""",
                "category": cat_foto,
                "tags": [tags_map["Ricoh"], tags_map["Fotocopiadoras"], tags_map["Alquiler"]],
                "reading_time_min": 5,
                "is_featured": True,
                "main_image_alt": "Comparativa entre Ricoh MP 3055SP y Ricoh IM 430F en oficina",
            },
            {
                "title": "Por que una fotocopiadora multifuncional es mejor que 5 impresoras de escritorio",
                "excerpt": (
                    "La mayoria de las empresas en Medellin aun tienen varias impresoras "
                    "de escritorio individuales. Te mostramos por que ese modelo sale mas caro "
                    "y mas problematico que un solo equipo multifuncional."
                ),
                "content": """<p>Es un error comun: la empresa crece, se compran impresoras de escritorio para cada area y de pronto hay 6 impresoras, 4 marcas distintas, toners diferentes y un problema diferente cada semana. Aqui esta el calculo real.</p>

<h2>El costo real de las impresoras de escritorio</h2>
<p>Una impresora de escritorio basica imprime a 20-25 ppm, consume un toner de $80.000-$120.000 cada 1.500-2.000 paginas y falla con frecuencia. Con 5 impresoras imprimiendo 500 paginas cada una al mes:</p>
<ul>
  <li>Toner mensual: entre $200.000 y $400.000 COP (para las 5)</li>
  <li>Mantenimiento: no incluido, cada reparacion es un imprevisto</li>
  <li>Velocidad: 20-25 ppm por equipo, colas de impresion por persona</li>
  <li>Espacio: 5 equipos sobre 5 escritorios</li>
</ul>

<h2>Un equipo multifuncional Ricoh centralizado</h2>
<p>Con un Ricoh MP 2554 o MP 2555SP imprimiendo 2.500 paginas al mes para todo el equipo:</p>
<ul>
  <li>Toner mensual: incluido en el plan de alquiler</li>
  <li>Mantenimiento: incluido, sin imprevistos</li>
  <li>Velocidad: 25-30 ppm, red compartida, impresion desde cualquier PC o movil</li>
  <li>Escaneo, copia y fax incluidos sin costo adicional</li>
</ul>

<h2>El ahorro es inmediato</h2>
<p>La mayoria de nuestros clientes que hacen esta migracion ahorran entre el 30% y el 50% en costos de impresion mensual. Y eliminan completamente los imprevistos: el equipo falla, llamamos, en menos de 24 horas esta resuelto.</p>

<p>Si todavia tienes impresoras de escritorio, este es un buen momento para hacer el cambio. <a href="/cotizador/">Cotiza aqui</a>.</p>""",
                "category": cat_foto,
                "tags": [tags_map["Ricoh"], tags_map["Fotocopiadoras"], tags_map["Pymes"]],
                "reading_time_min": 4,
                "is_featured": False,
                "main_image_alt": "Ricoh MP 2554 multifuncional frente a grupo de impresoras de escritorio",
            },
            {
                "title": "Cableado estructurado Cat 6A: por que es la mejor inversion para tu oficina en 2025",
                "excerpt": (
                    "El cableado estructurado es la infraestructura invisible que hace funcionar "
                    "todo lo demas. Te explicamos por que Cat 6A es el estandar correcto hoy "
                    "y cuanto cuesta en Medellin."
                ),
                "content": """<p>Si estas montando una oficina nueva o renovando la red existente, la decision del cableado es una de las mas importantes. Y es la que mas se subestima. Un cableado mal instalado genera problemas durante anos.</p>

<h2>Por que Cat 6A y no Cat 6</h2>
<p>Cat 6 soporta 1 Gbps a 100 metros. Cat 6A soporta 10 Gbps a 100 metros con mayor resistencia a interferencias. En 2025, la diferencia de costo entre instalar Cat 6 y Cat 6A es de entre $800.000 y $1.500.000 en un proyecto de 50 puntos. Un delta pequeno considerando que el cableado dura 15-20 anos.</p>

<h2>Que incluye una instalacion correcta</h2>
<ul>
  <li>Cable certificado Cat 6A por punto</li>
  <li>Conectores RJ45 categoria 6A</li>
  <li>Patch panel y rack de comunicaciones</li>
  <li>Certificacion punto por punto con equipo Fluke DSX-5000</li>
  <li>Informe tecnico con resultados de certificacion</li>
  <li>Etiquetado profesional de todos los puntos</li>
</ul>

<h2>Cuanto cuesta en Medellin</h2>
<p>Un punto de red Cat 6A certificado en Medellin cuesta entre $180.000 y $250.000 COP dependiendo del acceso y la distancia. Un proyecto tipico de oficina de 20 personas con 30 puntos de red queda entre $5.400.000 y $7.500.000 COP instalado y certificado.</p>

<h2>Para quien es el cableado estructurado</h2>
<p>Para cualquier empresa que dependa de la red para trabajar: desde una oficina de 10 personas hasta una empresa con 200 puestos. Si usas VoIP, camaras IP, impresoras en red o servidores locales, el cableado estructurado certificado es obligatorio.</p>

<p>¿Quieres saber cuantos puntos necesita tu espacio? <a href="/contacto/">Agendamos una visita tecnica sin costo</a>.</p>""",
                "category": cat_infra,
                "tags": [tags_map["Cableado estructurado"], tags_map["Pymes"], tags_map["Medellin"]],
                "reading_time_min": 5,
                "is_featured": True,
                "main_image_alt": "Tecnico instalando cableado estructurado Cat 6A en rack de comunicaciones en Medellin",
            },
        ]

        created = 0
        for data in posts:
            tags = data.pop("tags")
            obj, created_now = Post.objects.update_or_create(
                title=data["title"],
                defaults={
                    **data,
                    "author": author,
                    "status": "published",
                    "published_at": timezone.now(),
                },
            )
            obj.tags.set(tags)
            if created_now:
                created += 1

        self.stdout.write(f"  [OK] {len(posts)} posts del blog ({len(categories)} categorías)")
