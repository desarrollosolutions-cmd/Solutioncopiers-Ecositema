#!/usr/bin/env bash
# Script de build para despliegue en Render.com
# Se ejecuta automáticamente en cada deploy según render.yaml.
set -o errexit  # detiene el build ante el primer error

echo "==> Instalando dependencias Python..."
pip install -r requirements/production.txt

echo "==> Instalando dependencias Node..."
npm install

echo "==> Compilando assets (Tailwind CSS + esbuild)..."
npm run build

echo "==> Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

echo "==> Aplicando migraciones de base de datos..."
python manage.py migrate --noinput

echo "==> Build completado."
