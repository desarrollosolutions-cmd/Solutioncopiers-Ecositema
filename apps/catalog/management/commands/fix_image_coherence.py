"""
Corrige imagenes incoherentes o con referencias rotas en el catalogo de consumibles.

Problemas que detecta y corrige:
  1. Productos tipo 'drum' (cilindros) con imagenes de fuser, toner o tinta.
  2. Productos tipo 'toner_bn' con imagenes de tinta (TINTA_*) o referencias rotas.
  3. Productos tipo 'toner_color' con referencias a archivos que ya no existen en disco.
  4. Productos tipo 'fuser' con imagenes de toner, drum o tinta.
  5. Productos tipo 'ink' con imagenes que no son de tinta.
  6. Productos 'ink' YELLOW/AMARILLO con imagen de tinta NEGRA.

Uso:
    python manage.py fix_image_coherence
    python manage.py fix_image_coherence --dry-run
"""
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.catalog.models import Consumable

MEDIA_ROOT = Path(settings.MEDIA_ROOT)

# ---------------------------------------------------------------------------
# Imagenes disponibles por tipo
# ---------------------------------------------------------------------------

DRUM_IMAGES = {
    'sp':       'content/originals/CILINDRO_SP_340034103500.3510-Photoroom.png-Photoroom.webp',
    'mpc':      'content/originals/CILINDRO_MPC_25502551-Photoroom.png-Photoroom.webp',
    'mp_large': 'content/originals/CILINDRO_MP_40005000-Photoroom.png-Photoroom.webp',
    'mp':       'content/originals/CILINDRO_MP_102225502852-Photoroom.png-Photoroom.webp',
    'small':    'content/originals/CILINDRO_10131515201301_-.webp',
}

FUSER_IMAGE = (
    'content/originals/'
    'RODILLO_FUSOR_MP_205120602075_IKON_2871.-Photoroom.png-Photoroom.webp'
)

# Pool de imagenes genericas de toner para toner_bn con imagen incorrecta
TONER_POOL = [
    'content/originals/img-toner-1.webp',
    'content/originals/img-toner-1_1wmGTRr.webp',
    'content/originals/img-toner-1_bvORAtu.webp',
    'content/originals/img-toner-1_IzoC5C3.webp',
    'content/originals/img-toner-1_Ml5waKw.webp',
    'content/originals/img-toner-1_PFedAWo.webp',
    'content/originals/img-toner-2.webp',
    'content/originals/img-toner-2_275HfwT.webp',
    'content/originals/img-toner-2_fSTm9Le.webp',
    'content/originals/img-toner-2_fxPVUTx.webp',
    'content/originals/img-toner-2_SYwUgdd.webp',
    'content/originals/img-toner-3.webp',
    'content/originals/img-toner-3_FkxxS9K.webp',
]

# Pool de imagenes de toner MPC (para reparar referencias rotas en toner_color)
MPC_BLACK_POOL = [
    'content/originals/MPC_3003_BLACK.webp',
    'content/originals/MPC_3003_BLACK_3jnr873.webp',
    'content/originals/MPC_3003_BLACK_cicJDGe.webp',
    'content/originals/MPC_3003_BLACK_e3OXq1j.webp',
    'content/originals/MPC_3003_BLACK_GMuC8NX.webp',
    'content/originals/MPC_3003_BLACK_rCb80he.webp',
    'content/originals/MPC_3003_BLACK_wmd6ctU.webp',
]

INK_BLACK  = 'content/originals/TINTA_HP_LITRO_BLACK.webp'
INK_YELLOW = 'content/originals/TINTA__HP_664_YELLOW_GENERICA.webp'

TK_TONER  = 'content/originals/TK-3102_AMERICANO.webp'
KM_TONER  = 'content/originals/TONER_TDI_KONICA_MINOLTA_BLACK__PRO_C_6000C7000.webp'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def classify_image(basename: str) -> str:
    """Clasifica la imagen segun su nombre de archivo."""
    n = basename.upper()
    # Chips primero — sus nombres contienen "TK-" como subcadena (ej. ULTK-WW4)
    # y debe evaluarse antes del patron de toner
    if any(x in n for x in ('NC-RC', 'NC-KM', 'NC-TK', 'NC-TOS', 'NC-IMC')) or n.startswith('CHIP'):
        return 'chip'
    if 'CILINDRO' in n:
        return 'drum'
    if 'RODILLO' in n:
        return 'fuser'
    if 'TINTA' in n:
        return 'ink'
    if any(x in n for x in ('IMG-TONER', 'MPC_', 'TONER_', 'TK-3102', 'TK-', 'TN_324')):
        return 'toner'
    if 'CUCHILLA' in n:
        return 'blade'
    return 'unknown'


# Categorias de imagen aceptables para cada tipo de producto
ACCEPTABLE = {
    'drum':        {'drum'},
    'fuser':       {'fuser'},
    'ink':         {'ink'},
    'toner_bn':    {'toner'},
    'toner_color': {'toner'},
    'chip':        {'chip'},
    'blade':       {'blade', 'unknown'},
    'roller':      {'fuser', 'unknown'},
    'developer':   {'toner', 'unknown'},
    'kit':         {'toner', 'fuser', 'drum', 'unknown'},
    'other':       {'toner', 'fuser', 'drum', 'ink', 'blade', 'chip', 'unknown'},
}


