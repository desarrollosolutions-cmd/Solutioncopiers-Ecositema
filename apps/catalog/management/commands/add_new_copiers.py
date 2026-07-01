"""
Agrega dos nuevos equipos al catálogo:
  1. Ricoh MP 301SP  — foto local  (ricoh 301.png)
  2. Ricoh IM C2000  — foto desde internet (Ricoh USA CDN)

Uso:
    python manage.py add_new_copiers
    python manage.py add_new_copiers --dry-run
"""
import os
import tempfile
import urllib.request

from django.core.files import File
from django.core.management.base import BaseCommand

from apps.catalog.models import Copier, CopierCategory

LOCAL_PHOTO_301  = r'C:\Users\User\Desktop\fotos para pagina\Fotocopiadoras\ricoh 301.png'
IMC2000_IMAGE_URL = (
    'http://images.salsify.com/images/g4tqtmy0dlaoprotrgld/'
    'ricohimages_Equipment_Printers-and-Copiers_eqp-im-c2000-10.png'
)

COPIERS_DATA = [
    {
        'brand':               'Ricoh',
        'model_number':        'MP 301SP',
        'name':                'Ricoh MP 301SP - Compacta B/N para Oficina',
        'category_slug':       'fotocopiadoras-blanco-y-negro',
        'short_description':   (
            'Impresora multifuncional compacta B/N ideal para oficinas pequeñas, '
            'home office y puntos de impresión de bajo volumen.'
        ),
        'description':         (
            'La Ricoh MP 301SP es una solución de impresión compacta y económica '
            'diseñada para entornos de trabajo con volúmenes moderados. '
            'Con 30 ppm en B/N y resolución de hasta 1200×1200 dpi, garantiza '
            'documentos nítidos y profesionales. Su diseño de escritorio y fácil '
            'configuración la hacen perfecta para pequeñas oficinas, colegios y '
            'puntos de atención al público. Incluye copiadora, impresora y escáner '
            'en un solo equipo de bajo consumo energético.\n\n'
            'Características destacadas:\n'
            '• Velocidad de 30 ppm en B/N\n'
            '• Resolución de impresión hasta 1200×1200 dpi\n'
            '• Capacidad de papel: 250 hojas bandeja + 50 bypass\n'
            '• Conectividad USB y red Ethernet\n'
            '• Ciclo mensual recomendado: hasta 15.000 páginas\n'
            '• Bajo consumo: solo 1,4 W en modo ahorro\n'
            '• Ideal para A4/Carta'
        ),
        'toner_type':          'bw',
        'paper_size':          'a4',
        'speed_ppm':           30,
        'monthly_duty_cycle':  15000,
        'has_scanner':         True,
        'has_duplex':          False,
        'has_network':         True,
        'has_wifi':            False,
        'available_for_rental': True,
        'available_for_sale':   True,
        'is_featured':         False,
        'photo_source':        'local',
        'photo_path':          LOCAL_PHOTO_301,
        'photo_filename':      'ricoh-mp-301sp.png',
        'main_image_alt':      'Ricoh MP 301SP - Multifuncional compacta B/N',
    },
    {
        'brand':               'Ricoh',
        'model_number':        'IM C2000',
        'name':                'Ricoh IM C2000 - Multifuncional Color Inteligente',
        'category_slug':       'fotocopiadoras-a-color',
        'short_description':   (
            'Multifuncional color de última generación con panel táctil 10", '
            'IA integrada y conectividad avanzada para equipos modernos.'
        ),
        'description':         (
            'La Ricoh IM C2000 es la evolución inteligente de las impresoras '
            'multifuncionales color. Combina velocidad, calidad de imagen '
            'excepcional y un panel táctil de 10 pulgadas con tecnología Smart '
            'Operation Panel para simplificar los flujos de trabajo diarios.\n\n'
            'Perfecta para empresas medianas que necesitan impresión color '
            'profesional con integración a la nube, escaneado inteligente y '
            'seguridad avanzada de documentos. Compatible con los principales '
            'servicios cloud: Google Drive, Dropbox, OneDrive y más.\n\n'
            'Especificaciones principales:\n'
            '• Velocidad: 20 ppm color y B/N\n'
            '• Resolución: hasta 1200×1200 dpi\n'
            '• Panel táctil capacitivo de 10.1"\n'
            '• Copia, impresión, escaneo y fax opcional\n'
            '• Dúplex automático incluido\n'
            '• WiFi y Ethernet Gigabit\n'
            '• Capacidad de papel: hasta 2.300 hojas con bandejas adicionales\n'
            '• Ciclo mensual: hasta 100.000 páginas\n'
            '• NFC para impresión móvil directa'
        ),
        'toner_type':          'color',
        'paper_size':          'both',
        'speed_ppm':           20,
        'monthly_duty_cycle':  100000,
        'has_scanner':         True,
        'has_duplex':          True,
        'has_network':         True,
        'has_wifi':            True,
        'available_for_rental': True,
        'available_for_sale':   True,
        'is_featured':         True,
        'photo_source':        'url',
        'photo_url':           IMC2000_IMAGE_URL,
        'photo_filename':      'ricoh-im-c2000.png',
        'main_image_alt':      'Ricoh IM C2000 - Multifuncional Color Inteligente',
    },
]


