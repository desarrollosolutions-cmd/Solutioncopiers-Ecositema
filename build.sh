#!/usr/bin/env bash
# Script de build para despliegue en Render.com
# Se ejecuta automáticamente en cada deploy según render.yaml.
set -o errexit  # detiene el build ante el primer error

echo "==> Instalando dependencias Python..."
python -m pip install -r requirements.txt

echo "==> Ejecutando migraciones de base de datos..."
python manage.py migrate --no-input

echo "==> Cargando datos iniciales si la base de datos está vacía..."
python manage.py shell -c "
from apps.catalog.models import Copier
if not Copier.objects.exists():
    from django.core.management import call_command
    call_command('loaddata', 'fixtures/sqlite_full_export.json')
    print('Fixture cargado.')
else:
    print('Base de datos ya tiene datos, omitiendo loaddata.')
"

echo "==> Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

echo "==> Copiando media a staticfiles para WhiteNoise..."
if [ -d "media" ]; then
  cp -r media/. staticfiles/media/
  echo "   media/ copiado a staticfiles/media/"
else
  echo "   Sin directorio media/, omitiendo."
fi

echo "==> Build completado."