def is_incoherent(img_category: str, product_type: str) -> bool:
    allowed = ACCEPTABLE.get(product_type, {'unknown'})
    return img_category not in allowed


def pick_drum_image(name: str) -> str:
    n = name.upper()
    if 'SP ' in n or 'SP4' in n or 'SP3' in n:
        return DRUM_IMAGES['sp']
    if 'MPC' in n or 'MP C' in n or 'C220' in n or 'C224' in n or 'C305' in n:
        return DRUM_IMAGES['mpc']
    if '4000' in n or '5000' in n or '4500' in n:
        return DRUM_IMAGES['mp_large']
    if 'DI ' in n or 'DI1' in n or '1013' in n or '1015' in n or '1018' in n:
        return DRUM_IMAGES['small']
    return DRUM_IMAGES['mp']


def pick_toner_bn_image(name: str, pool_idx: int) -> str:
    n = name.upper()
    if 'KYOCERA' in n or ' TK-' in n or ' TK ' in n:
        return TK_TONER
    if 'KONICA' in n or 'MINOLTA' in n or 'BIZHUB' in n:
        return KM_TONER
    return TONER_POOL[pool_idx % len(TONER_POOL)]


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = 'Corrige imagenes incoherentes o rotas en el catalogo de consumibles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Muestra los cambios sin guardarlos',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        self.stdout.write('\n=== Revision de coherencia de imagenes ===\n')
        if dry_run:
            self.stdout.write('[DRY-RUN] no se guardaran cambios\n')

        # Archivos que realmente existen en disco
        originals_dir = MEDIA_ROOT / 'content' / 'originals'
        existing = {
            f'content/originals/{f.name}'
            for f in originals_dir.iterdir()
            if f.is_file()
        }

        consumables = (
            Consumable.objects
            .filter(main_image__isnull=False)
            .exclude(main_image='')
            .order_by('pk')
        )

        fixed = broken_count = incoherent_count = ok = 0
        toner_pool_idx = 0
        mpc_pool_idx   = 0

        for product in consumables:
            current = product.main_image.name          # 'content/originals/XXXX.webp'
            basename = os.path.basename(current)
            img_cat  = classify_image(basename)
            ptype    = product.consumable_type

            file_exists = current in existing
            type_ok     = not is_incoherent(img_cat, ptype)

            # Caso especial: ink YELLOW con imagen de tinta NEGRA (color incoherente)
            yellow_ink_mismatch = (
                ptype == 'ink'
                and file_exists
                and type_ok
                and ('YELLOW' in product.name.upper() or 'AMARILLO' in product.name.upper())
                and 'LITRO_BLACK' in basename.upper()
            )

            if file_exists and type_ok and not yellow_ink_mismatch:
                ok += 1
                continue

            # Contadores de razon
            reasons = []
            if not file_exists:
                reasons.append('ROTO')
                broken_count += 1
            if not type_ok:
                reasons.append(f'INCOHERENTE [{img_cat}->{ptype}]')
                incoherent_count += 1
            if yellow_ink_mismatch:
                reasons.append('COLOR [amarillo con imagen negra]')
                incoherent_count += 1

            # Elegir nueva imagen
            new_path = None

            if ptype == 'drum':
                new_path = pick_drum_image(product.name)

            elif ptype == 'toner_bn':
                new_path = pick_toner_bn_image(product.name, toner_pool_idx)
                toner_pool_idx += 1

            elif ptype == 'toner_color':
                # Solo corregir si el archivo esta roto o la imagen es de tipo incorrecto
                if not file_exists:
                    new_path = MPC_BLACK_POOL[mpc_pool_idx % len(MPC_BLACK_POOL)]
                    mpc_pool_idx += 1
                elif not type_ok:
                    new_path = MPC_BLACK_POOL[mpc_pool_idx % len(MPC_BLACK_POOL)]
                    mpc_pool_idx += 1

            elif ptype == 'fuser':
                if not type_ok:
                    new_path = FUSER_IMAGE

            elif ptype == 'ink':
                if yellow_ink_mismatch:
                    new_path = INK_YELLOW
                elif not type_ok:
                    new_path = INK_BLACK

            # Si no encontramos reemplazo, reportar pero no tocar
            if new_path is None:
                self.stdout.write(
                    f'  ?? [{product.pk:4}] {ptype:<12} {" + ".join(reasons)}\n'
                    f'       {basename}\n'
                    f'       (sin imagen de reemplazo disponible)\n'
                    f'       {product.name[:70]}\n'
                )
                ok += 1
                continue

            self.stdout.write(
                f'  FIX [{product.pk:4}] {ptype:<12} {" + ".join(reasons)}\n'
                f'       {basename}\n'
                f'    -> {os.path.basename(new_path)}\n'
                f'       {product.name[:70]}\n'
            )

            if not dry_run:
                Consumable.objects.filter(pk=product.pk).update(main_image=new_path)
            fixed += 1

        self.stdout.write(
            f'\n=== Resultado ===\n'
            f'  Corregidos    : {fixed}\n'
            f'    (rotos)     : {broken_count}\n'
            f'    (incoherentes/color): {incoherent_count}\n'
            f'  Sin cambios   : {ok}\n'
        )
        if dry_run:
            self.stdout.write('Ejecuta sin --dry-run para aplicar los cambios.\n')
