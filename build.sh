#!/usr/bin/env bash
# Script de build para despliegue en Render.com
# Se ejecuta automáticamente en cada deploy según render.yaml.
set -o errexit  # detiene el build ante el primer error

echo "==> Instalando dependencias Python..."
python -m pip install -r requirements.txt

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
