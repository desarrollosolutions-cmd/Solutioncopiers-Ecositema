"""
Asigna fotos de chips desde la carpeta 'fotos pagina/CHIP MPC' del escritorio
a los consumibles de tipo 'chip' en el catalogo.

Uso:
    python manage.py import_chip_photos
    python manage.py import_chip_photos --dry-run
    python manage.py import_chip_photos --overwrite
    python manage.py import_chip_photos --folder "C:\\otra\\ruta\\CHIP MPC"
"""
import os
import re
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand

from apps.catalog.models import Consumable

DEFAULT_FOLDER = r'C:\Users\User\Desktop\fotos pagina\CHIP MPC'

# Mapa manual: normalize(ref_en_archivo) -> part_number_en_BD
# Para casos donde la normalizacion automatica no basta.
MANUAL_MAP = {
    # NC-RCC406 tiene doble C en el archivo pero NC-RC406 en BD
    'ncrcc406tk':       'NCRC406TK',
    'ncrcc406tc':       'NCRC406TC',
    'ncrcc406tcww4':    'NCRC406TC',
    'ncrcc406tm':       'NCRC406TM',
    'ncrcc406tmww4':    'NCRC406TM',
    'ncrcc406ty':       'NCRC406TY',
    'ncrcc406tyww4':    'NCRC406TY',
    # NC-RC03-04 (rango de modelos) -> refs individuales en BD
    'ncrc0304ultkww4':  'NCRC04ULTK/NCRC03/04ULTK/NCRC0',
    'ncrc0304ulm':      'NCRC04ULTM',
    'ncrc0304ulmww4':   'NCRC04ULTM',
    'ncrc0304ulty':     'NCRC04ULTY',
    'ncrc0304ultyww4':  'NCRC04ULTY',
    # NC-RCIMC300 (archivo tiene RC extra en el prefijo)
    'ncrcimc300tc':     'NCIMC300TC',
    'ncrcimc300ty':     'NCIMC300TY',
    # Archivo con typo: NC-RC3ChTC deberia ser NC-RC300TC
    'ncrc3chtc':        'NCRC300TC',
    # NC-RCC406TK con sufijo -WW4
    'ncrcc406tkww4':    'NCRC406TK',
    # NC-RCSP4500HT <-> NCRCSP4500TH (letras invertidas en archivo)
    'ncrcsp4500ht':     'NCRCSP4500TH',
    # Toshiba 30: archivo sin U intermedia
    'nctos30m':         'NCTOS30UM',
    'nctos30c':         'NCTOS30UC',
    'nctos30k':         'NCTOS30UK',
    'nctos30y':         'NCTOS30UY',
}


def normalize(text: str) -> str:
    return re.sub(r'[^a-z0-9]', '', text.lower())


def extract_ref(stem: str) -> str:
    """Todo lo que precede a '  Chip' o ' Chip' en el nombre del archivo."""
    parts = re.split(r'\s{2,}|\s+(?=chip)', stem, maxsplit=1, flags=re.IGNORECASE)
    return parts[0].strip()


def find_match(norm_ref: str, db_map: dict) -> 'Consumable | None':
    """1. Mapa manual  2. Exacto  3. Prefijo."""
    # Mapa manual
    part_number = MANUAL_MAP.get(norm_ref)
    if part_number:
        return db_map.get(normalize(part_number))

    # Exacto
    if norm_ref in db_map:
        return db_map[norm_ref]

    # Prefijo (variantes regionales: -EXU, -WW, -USA04, ...)
    for db_norm, consumable in db_map.items():
        if norm_ref.startswith(db_norm) or db_norm.startswith(norm_ref):
            return consumable

    return None


class Command(BaseCommand):
    help = 'Importa fotos de chips y las asigna a consumibles por referencia'

    def add_arguments(self, parser):
        parser.add_argument('--folder', default=DEFAULT_FOLDER)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--overwrite', action='store_true')

    def handle(self, *args, **options):
        folder    = Path(options['folder'])
        dry_run   = options['dry_run']
        overwrite = options['overwrite']

        self.stdout.write('\n=== Importando fotos de chips ===\n')
        if dry_run:
            self.stdout.write('[DRY-RUN] no se guardaran cambios\n')

        if not folder.is_dir():
            self.stderr.write(f'No se encontro la carpeta: {folder}')
            return

        # Construir mapa normalizado de chips en BD
        chips   = Consumable.objects.filter(consumable_type='chip')
        db_map  = {normalize(c.part_number): c for c in chips if c.part_number}
        self.stdout.write(f'Chips en BD     : {chips.count()} (con referencia: {len(db_map)})')

        image_files = sorted(
            f for f in folder.iterdir()
            if f.suffix.lower() in ('.png', '.jpg', '.jpeg') and f.is_file()
        )
        self.stdout.write(f'Fotos en carpeta: {len(image_files)}\n')

        assigned  = 0
        skipped   = 0
        no_match  = 0
        duplicate = {}  # consumable_pk -> primer filename asignado

        for photo in image_files:
            ref = extract_ref(photo.stem)

            # Ignorar archivos sin referencia clara al inicio
            if not ref or ref.upper().startswith('CHIP') or ref.upper().startswith('TONER'):
                self.stdout.write(f'  OMITIDO (sin ref): {photo.name}')
                no_match += 1
                continue

            norm_ref = normalize(ref)
            match    = find_match(norm_ref, db_map)

            if not match:
                self.stdout.write(f'  SIN MATCH: {photo.name}  [ref={ref!r}]')
                no_match += 1
                continue

            # Detectar duplicate en esta ejecucion
            if match.pk in duplicate:
                self.stdout.write(
                    f'  DUPLICADO: {photo.name}'
                    f' -> ya cubierto por {duplicate[match.pk]}'
                )
                skipped += 1
                continue

            if match.main_image and not overwrite:
                self.stdout.write(
                    f'  SKIP (ya tiene imagen): [{match.pk}] {match.name[:55]}'
                )
                skipped += 1
                duplicate[match.pk] = photo.name
                continue

            self.stdout.write(
                f'  OK  {photo.name}\n'
                f'      -> [{match.pk}] {match.part_number}  {match.name[:55]}'
            )
            duplicate[match.pk] = photo.name

            if not dry_run:
                try:
                    with open(photo, 'rb') as f:
                        match.main_image.save(photo.name, File(f), save=False)
                        match.main_image_alt = match.name[:200]
                        match.save(update_fields=['main_image', 'main_image_alt'])
                    assigned += 1
                except Exception as exc:
                    self.stdout.write(f'      ERROR: {exc}')
            else:
                assigned += 1

        self.stdout.write(
            f'\n=== Resultado ===\n'
            f'  Asignadas  : {assigned}\n'
            f'  Omitidas   : {skipped}\n'
            f'  Sin match  : {no_match}\n'
        )
        if dry_run:
            self.stdout.write('Ejecuta sin --dry-run para aplicar los cambios.\n')
