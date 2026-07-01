# 🚀 Solution Copiers — Integrador Tecnológico B2B

Plataforma web para Solution Copiers (Medellín, Colombia). Combina dos líneas de negocio en una sola identidad:
- **Hardware:** Alquiler/venta de fotocopiadoras Ricoh, consumibles, cableado estructurado.
- **Software:** Desarrollo a la medida, diseño web, apps móviles, bases de datos.

## 🛠️ Stack Técnico

- **Backend:** Django 5.x + Python 3.11+
- **Base de datos:** PostgreSQL 14+
- **Frontend:** Tailwind CSS + Alpine.js + GSAP
- **Build:** esbuild + PostCSS
- **Testing:** pytest + factory_boy

## 📋 Requisitos previos

Antes de empezar, asegúrate de tener instalado:

| Software | Versión | Comando para verificar |
|---|---|---|
| Python | 3.11+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| PostgreSQL | 14+ | `psql --version` |
| Git | 2.30+ | `git --version` |
| VS Code | reciente | descargar de code.visualstudio.com |

## ⚡ Inicio rápido (8 pasos)

Ver `INSTRUCCIONES_VSCODE.md` para la guía detallada paso a paso.

### Resumen express:

```bash
# 1. Entrar al proyecto en terminal de VS Code
cd solution-copiers

# 2. Crear entorno virtual
python3.11 -m venv venv

# 3. Activar venv
# Linux/Mac:
source venv/bin/activate
# Windows:
.\venv\Scripts\Activate.ps1

# 4. Instalar dependencias Python
pip install -r requirements/development.txt

# 5. Instalar dependencias Node
npm install

# 6. Crear archivo .env (copiar de .env.example y rellenar)
cp .env.example .env

# 7. Crear BD PostgreSQL y aplicar migraciones
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo_data

# 8. Levantar 2 procesos (en terminales separadas):
# Terminal 1: compilar CSS y JS
npm run dev

# Terminal 2: servidor Django
python manage.py runserver
```

Abrir en navegador: **http://127.0.0.1:8000/**

## 📂 Estructura del proyecto

```
solution-copiers/
├── apps/                    # Aplicaciones modulares
│   ├── core/                # Home, configuración global, mixins
│   ├── catalog/             # Silo 1: hardware (fotocopiadoras, cableado)
│   ├── services/            # Silo 2: software (web, apps, BD)
│   ├── leads/               # Cotizador y captura de leads
│   ├── blog/                # Sistema de blog
│   └── seo/                 # Sitemaps, robots, design tokens
├── solution_copiers/        # Configuración del proyecto Django
│   └── settings/            # base, development, production
├── templates/               # Templates HTML globales
├── static/src/              # Assets fuente (CSS, JS)
├── static/dist/             # Assets compilados (gitignored)
├── tests/                   # Suite de tests pytest
├── requirements/            # Dependencias Python por entorno
├── docs/qa/                 # Documentación QA
├── manage.py
├── package.json             # Dependencias Node
├── tailwind.config.js
├── esbuild.config.mjs
└── .env.example
```

## 🧪 Tests

```bash
# Suite completa
pytest

# Con coverage
pytest --cov=apps

# Solo tests rápidos
pytest -m unit

# QA check antes de deploy
python manage.py qa_check
```

## 📚 Documentación

- `INSTRUCCIONES_VSCODE.md` — Guía paso a paso para correr el proyecto
- `docs/FUNCIONALIDAD.md` — Documentación completa de funcionalidad y comportamiento del sistema
- `docs/qa/QUICK_CHECKLIST.md` — Checklist de QA pre-deploy
- `docs/qa/MANUAL_CHECKLIST.md` — Checklist exhaustivo

## 🌐 URLs principales

| Ruta | Descripción |
|---|---|
| `/` | Home con Bento Grid |
| `/alquiler-fotocopiadoras-medellin/` | Pilar SEO Silo 1 |
| `/desarrollo-software-medellin/` | Pilar SEO Silo 2 |
| `/cotizador/` | Wizard interactivo |
| `/panel-admin-sc/` | Admin Django |
| `/sitemap.xml` | Sitemap dinámico |
| `/robots.txt` | Robots dinámico |

## 🚀 Despliegue a producción (Render.com + Supabase)

El proyecto incluye `render.yaml` (Blueprint) y `build.sh` listos para desplegar.

1. En el dashboard de Render: **New +** → **Blueprint** → conectar este repositorio. Render lee `render.yaml` automáticamente.
2. `build.sh` instala dependencias, compila CSS/JS (`npm run build`), ejecuta `collectstatic` y `migrate` en cada deploy.
3. **Pegar manualmente** en Render → Environment las variables marcadas `sync: false` en `render.yaml` (ver `.env.example` para la lista completa con su propósito). Como mínimo:
   - `DJANGO_SECRET_KEY` — generar uno nuevo, NUNCA reusar el de desarrollo
   - `ALLOWED_HOSTS` — dominio real (ej. `solutioncopiers.com`)
   - `DATABASE_URL` — cadena de conexión de Supabase (Postgres, con `sslmode=require`)
   - `WOMPI_PUBLIC_KEY` / `WOMPI_PRIVATE_KEY` / `WOMPI_INTEGRITY_KEY` / `WOMPI_EVENTS_KEY` — claves reales de producción (no las de sandbox)
   - `GROQ_API_KEY` y/o `ANTHROPIC_API_KEY` — para que funcionen los asistentes IA
   - `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` — SMTP real para envío de notificaciones

⚠️ **Pendiente antes del primer deploy real**: el almacenamiento de `media/` (imágenes de productos, blog, comprobantes) usa disco local — en Render esto es efímero y se pierde en cada redeploy. Hay que migrarlo a un storage tipo S3 (Supabase Storage es la opción más natural dado el stack) antes de subir contenido real. Ver `docs/FUNCIONALIDAD.md` sección 12 para más detalle.

## 📞 Soporte

Si encuentras problemas, consulta `INSTRUCCIONES_VSCODE.md` sección de troubleshooting.