class Command(BaseCommand):
    help = 'Agrega Ricoh MP 301SP e IM C2000 al catálogo con sus fotos'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        self.stdout.write('\n=== Agregando nuevos equipos ===\n')
        if dry_run:
            self.stdout.write('MODO DRY-RUN\n')

        for data in COPIERS_DATA:
            model_number = data['model_number']

            # Verificar si ya existe
            if Copier.objects.filter(brand=data['brand'], model_number=model_number).exists():
                self.stdout.write(f'  [YA EXISTE] {data["brand"]} {model_number} — omitido')
                continue

            # Obtener categoría
            try:
                category = CopierCategory.objects.get(slug=data['category_slug'])
            except CopierCategory.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'  [ERROR] Categoría "{data["category_slug"]}" no encontrada'))
                continue

            self.stdout.write(f'\n  Creando: {data["brand"]} {model_number}')
            self.stdout.write(f'    Categoria : {category.name}')
            self.stdout.write(f'    Foto      : {data["photo_filename"]} ({data["photo_source"]})')

            if dry_run:
                continue

            # Crear el copier
            copier = Copier(
                brand               = data['brand'],
                model_number        = model_number,
                name                = data['name'],
                category            = category,
                short_description   = data['short_description'],
                description         = data['description'],
                toner_type          = data['toner_type'],
                paper_size          = data['paper_size'],
                speed_ppm           = data['speed_ppm'],
                monthly_duty_cycle  = data['monthly_duty_cycle'],
                has_scanner         = data['has_scanner'],
                has_duplex          = data['has_duplex'],
                has_network         = data['has_network'],
                has_wifi            = data['has_wifi'],
                available_for_rental = data['available_for_rental'],
                available_for_sale   = data['available_for_sale'],
                is_featured          = data.get('is_featured', False),
                status               = 'published',
            )

            # Asignar imagen
            try:
                if data['photo_source'] == 'local':
                    with open(data['photo_path'], 'rb') as f:
                        copier.save()
                        copier.main_image.save(data['photo_filename'], File(f), save=False)
                        copier.main_image_alt = data['main_image_alt']
                        copier.save(update_fields=['main_image', 'main_image_alt'])

                elif data['photo_source'] == 'url':
                    self.stdout.write(f'    Descargando imagen desde internet...')
                    req = urllib.request.Request(
                        data['photo_url'],
                        headers={'User-Agent': 'Mozilla/5.0'}
                    )
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        img_data = resp.read()

                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                        tmp.write(img_data)
                        tmp_path = tmp.name

                    try:
                        copier.save()
                        with open(tmp_path, 'rb') as f:
                            copier.main_image.save(data['photo_filename'], File(f), save=False)
                            copier.main_image_alt = data['main_image_alt']
                            copier.save(update_fields=['main_image', 'main_image_alt'])
                    finally:
                        os.unlink(tmp_path)

                self.stdout.write(self.style.SUCCESS(
                    f'    [OK] Creado con pk={copier.pk} y slug={copier.slug}'
                ))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'    [ERROR] {e}'))
                if copier.pk:
                    copier.delete()

        self.stdout.write('\n=== Listo ===\n')
