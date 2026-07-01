"""
Descarga las fotos oficiales de Ricoh USA (sin fondo) para cada equipo del catálogo
y las asigna sobreescribiendo la imagen actual.

Uso:
    python manage.py import_ricoh_official_photos
    python manage.py import_ricoh_official_photos --dry-run
"""
import os
import tempfile
import time
import urllib.request

from django.core.files import File
from django.core.management.base import BaseCommand

from apps.catalog.models import Copier

# brand, model_number -> (url_imagen, nombre_archivo)
OFFICIAL_IMAGES = {
    ('Ricoh', 'MP 301SP'): (
        'http://images.salsify.com/images/qugtbe5bfiy5syg7sqzc/'
        'ricohimages_Equipment_Printers-and-Copiers_Eqp-MP-301SPF-10.png',
        'ricoh-mp-301spf.png',
    ),
    ('Ricoh', 'MP 2554'): (
        'http://images.salsify.com/images/l5ixoyyiynzxzselptp5/'
        'ricohimages_Equipment_Printers-and-Copiers_Eqp-MP-2554-10.png',
        'ricoh-mp-2554.png',
    ),
    ('Ricoh', 'MP 2555SP'): (
        'http://images.salsify.com/images/m7u8cv6baydtj8qtxhkw/'
        'ricohimages_Equipment_Printers-and-Copiers_Eqp-MP-2555-10.png',
        'ricoh-mp-2555.png',
    ),
    ('Ricoh', 'MP 3054'): (
        'http://images.salsify.com/images/kzgkvpqlap9ghoqwshhv/'
        'ricohimages_Equipment_Printers-and-Copiers_Eqp-MP-3054-10.png',
        'ricoh-mp-3054.png',
    ),
    ('Ricoh', 'MP 3055SP'): (
        'http://images.salsify.com/images/rfaxq5fwpdykq1vsodca/'
        'ricohimages_Equipment_Printers-and-Copiers_Eqp-MP-3055-10.png',
        'ricoh-mp-3055.png',
    ),
    ('Ricoh', 'MP 4002'): (
        # Sin página propia en Ricoh USA — mismo chasis que MP 3054 (misma generación)
        'http://images.salsify.com/images/kzgkvpqlap9ghoqwshhv/'
        'ricohimages_Equipment_Printers-and-Copiers_Eqp-MP-3054-10.png',
        'ricoh-mp-4002.png',
    ),
    ('Ricoh', 'MP 4055SP'): (
        'http://images.salsify.com/images/bgsjdlqznhly7dpnc3og/'
        'ricohimages_Equipment_Printers-and-Copiers_Eqp-MP-4055SP-TE-10.png',
        'ricoh-mp-4055sp.png',
    ),
    ('Ricoh', 'IM 430F'): (
        'http://images.salsify.com/images/q3lrhjms2x7yr17hzgdh/'
        'ricohimages_Equipment_Printers-and-Copiers_eqp-im-430F-10.png',
        'ricoh-im-430f.png',
    ),
    ('Ricoh', 'MP C2004'): (
        'http://images.salsify.com/images/urtmfvdepcguylbdolbt/'
        'ricohimages_Equipment_Printers-and-Copiers_Eqp-MP-C2004-10.png',
        'ricoh-mp-c2004.png',
    ),
    ('Ricoh', 'MP C3003'): (
        'http://images.salsify.com/images/idtqbzksknvob6ac9egs/'
        'ricohimages_Equipment_Printers-and-Copiers_Eqp-MP-C3003-10.png',
        'ricoh-mp-c3003.png',
    ),
    ('Ricoh', 'MP C3004'): (
        'http://images.salsify.com/images/yucn9oqez7hlrbdtiy1w/'
        'ricohimages_Equipment_Printers-and-Copiers_Eqp-MP-C3004-10.png',
        'ricoh-mp-c3004.png',
    ),
    ('Ricoh', 'IMC 2500'): (
        'http://images.salsify.com/images/d9dzvn2lqxbncol50tzx/'
        'ricohimages_Equipment_Printers-and-Copiers_eqp-im-c2500-10.png',
        'ricoh-im-c2500.png',
    ),
    ('Ricoh', 'MPC 4503'): (
        'http://images.salsify.com/images/ayywcxdp22s2f1zarjsp/'
        'ricohimages_Equipment_Printers-and-Copiers_Eqp-MP-C4503-10.png',
        'ricoh-mp-c4503.png',
    ),
    ('Ricoh', 'IM C2000'): (
        'http://images.salsify.com/images/g4tqtmy0dlaoprotrgld/'
        'ricohimages_Equipment_Printers-and-Copiers_eqp-im-c2000-10.png',
        'ricoh-im-c2000.png',
    ),
}

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; Ricoh catalog importer)'}


def download_image(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


class Command(BaseCommand):
    help = 'Descarga fotos oficiales Ricoh USA y las asigna a los equipos del catalogo'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        self.stdout.write('\n=== Importando fotos oficiales Ricoh ===\n')
        if dry_run:
            self.stdout.write('MODO DRY-RUN\n\n')

        ok = 0
        err = 0
        skip = 0

        for (brand, model), (url, fname) in OFFICIAL_IMAGES.items():
            try:
                copier = Copier.objects.get(brand=brand, model_number=model)
            except Copier.DoesNotExist:
                self.stdout.write(f'  [NO EXISTE] {brand} {model} — omitido')
                skip += 1
                continue

            self.stdout.write(f'  {brand} {model:<15}  {fname}')

            if dry_run:
                ok += 1
                continue

            try:
                img_bytes = download_image(url)

                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                    tmp.write(img_bytes)
                    tmp_path = tmp.name

                try:
                    with open(tmp_path, 'rb') as f:
                        copier.main_image.save(fname, File(f), save=False)
                        copier.main_image_alt = f'{brand} {model} - {copier.name}'
                        copier.save(update_fields=['main_image', 'main_image_alt'])
                finally:
                    os.unlink(tmp_path)

                self.stdout.write(self.style.SUCCESS(f'    [OK]'))
                ok += 1
                time.sleep(0.3)  # cortesia al CDN

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'    [ERROR] {e}'))
                err += 1

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\n=== Resultado ===\n'
            f'  OK        : {ok}\n'
            f'  Errores   : {err}\n'
            f'  No existe : {skip}\n'
        ))
        if dry_run:
            self.stdout.write('Ejecuta sin --dry-run para aplicar.\n')
