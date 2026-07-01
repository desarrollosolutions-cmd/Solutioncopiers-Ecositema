"""
Asigna fotos de la carpeta 'Fotocopiadoras' a los equipos del catálogo.
Matching por tokens del número de modelo.  Para copiers sin match exacto
se reutiliza la foto del equipo más similar (misma familia/serie).

Uso:
    python manage.py import_copier_photos
    python manage.py import_copier_photos --dry-run
"""
import os
import re

from django.core.files import File
from django.core.management.base import BaseCommand

from apps.catalog.models import Copier

PHOTOS_ROOT = r'C:\Users\User\Desktop\fotos para pagina\Fotocopiadoras'


def clean_name(filename):
    name = os.path.splitext(filename)[0]
    name = re.sub(r'[-_]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip().upper()
    return name


def extract_tokens(text):
    """Extrae números de modelo y prefijos de serie (sin marcas genéricas)."""
    text = text.upper()
    # Números 3-4 dígitos NO adyacentes a otros dígitos (ej. "3055" en "3055SP" o "MP 3055")
    numbers = set(re.findall(r'(?<!\d)\d{3,4}(?!\d)', text))
    # Para números de 5 dígitos (ej. "40550"), añadir también el prefijo de 4 (4055)
    for n5 in re.findall(r'(?<!\d)\d{5}(?!\d)', text):
        numbers.add(n5[:4])
    # Prefijos de serie relevantes (no marcas)
    codes = set(re.findall(r'\b(IMC|IM|MPC|MP|SP)\b', text))
    return numbers | codes


def score_match(photo_tokens, copier):
    """Overlap de tokens entre foto y modelo del copier."""
    cop_text  = f"{copier.brand} {copier.model_number} {copier.name}"
    cop_tokens = extract_tokens(cop_text)
    return len(photo_tokens & cop_tokens)


class Command(BaseCommand):
    help = 'Importa fotos de equipos y las asigna a los Copiers por coincidencia de modelo'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Solo muestra el plan, no guarda nada')

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        self.stdout.write('\n=== Importando fotos de equipos ===\n')
        if dry_run:
            self.stdout.write('MODO DRY-RUN\n')

        # ── Recolectar fotos (ignorar nombres genéricos) ──────────────────
        SKIP_NAMES = {'IMAGES', 'IMAGE', 'FOTO', 'PHOTO'}
        photos = []
        for fname in os.listdir(PHOTOS_ROOT):
            fpath = os.path.join(PHOTOS_ROOT, fname)
            if not os.path.isfile(fpath):
                continue
            if not fname.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                continue
            base = clean_name(fname)
            if base in SKIP_NAMES or not base:
                self.stdout.write(f'  [SKIP genérico] {fname}')
                continue
            photos.append((base, fpath, fname))
            self.stdout.write(f'  [FOTO] {fname}  ->  base: "{base}"')

        if not photos:
            self.stdout.write(self.style.ERROR('No se encontraron fotos válidas.'))
            return

        copiers = list(Copier.objects.all())
        self.stdout.write(f'\nEquipos en DB: {len(copiers)}')
        self.stdout.write(f'Fotos válidas: {len(photos)}\n')

        # ── Paso 1: match exacto (mejor overlap) ─────────────────────────
        # Para cada copier, calcula cuál foto tiene mayor overlap
        assignment = {}  # copier.pk -> (score, base, fpath, fname)

        for cop in copiers:
            best_score = 0
            best_photo = None
            for base, fpath, fname in photos:
                tokens = extract_tokens(base)
                s = score_match(tokens, cop)
                if s > best_score:
                    best_score = s
                    best_photo = (base, fpath, fname)
            if best_photo and best_score > 0:
                assignment[cop.pk] = (best_score, *best_photo)

        # ── Paso 2: fallback por serie ────────────────────────────────────
        # Foto con más tokens de modelo = más genérica/versátil (para serie MP)
        mp_fallback = max(photos, key=lambda x: len(extract_tokens(x[0])))
        # Foto con token "IM" o "430" (para serie IM/IMC)
        im_fallback = next(
            (p for p in photos if 'IM' in extract_tokens(p[0]) or '430' in extract_tokens(p[0])),
            mp_fallback,
        )
        biggest_photo = max(photos, key=lambda x: os.path.getsize(x[1]))

        assigned = 0
        fallback  = 0

        self.stdout.write('-' * 70)
        for idx, cop in enumerate(copiers):
            if cop.pk in assignment:
                score, base, fpath, fname = assignment[cop.pk]
                tag = f'[MATCH score={score}]'
            else:
                model_upper = cop.model_number.upper()
                if model_upper.startswith(('IM', 'IMC')):
                    base, fpath, fname = im_fallback
                else:
                    base, fpath, fname = mp_fallback
                tag = '[FALLBACK]'
                fallback += 1

            self.stdout.write(
                f'{tag:<20} {cop.brand} {cop.model_number:<15}  <-  {fname}'
            )

            if not dry_run:
                try:
                    with open(fpath, 'rb') as f:
                        cop.main_image.save(fname, File(f), save=False)
                        cop.main_image_alt = f'{cop.brand} {cop.model_number} - {cop.name}'
                        cop.save(update_fields=['main_image', 'main_image_alt'])
                    assigned += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ERROR: {e}'))
            else:
                assigned += 1

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\n=== Resultado ===\n'
            f'  Con match exacto : {assigned - fallback}\n'
            f'  Con foto fallback : {fallback}\n'
            f'  Total actualizado : {assigned}\n'
        ))
        if dry_run:
            self.stdout.write('Ejecuta sin --dry-run para aplicar.\n')
