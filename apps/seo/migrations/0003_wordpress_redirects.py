"""
Migración de datos: crea las reglas 301 para URLs del sitio WordPress anterior
que no coinciden con la estructura de URLs del nuevo sitio Django.

Fuente: análisis de solutioncopiers.com (WordPress + WooCommerce + Elementor)
Destino: URLs del nuevo sitio Django
"""
from django.db import migrations


REDIRECTS = [
    # Páginas institucionales
    ("/nuestra-empresa/",                    "/sobre-nosotros/"),
    ("/contactanos/",                         "/contacto/"),
    ("/servicios-de-fotocopiadoras/",         "/soluciones-empresariales/"),

    # Catálogo principal
    ("/alquiler-de-fotocopiadoras/",          "/alquiler-fotocopiadoras-medellin/"),
    ("/venta-de-fotocopiadoras/",             "/venta-fotocopiadoras-medellin/"),
    ("/mantenimiento-de-fotocopiadoras/",     "/servicio-tecnico-fotocopiadoras/"),
    ("/consumibles/",                         "/consumibles-toner-ricoh/"),
    ("/toner/",                               "/consumibles-toner-ricoh/"),
    ("/insumos/",                             "/consumibles-toner-ricoh/"),

    # WooCommerce shop → catálogo principal
    ("/tienda/",                              "/alquiler-fotocopiadoras-medellin/"),
    ("/shop/",                                "/alquiler-fotocopiadoras-medellin/"),
    ("/productos/",                           "/alquiler-fotocopiadoras-medellin/"),

    # Servicios tecnológicos (si existían en WordPress)
    ("/servicios/",                           "/soluciones-empresariales/"),
    ("/soporte-tecnico/",                     "/servicio-tecnico-fotocopiadoras/"),
    ("/soporte/",                             "/servicio-tecnico-fotocopiadoras/"),

    # Formulario de contacto / cotización
    ("/cotizar/",                             "/cotizador/"),
    ("/solicitar-cotizacion/",                "/cotizador/"),
    ("/solicitud/",                           "/cotizador/"),

    # Política / términos
    ("/politica-privacidad/",                 "/politica-de-privacidad/"),
    ("/privacidad/",                          "/politica-de-privacidad/"),
    ("/terminos/",                            "/terminos-y-condiciones/"),
    ("/terminos-condiciones/",                "/terminos-y-condiciones/"),

    # Blog
    ("/noticias/",                            "/blog/"),
    ("/articulos/",                           "/blog/"),
]


def crear_redirects(apps, schema_editor):
    RedirectRule = apps.get_model("seo", "RedirectRule")
    for old_path, new_path in REDIRECTS:
        RedirectRule.objects.get_or_create(
            old_path=old_path,
            defaults={"new_path": new_path, "redirect_type": 301, "is_active": True},
        )


def eliminar_redirects(apps, schema_editor):
    RedirectRule = apps.get_model("seo", "RedirectRule")
    old_paths = [r[0] for r in REDIRECTS]
    RedirectRule.objects.filter(old_path__in=old_paths).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("seo", "0002_alter_designtokens_color_accent_and_more"),
    ]

    operations = [
        migrations.RunPython(crear_redirects, eliminar_redirects),
    ]
