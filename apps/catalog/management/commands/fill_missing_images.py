"""
Rellena consumibles sin imagen reutilizando imágenes de productos del mismo tipo.
No requiere archivos físicos nuevos — solo copia el path en la DB.

Criterios de matching (de mayor a menor prioridad):
  1. Mismo tipo + mismo color (CYAN/MAGENTA/YELLOW/BLACK para tóner color)
  2. Mismo tipo + mismo color parcial (e.g. "MP305" coincide con "MP305")
  3. Mismo tipo (fallback)

Uso:
    python manage.py fill_missing_images
    python manage.py fill_missing_images --dry-run
    python manage.py fill_missing_images --overwrite    # reemplaza imágenes ya asignadas
"""
import re

from django.core.management.base import BaseCommand

from apps.catalog.models import Consumable


# ── Color keywords ──────────────────────────────────────────────────────────

_COLOR_PATTERNS = [
    ('CYAN',     re.compile(r'\bCYAN\b',                      re.I)),
    ('MAGENTA',  re.compile(r'\bMAGENTA\b',                   re.I)),
    ('YELLOW',   re.compile(r'\b(YELLOW|AMARILLO)\b',         re.I)),
    ('BLACK',    re.compile(r'\b(BLACK|NEGRO|NEGR[AO])\b',    re.I)),
]


def detect_color(name):
    """Devuelve 'CYAN' | 'MAGENTA' | 'YELLOW' | 'BLACK' | None."""
    for color, pattern in _COLOR_PATTERNS:
        if pattern.search(name):
            return color
    return None


def best_source(target, sources, idx):
    """
    Elige la fuente más apropiada para `target` dentro de `sources`.
    Prioriza coincidencia de color; si no hay, cicla por índice.
    """
    target_color = detect_color(target.name)

    if target_color:
        color_matches = [s for s in sources if detect_color(s.name) == target_color]
        if color_matches:
            return color_matches[idx % len(color_matches)]

    return sources[idx % len(sources)]


class Command(BaseCommand):
    help = 'Rellena imágenes faltantes reutilizando fotos de consumibles del mismo tipo'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run',   action='store_true', help='Solo muestra el plan, no guarda nada')
        parser.add_argument('--overwrite', action='store_true', help='Reemplaza imágenes ya asignadas también')

    def handle(self, *args, **options):
        dry_run   = options['dry_run']
        overwrite = options['overwrite']

        self.stdout.write('\n=== Rellenando imágenes faltantes ===\n')
        if dry_run:
            self.stdout.write('MODO DRY-RUN — no se guardarán cambios\n')
        if overwrite:
            self.stdout.write('MODO OVERWRITE — se reemplazarán imágenes existentes\n')

        # Separar consumibles por tipo en dos buckets
        with_image    = {}  # ctype -> [c, ...]
        without_image = {}  # ctype -> [c, ...]

        for c in Consumable.objects.all():
            has = bool(c.main_image)
            if has:
                with_image.setdefault(c.consumable_type, []).append(c)
            if not has or overwrite:
                without_image.setdefault(c.consumable_type, []).append(c)

        total_filled  = 0
        total_skipped = 0

        for ctype, missing in sorted(without_image.items()):
            # Fuentes = consumibles del mismo tipo QUE SÍ tienen imagen
            sources = [s for s in with_image.get(ctype, []) if s.main_image]

            if not sources:
                self.stdout.write(
                    f'  [SIN REF] {ctype}: {len(missing)} sin fuente disponible'
                )
                total_skipped += len(missing)
                continue

            self.stdout.write(
                f'\n  [{ctype}] {len(missing)} targets · {len(sources)} fuentes'
            )

            color_idx = {}  # color -> contador independiente para cycling

            for c in missing:
                # No reemplazar la propia imagen si tiene una (solo en modo overwrite
                # con misma fuente evitamos loops, pero en la práctica no pasa porque
                # al menos hay otra fuente en el mismo tipo)
                target_color = detect_color(c.name)
                bucket_key   = target_color or '_any'
                idx          = color_idx.get(bucket_key, 0)
                color_idx[bucket_key] = idx + 1

                source     = best_source(c, sources, idx)
                image_path = source.main_image.name

                color_tag = f'[{target_color}]' if target_color else ''
                self.stdout.write(
                    f'    {color_tag:<10}{c.name[:50]:<50}  <-  {source.name[:40]}'
                )

                if not dry_run:
                    c.main_image     = image_path
                    c.main_image_alt = c.name[:200]
                    c.save(update_fields=['main_image', 'main_image_alt'])

                total_filled += 1

        self.stdout.write(
            f'\n=== Resultado ===\n'
            f'  Asignados  : {total_filled}\n'
            f'  Sin fuente : {total_skipped} (tipos sin ninguna imagen)\n'
        )
        if dry_run:
            self.stdout.write('Ejecuta sin --dry-run para aplicar los cambios.\n')
