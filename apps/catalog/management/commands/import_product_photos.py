"""
Asigna automáticamente fotos de la carpeta 'fotos para pagina' del escritorio
a los consumibles del catálogo, basándose en coincidencia de números de modelo.

Uso:
    python manage.py import_product_photos
    python manage.py import_product_photos --dry-run     # solo muestra, no guarda
    python manage.py import_product_photos --overwrite   # reemplaza imágenes existentes
"""
import os
import re

from django.core.files import File
from django.core.management.base import BaseCommand

from apps.catalog.models import Consumable

PHOTOS_ROOT = r'C:\Users\User\Desktop\fotos para pagina'

# Carpeta raíz -> tipo de consumible en la DB
ROOT_TYPE_MAP = {
    'CILINDROS':    'drum',
    'CUCHILLAS':    'blade',
    'RODILLO FUSOR': 'fuser',
    'balineras':    'roller',
}

# Subcarpetas de la carpeta 'toner' -> tipo de consumible
TONER_SUBFOLDER_TYPE = {
    'TONER MP':                     'toner_bn',
    'TONER TK':                     'toner_bn',
    'KYOCERA TK 1152':              'toner_bn',
    'TONER HP LASER':               'toner_bn',
    'TONER HP 664,504,544':         'toner_bn',
    'TONER MINOLTA COLORES':        'toner_color',
    'TONER MINOLTA':                'toner_bn',
    'TONER COLOR RICOH':            'toner_color',
    'TONER TN 616 COLORES':         'toner_color',
    'TONER DE 1000 GRAMOS COLOR':   'toner_color',
    'TONER RECARGA COLOR':          'toner_color',
    'TONER RECARGA':                'toner_bn',
    'REVELADORES A COLOR':          'developer',
    'REVELADOR SHARP':              'developer',
    'TINTA HP LITRO COLORES':       'ink',
    'TINTA JP 7':                   'ink',
}


def clean_name(filename):
    """Devuelve el nombre base sin extensión ni sufijos de edición."""
    name = os.path.splitext(filename)[0]
    name = re.sub(r'-Photoroom\.png-Photoroom(\s*\(\d+\))?', '', name, flags=re.I)
    name = re.sub(r'-Photoroom', '', name, flags=re.I)
    name = re.sub(r'-removebg-preview', '', name, flags=re.I)
    name = re.sub(r'[.,\s\-]+$', '', name)
    result = name.strip().upper()
    # Ignorar nombres que son solo timestamps (ej: 20240516_112219)
    if re.match(r'^\d{8}_\d{6}$', result):
        return ''
    return result


def extract_tokens(text):
    """Extrae números de 3-5 dígitos y siglas clave del texto."""
    text = text.upper()
    numbers = set(re.findall(r'\b\d{3,5}\b', text))
    codes = set(re.findall(r'\b(MP|MPC|SP|TK|TN|HP|FS|ML|CLT|CF|CE|CB|CC|CZ|TASKalfa|M\d{4}|C\d{3,4})\b', text))
    return numbers | codes


def best_image_score(filename):
    """Puntuación para elegir la mejor foto de un grupo (mayor = mejor)."""
    name = filename.lower()
    score = 0
    if name.endswith('.png'):
        score += 10       # sin fondo es mejor
    # Penalizar nombres con muchos puntos extra (son fotos de ángulos secundarios)
    extra_dots = len(re.findall(r'\.(?!png|jpg)', name))
    score -= extra_dots
    # Penalizar nombres demasiado largos
    score -= len(filename) * 0.01
    return score


