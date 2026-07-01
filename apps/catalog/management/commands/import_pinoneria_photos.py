"""
Asigna fotos de la carpeta 'fotos pagina/PIÑONERIA' del escritorio
a los consumibles (repuestos: piñones, bujes, sellos, etc.) por referencia.

El nombre de archivo trae la referencia al inicio (uno o más códigos
alfanuméricos separados por espacios/guiones) seguida de la descripción
del repuesto, igual que en import_chip_photos.py.

Uso:
    python manage.py import_pinoneria_photos
    python manage.py import_pinoneria_photos --dry-run
    python manage.py import_pinoneria_photos --overwrite
    python manage.py import_pinoneria_photos --folder "C:\\otra\\ruta\\PIÑONERIA"
"""
import os
import re
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand

from apps.catalog.models import Consumable

DEFAULT_FOLDER = r'C:\Users\User\Desktop\fotos pagina\PIÑONERIA'

# Mapa manual para casos donde la normalización automática no basta.
MANUAL_MAP = {
    # archivo trae dos refs juntas con guion -> ref compuesta en BD
    'b0654234b2474234':   'B0654234',
    'd1292607d00926':     'D1292607',
    'd2024234d2024244':   'D2024234',
    'cet3714ae030053':    'CET3714',
    # archivo sin guion intermedio entre dos códigos pegados
    'd0672710b0442710':   'D0672710',
    # referencia en BD trae prefijo "(1)" que rompe la normalización
    'b0443426':           '(1)B0443426',
    # archivo usa código de catálogo del fabricante (W253-2110), BD usa código interno (116FT)
    'w2532110':           '116FT',
}

# Casos donde la referencia NO está al inicio del nombre (archivo empieza con
# una palabra descriptiva). Se busca el fragmento normalizado en cualquier
# parte del nombre del archivo.
FULL_TEXT_OVERRIDES = [
    ('205120602075600060016002', 'KIT8000ANG'),
    ('102720222027angdelgado',   '6YFL'),
]

# Palabras que indican que el token YA NO es parte de la referencia
_STOPWORDS = {
    'ALIMENTADOR', 'THERMISTOR', 'EJE', 'MANDRIL', 'TOLVA', 'RESORTE', 'TUBO',
    'UNID', 'RECICLAJE', 'FLAUTA', 'PIÑON', 'PIÑONES', 'CEPILLO', 'LIMPIEZA',
    'UR', 'ORIGINAL', 'ENGRANA', 'EN', 'EL', 'RODILLO', 'MAGNETICO', 'GRANA',
    'REVELADO', 'UNIDAD', 'TRANSFERENCIA', 'COLLECTION', 'GEA', 'WEB', 'SELLO',
    'REV', 'REVRODILLO', 'ASPAS', 'BLANCA', 'RECOGEDOR', 'PAD', 'FRICCION',
    'CASETERA', 'ADF', 'ESPUMA', 'FINISCHER', 'BALINERA', 'INFE', 'KIT', 'POR',
    'GENERICAS', 'GENERICA', 'GENERICO', 'GENÉRICO', 'BUJE', 'FUSOR', 'PAR',
    'COLLAR', 'SEPARACION', 'REGISTRO', 'SINCRONISMO', 'PALANCA', 'FRONTAL',
    'Y', 'POSTERIOR', 'FUSORA', 'X2', 'X3', 'X4', 'CAUCHO', 'BOMBA', 'AF',
    'ANG', 'DELGADO', 'CON', 'COGEDORA', 'VERDE', 'RICOH', 'MP', 'AE03', 'R',
}


def normalize(text: str) -> str:
    return re.sub(r'[^a-z0-9]', '', text.lower())


def extract_ref(stem: str) -> str:
    """
    Toma los tokens iniciales que parecen referencia (alfanumericos con
    guion y al menos un digito) hasta encontrar la primera palabra
    descriptiva conocida.
    """
    tokens = stem.split()
    ref_tokens = []
    for tok in tokens:
        clean = tok.strip('-')
        upper = clean.upper()
        if upper in _STOPWORDS:
            break
        has_digit = any(ch.isdigit() for ch in clean)
        looks_like_code = bool(re.match(r'^[A-Za-zÑñ0-9\-]+$', clean)) and has_digit
        if looks_like_code:
            ref_tokens.append(clean)
            continue
        break
    return ' '.join(ref_tokens)


def find_match(norm_ref: str, db_map: dict):
    """1. Mapa manual  2. Exacto  3. Prefijo/contención."""
    mapped = MANUAL_MAP.get(norm_ref)
    if mapped:
        return db_map.get(normalize(mapped))

    if norm_ref in db_map:
        return db_map[norm_ref]

    for db_norm, consumable in db_map.items():
        if not db_norm:
            continue
        if norm_ref.startswith(db_norm) or db_norm.startswith(norm_ref):
            return consumable

    return None


class Command(BaseCommand):
    help = 'Importa fotos de piñonería/repuestos y las asigna a consumibles por referencia'

    def add_arguments(self, parser):
        parser.add_argument('--folder', default=DEFAULT_FOLDER)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--overwrite', action='store_true')

    def handle(self, *args, **options):
        folder    = Path(options['folder'])
        dry_run   = options['dry_run']
        overwrite = options['overwrite']

        self.stdout.write('\n=== Importando fotos de PIÑONERIA ===\n')
        if dry_run:
            self.stdout.write('[DRY-RUN] no se guardaran cambios\n')

        if not folder.is_dir():
            self.stderr.write(f'No se encontro la carpeta: {folder}')
            return

        # Construir mapa normalizado: cada parte de un part_number con "/" se mapea individualmente
        db_map = {}
        for c in Consumable.objects.exclude(part_number=''):
            for piece in re.split(r'[/,]', c.part_number):
                piece = piece.strip()
                if piece:
                    db_map[normalize(piece)] = c
        self.stdout.write(f'Consumibles con referencia en BD: {len(db_map)}')

        image_files = sorted(
            f for f in folder.iterdir()
            if f.suffix.lower() in ('.png', '.jpg', '.jpeg') and f.is_file()
        )
        self.stdout.write(f'Fotos en carpeta: {len(image_files)}\n')

        assigned  = 0
        skipped   = 0
        no_match  = 0
        duplicate = {}

        for photo in image_files:
            ref = extract_ref(photo.stem)
            match = None

            if ref:
                norm_ref = normalize(ref)
                match = find_match(norm_ref, db_map)

            if not match:
                # Intentar por fragmento de texto completo (referencia al final o ausente)
                norm_full = normalize(photo.stem)
                for fragment, target in FULL_TEXT_OVERRIDES:
                    if fragment in norm_full:
                        match = db_map.get(normalize(target))
                        if match:
                            break

            if not match:
                label = ref or '(sin ref detectada)'
                self.stdout.write(f'  SIN MATCH: {photo.name}  [ref={label!r}]')
                no_match += 1
                continue

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