def collect_photos():
    """
    Devuelve lista de (consumable_type, base_name, file_path).
    Elige la mejor foto cuando hay varias versiones del mismo producto.
    """
    photos = []

    def process_folder(folder_path, ctype):
        """Agrupa archivos del folder por nombre base y elige el mejor."""
        if not os.path.isdir(folder_path):
            return
        groups = {}  # base_name -> (file_path, score)
        for fname in os.listdir(folder_path):
            if not fname.lower().endswith(('.png', '.jpg', '.jpeg')):
                continue
            base = clean_name(fname)
            if not base:
                continue
            fpath = os.path.join(folder_path, fname)
            score = best_image_score(fname)
            if base not in groups or score > groups[base][1]:
                groups[base] = (fpath, score)
        for base, (fpath, _) in groups.items():
            photos.append((ctype, base, fpath))

    def find_subfolder(parent, keyword):
        """Busca subcarpeta que contenga keyword (case insensitive)."""
        if not os.path.isdir(parent):
            return None
        for name in os.listdir(parent):
            if keyword.upper() in name.upper():
                return os.path.join(parent, name)
        return None

    # ── Carpetas simples: CILINDROS, CUCHILLAS, RODILLO FUSOR, balineras ──
    for folder_name, ctype in ROOT_TYPE_MAP.items():
        folder_path = os.path.join(PHOTOS_ROOT, folder_name)
        if not os.path.isdir(folder_path):
            continue

        # Preferir subcarpeta SIN FONDO; fallback a CON FONDO; fallback a raíz
        sf = find_subfolder(folder_path, 'SIN FONDO')
        cf = find_subfolder(folder_path, 'CON FONDO')
        search = sf or cf or folder_path
        process_folder(search, ctype)

    # ── Carpeta toner con múltiples subcarpetas ──
    toner_root = os.path.join(PHOTOS_ROOT, 'toner')
    if os.path.isdir(toner_root):
        # Archivo suelto en la raíz de balineras
        for fname in os.listdir(toner_root):
            fpath = os.path.join(toner_root, fname)
            if os.path.isfile(fpath) and fname.lower().endswith(('.png', '.jpg', '.jpeg')):
                photos.append(('toner_bn', clean_name(fname), fpath))

        # Recorrer subcarpetas
        for subname in os.listdir(toner_root):
            subpath = os.path.join(toner_root, subname)
            if not os.path.isdir(subpath):
                continue

            # Determinar tipo basado en el nombre de la subcarpeta
            ctype = None
            subkey = re.sub(r'\s*SIN FONDO\s*$', '', subname.strip(), flags=re.I).strip().upper()
            for key, t in TONER_SUBFOLDER_TYPE.items():
                if subkey.startswith(key.upper()):
                    ctype = t
                    break
            if ctype is None:
                # Fallback: si dice COLOR -> toner_color, si no -> toner_bn
                ctype = 'toner_color' if 'COLOR' in subname.upper() else 'toner_bn'

            # Preferir versión SIN FONDO de esta subcarpeta
            sf = find_subfolder(subpath, 'SIN FONDO')
            search = sf if sf else subpath
            process_folder(search, ctype)

    # Archivo suelto de balineras (está directamente en la carpeta)
    bal_root = os.path.join(PHOTOS_ROOT, 'balineras')
    if os.path.isdir(bal_root):
        for fname in os.listdir(bal_root):
            fpath = os.path.join(bal_root, fname)
            if os.path.isfile(fpath) and fname.lower().endswith(('.png', '.jpg', '.jpeg')):
                base = clean_name(fname)
                if base:
                    photos.append(('roller', base, fpath))

    return photos


def match_consumables(ctype, base_name, all_consumables):
    """
    Devuelve lista de consumibles que mejor coinciden con este nombre de foto.
    Usa overlap de números de modelo como métrica.
    """
    photo_tokens = extract_tokens(base_name)
    if not photo_tokens:
        return []

    scored = []
    for c in all_consumables.get(ctype, []):
        cons_tokens = extract_tokens(c.name)
        overlap = len(photo_tokens & cons_tokens)
        if overlap > 0:
            scored.append((overlap, c))

    if not scored:
        return []

    # Devolver todos los que tienen el máximo overlap
    max_score = max(s for s, _ in scored)
    return [c for s, c in scored if s == max_score]


class Command(BaseCommand):
    help = 'Importa fotos de productos y las asigna a consumibles por coincidencia de modelo'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Solo muestra el plan, no guarda nada')
        parser.add_argument('--overwrite', action='store_true', help='Reemplaza imágenes existentes')

    def handle(self, *args, **options):
        dry_run  = options['dry_run']
        overwrite = options['overwrite']

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Importando fotos de productos ===\n'))
        if dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN — no se guardarán cambios\n'))

        # Cargar todos los consumibles agrupados por tipo
        all_consumables = {}
        for c in Consumable.objects.all():
            all_consumables.setdefault(c.consumable_type, []).append(c)

        self.stdout.write(f'Consumibles en DB: {Consumable.objects.count()}')

        # Recopilar fotos
        photos = collect_photos()
        self.stdout.write(f'Fotos encontradas: {len(photos)}\n')

        assigned = 0
        skipped  = 0
        no_match = 0

        for ctype, base_name, fpath in sorted(photos, key=lambda x: x[1]):
            matches = match_consumables(ctype, base_name, all_consumables)

            if not matches:
                self.stdout.write(self.style.WARNING(f'  SIN MATCH [{ctype}] {base_name}'))
                no_match += 1
                continue

            for c in matches:
                if c.main_image and not overwrite:
                    skipped += 1
                    continue

                fname = os.path.basename(fpath)
                self.stdout.write(
                    self.style.SUCCESS(f'  [OK] [{ctype}] {base_name}') +
                    f'\n      -> [{c.pk}] {c.name[:60]}'
                )

                if not dry_run:
                    try:
                        with open(fpath, 'rb') as f:
                            c.main_image.save(fname, File(f), save=False)
                            c.main_image_alt = c.name[:200]
                            c.save(update_fields=['main_image', 'main_image_alt'])
                        assigned += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'      ERROR: {e}'))
                else:
                    assigned += 1

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\n=== Resultado ===\n'
            f'  Asignadas : {assigned}\n'
            f'  Omitidas  : {skipped} (ya tenían imagen)\n'
            f'  Sin match : {no_match}\n'
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING('Ejecuta sin --dry-run para aplicar los cambios.\n'))
