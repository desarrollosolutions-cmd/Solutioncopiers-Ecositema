# 🎯 Guía Paso a Paso — Correr Solution Copiers en VS Code

Esta guía te lleva de cero a ver el sitio funcionando en tu navegador en aproximadamente **15-20 minutos**.

---

## 📋 PASO 0 — Verificar requisitos previos

Abre una terminal (cmd, PowerShell, bash) y ejecuta:

```bash
python3 --version    # Debe decir 3.11 o superior
node --version       # Debe decir v18 o superior
npm --version
psql --version       # Debe decir 14 o superior
git --version
```

### Si te falta algo:

**Python 3.11+:**
- Windows/Mac: Descarga de https://www.python.org/downloads/
- Linux Ubuntu: `sudo apt install python3.11 python3.11-venv python3-pip`

**Node.js 18+:**
- Todos los sistemas: https://nodejs.org/ (descargar LTS)

**PostgreSQL 14+:**
- Windows: https://www.postgresql.org/download/windows/
- Mac: `brew install postgresql@16`
- Linux: `sudo apt install postgresql postgresql-contrib libpq-dev`

**VS Code:**
- https://code.visualstudio.com/

---

## 📋 PASO 1 — Descomprimir el proyecto

1. **Descomprime el archivo `solution-copiers.zip`** en una ubicación de tu elección.
   - Recomendado: `C:\proyectos\solution-copiers` (Windows) o `~/proyectos/solution-copiers` (Mac/Linux).

2. **Abre VS Code.**

3. En VS Code: **File → Open Folder** → selecciona la carpeta `solution-copiers` descomprimida.

4. Verás esta estructura en el panel izquierdo:
   ```
   solution-copiers/
   ├── apps/
   ├── solution_copiers/
   ├── templates/
   ├── static/
   ├── requirements/
   ├── manage.py
   ├── package.json
   ├── .env.example
   └── README.md
   ```

---

## 📋 PASO 2 — Instalar extensiones recomendadas de VS Code

Cuando abras el proyecto, VS Code te sugerirá instalar extensiones recomendadas (esquina inferior derecha). Acepta. Si no aparece, instala manualmente desde el ícono de extensiones (lado izquierdo):

| Extensión | ID | Para qué |
|---|---|---|
| Python | ms-python.python | Soporte Python |
| Pylance | ms-python.vscode-pylance | Autocompletado |
| Django | batisteo.vscode-django | Templates Django |
| Tailwind CSS IntelliSense | bradlc.vscode-tailwindcss | Clases Tailwind |
| Alpine.js IntelliSense | adrianwilczynski.alpine-js-intellisense | Directivas Alpine |
| EditorConfig | EditorConfig.EditorConfig | Consistencia |

---

## 📋 PASO 3 — Abrir terminal integrada de VS Code

**Atajos para abrir terminal:**
- Windows/Linux: `Ctrl + Ñ` o `Ctrl + ` (backtick)
- Mac: `Cmd + Ñ` o `Cmd + ` (backtick)

O desde el menú: **Terminal → New Terminal**

Verifica que estás en la carpeta correcta:

```bash
pwd
# Debe mostrar la ruta completa terminada en /solution-copiers
```

---

## 📋 PASO 4 — Crear y activar entorno virtual de Python

En la terminal de VS Code:

### Linux / Mac:
```bash
# Crear entorno virtual
python3.11 -m venv venv

# Activar
source venv/bin/activate
```

### Windows PowerShell:
```powershell
# Crear entorno virtual
python -m venv venv

# Si te da error de ejecución, ejecuta primero:
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# Activar
.\venv\Scripts\Activate.ps1
```

### Windows CMD:
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**Verificación:** El prompt debe ahora mostrar `(venv)` al inicio:
```
(venv) usuario@maquina:~/solution-copiers$
```

**VS Code detectará automáticamente el venv.** Si te pregunta "Select interpreter", elige el de `./venv/bin/python` o `.\venv\Scripts\python.exe`.

---

## 📋 PASO 5 — Instalar dependencias

### 5.1 Dependencias Python

```bash
# Asegúrate de que el venv está activo (debe verse (venv) en el prompt)
pip install --upgrade pip
pip install -r requirements/development.txt
```

⏳ Esto tomará 2-3 minutos. Verás muchas líneas de instalación.

**Verificación:**
```bash
python -m django --version
# Debe mostrar: 5.1.4
```

### 5.2 Dependencias Node.js

```bash
npm install
```

⏳ Esto tomará 1-2 minutos.

**Verificación:** Aparece carpeta `node_modules/` en el proyecto.

---

## 📋 PASO 6 — Configurar PostgreSQL

### 6.1 Crear base de datos y usuario

Abre una **NUEVA terminal** (mantén la anterior abierta) y ejecuta:

**Linux/Mac:**
```bash
sudo -u postgres psql
# O en Mac: psql postgres
```

**Windows:** Abre "SQL Shell (psql)" del menú inicio y conecta con usuario `postgres`.

Dentro del prompt de psql (`postgres=#`), ejecuta:

```sql
CREATE USER solution_user WITH PASSWORD 'solution_dev_2026';
CREATE DATABASE solution_copiers_db OWNER solution_user;
GRANT ALL PRIVILEGES ON DATABASE solution_copiers_db TO solution_user;
ALTER DATABASE solution_copiers_db OWNER TO solution_user;
\c solution_copiers_db
GRANT ALL ON SCHEMA public TO solution_user;
\q
```

### 6.2 Verificar conexión

```bash
psql -U solution_user -d solution_copiers_db -h localhost
# Te pedirá la contraseña: solution_dev_2026
# Si entra al prompt postgres=#, está OK. Sal con \q
```

---

## 📋 PASO 7 — Crear archivo .env

Vuelve a la terminal de VS Code (donde tienes el venv activo).

```bash
# Copiar plantilla
cp .env.example .env
```

**En Windows si `cp` no funciona:**
```powershell
Copy-Item .env.example .env
```

**Edita el archivo `.env`** en VS Code (click en el archivo en el panel izquierdo) y asegúrate de que contenga:

```bash
# Django
DJANGO_SETTINGS_MODULE=solution_copiers.settings.development
DJANGO_SECRET_KEY=django-insecure-dev-key-cambiar-en-produccion-1234567890abcdef
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Base de datos (mismo password que usaste en PASO 6)
DATABASE_URL=postgres://solution_user:solution_dev_2026@localhost:5432/solution_copiers_db

# Email (en desarrollo va a consola)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=Solution Copiers <no-reply@solutioncopiers.com>
LEADS_NOTIFICATION_EMAIL=ventas@solutioncopiers.com

# SEO
SITE_DOMAIN=localhost:8000
SITE_NAME=Solution Copiers
SITE_PROTOCOL=http
```

**Genera una SECRET_KEY mejor (opcional pero recomendado):**

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copia el resultado y reemplaza el valor de `DJANGO_SECRET_KEY` en `.env`.

---

## 📋 PASO 8 — Aplicar migraciones y crear datos

En la terminal de VS Code (con venv activo):

```bash
# Generar migraciones
python manage.py makemigrations

# Aplicarlas a PostgreSQL
python manage.py migrate
```

⏳ Toma unos 10-20 segundos. Verás muchas líneas tipo `Applying ...`.

### Crear superusuario (admin):

```bash
python manage.py createsuperuser
```

Te pedirá:
- **Username:** admin (o el que prefieras)
- **Email:** tu-email@ejemplo.com
- **Password:** mínimo 10 caracteres (no muy simple)

### Poblar la BD con datos demo:

```bash
python manage.py seed_demo_data
```

⏳ Verás la salida:
```
🌱 Poblando base de datos...
  ✓ Configuración del sitio
  ✓ 3 categorías de fotocopiadoras
  ✓ 5 fotocopiadoras Ricoh
  ✓ 3 consumibles
  ✓ 3 servicios de cableado
  ✓ 16 tecnologías
  ✓ 2 servicios de software
  ✓ 2 servicios web
  ✓ 1 servicios móviles
  ✓ 1 servicios de bases de datos
  ✓ 2 casos de éxito
  ✓ 3 testimoniales
✅ Seeding completado con éxito!
```

---

## 📋 PASO 9 — Levantar los servidores

Necesitas **DOS procesos corriendo simultáneamente**:
- **Proceso 1:** Compilador de CSS/JS (npm)
- **Proceso 2:** Servidor Django

### Terminal 1: Compilar frontend

En la terminal actual de VS Code:

```bash
npm run dev
```

⏳ Verás:
```
> dev:css → compilando Tailwind...
> dev:js  → 👀 esbuild watching for changes...
```

**Déjala corriendo.**

### Terminal 2: Servidor Django

Abre una **NUEVA terminal** en VS Code (`Ctrl + Shift + Ñ` o icono `+` en panel terminal):

**Importante:** Activa el venv en esta nueva terminal también:

```bash
# Linux/Mac
source venv/bin/activate

# Windows PowerShell
.\venv\Scripts\Activate.ps1
```

Luego:

```bash
python manage.py runserver
```

✅ Verás:
```
Watching for file changes with StatReloader
Performing system checks...

System check identified no issues (0 silenced).
Django version 5.1.4, using settings 'solution_copiers.settings.development'
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```

---

## 📋 PASO 10 — ¡Ver el sitio en el navegador!

Abre tu navegador favorito y ve a:

### 🏠 Home con Bento Grid
**http://127.0.0.1:8000/**

Deberías ver:
- Hero animado con letras apareciendo
- Bento Grid asimétrico con servicios
- Paleta de colores rojo/vinotinto corporativa
- Navbar que cambia a glassmorphism al hacer scroll

### 🛒 Catálogo de fotocopiadoras
**http://127.0.0.1:8000/alquiler-fotocopiadoras-medellin/**

Verás las 5 fotocopiadoras Ricoh del seed con filtros.

### 💻 Servicios de software
**http://127.0.0.1:8000/desarrollo-software-medellin/**

Pilar SEO del Silo 2 con servicios de software.

### 📝 Cotizador (joya del proyecto)
**http://127.0.0.1:8000/cotizador/**

Prueba el wizard:
1. Selecciona "Alquiler de fotocopiadoras"
2. Ajusta cantidad y páginas (verás el cálculo en vivo en el sidebar)
3. Completa contacto
4. Envía → redirige a página de gracias
5. Revisa la consola del servidor Django: verás el email de notificación

### 🔐 Admin
**http://127.0.0.1:8000/panel-admin-sc/**

Login con el superuser que creaste. Podrás:
- Editar Design Tokens (colores, fuentes) y verlos cambiar en vivo
- Ver todos los Leads y Cotizaciones recibidos
- Gestionar fotocopiadoras, servicios, blog

### 🗺️ Sitemap
**http://127.0.0.1:8000/sitemap.xml**

Lista todas las URLs indexables.

### 🤖 Robots
**http://127.0.0.1:8000/robots.txt**

Reglas para crawlers.

---

## 🧪 PASO 11 — Correr tests (opcional pero recomendado)

Abre **una tercera terminal** en VS Code, activa venv y ejecuta:

```bash
pytest
```

Deberías ver algo así:
```
======================= test session starts ========================
collected 47 items

tests/test_core/test_mixins.py ............              [ 25%]
tests/test_catalog/test_filters.py ........              [ 42%]
tests/test_catalog/test_views.py .......                 [ 57%]
tests/test_leads/test_services.py .......                [ 72%]
tests/test_leads/test_wizard_flow.py .......             [ 87%]
tests/test_seo/test_sitemaps.py ....                     [ 95%]
tests/test_security/test_headers_and_csrf.py ...        [100%]

======================= 47 passed in 8.42s ========================
```

QA check rápido:
```bash
python manage.py qa_check
```

---

## ⚠️ TROUBLESHOOTING — Problemas comunes

### ❌ Error: "No module named 'django'"

**Causa:** El venv no está activo.

**Solución:**
```bash
# Verificar que (venv) aparece en el prompt
# Si no:
source venv/bin/activate    # Linux/Mac
.\venv\Scripts\Activate.ps1 # Windows
```

### ❌ Error: "could not connect to server: Connection refused"

**Causa:** PostgreSQL no está corriendo.

**Solución:**
```bash
# Linux
sudo systemctl start postgresql

# Mac
brew services start postgresql@16

# Windows: Buscar "Services" en menú inicio → buscar postgresql → Start
```

### ❌ Error: "psql: FATAL: password authentication failed"

**Causa:** Password incorrecto en `.env`.

**Solución:** Verifica que el password en `DATABASE_URL` del `.env` coincida con el que pusiste al crear `solution_user`.

### ❌ El sitio carga pero sin estilos

**Causa:** `npm run dev` no está corriendo o no ha terminado de compilar.

**Solución:**
1. Verifica que la Terminal 1 muestra "esbuild watching".
2. Si no, ejecuta `npm run dev` y espera 10 segundos.
3. Refresca el navegador con `Ctrl+F5` (recarga forzada).

### ❌ Error: "Port 8000 is already in use"

**Causa:** Otro proceso Django ya está corriendo.

**Solución:**
```bash
# Opción 1: Usar otro puerto
python manage.py runserver 8001
# Luego abre http://127.0.0.1:8001/

# Opción 2: Matar el proceso anterior
# Linux/Mac:
lsof -ti:8000 | xargs kill -9
# Windows:
netstat -ano | findstr :8000
taskkill /PID <numero> /F
```

### ❌ Error: "ModuleNotFoundError: No module named 'apps.core'"

**Causa:** Falta `__init__.py` en `apps/` o estás corriendo desde directorio equivocado.

**Solución:**
```bash
# Verifica que estás en el directorio raíz
pwd
# Debe terminar en /solution-copiers

# Verifica que existe apps/__init__.py
ls apps/__init__.py
# Si no existe:
touch apps/__init__.py    # Linux/Mac
echo. > apps\__init__.py  # Windows
```

### ❌ Tailwind no aplica clases

**Causa:** El bundle no se compiló o el path está mal.

**Solución:**
```bash
# Compilar manualmente
npm run build

# Verificar que existe el archivo compilado
ls static/dist/css/main.css
# Si existe, refresca el navegador con Ctrl+F5
```

### ❌ Animaciones GSAP no funcionan

**Causa:** Bundle JS no compilado.

**Solución:**
```bash
# En terminal donde corre npm run dev:
# Verifica que dice "✅ esbuild build complete"

# Si no:
npm run build
# Refrescar navegador con Ctrl+F5
```

### ❌ Error al ejecutar seed_demo_data: "no such table"

**Causa:** Migraciones no aplicadas.

**Solución:**
```bash
python manage.py migrate
python manage.py seed_demo_data
```

---

## 🎯 Workflow diario después del setup

Una vez configurado, tu rutina diaria es:

```bash
# Abrir VS Code en el proyecto
code .

# Terminal 1: activar venv y compilar assets
source venv/bin/activate   # Linux/Mac
.\venv\Scripts\Activate.ps1 # Windows
npm run dev

# Terminal 2: activar venv y correr servidor
source venv/bin/activate
python manage.py runserver

# Abrir http://127.0.0.1:8000/ en navegador
```

Para detener todo: `Ctrl + C` en cada terminal.

---

## 📚 Comandos útiles de referencia

```bash
# Aplicar nuevas migraciones
python manage.py makemigrations
python manage.py migrate

# Crear superusuario nuevo
python manage.py createsuperuser

# Resetear BD completamente (cuidado, borra todo)
python manage.py flush
python manage.py seed_demo_data

# Shell Django con todos los modelos cargados
python manage.py shell_plus

# Listar todas las URLs
python manage.py show_urls

# Compilar assets para producción (minificado)
npm run build

# Recolectar estáticos (para producción)
python manage.py collectstatic --noinput

# QA antes de cambios importantes
python manage.py qa_check
pytest
```

---

## ✅ Checklist final

Marca cada paso completado:

- [ ] Python 3.11+, Node 18+, PostgreSQL 14+ instalados
- [ ] VS Code abierto en la carpeta `solution-copiers`
- [ ] Entorno virtual creado y activo
- [ ] Dependencias Python instaladas
- [ ] Dependencias Node instaladas
- [ ] Base de datos PostgreSQL creada
- [ ] Archivo `.env` creado y configurado
- [ ] Migraciones aplicadas
- [ ] Superusuario creado
- [ ] Datos demo cargados
- [ ] `npm run dev` corriendo en Terminal 1
- [ ] `python manage.py runserver` corriendo en Terminal 2
- [ ] Sitio visible en http://127.0.0.1:8000/

🎉 **¡Listo!** Ya tienes el proyecto corriendo localmente.

---

## 🚀 Siguiente paso

Cuando todo funcione localmente, cuando estés listo, podemos avanzar al **deploy en Render.com + Supabase** siguiendo el plan de la Fase 8.

¿Dudas? Revisa el README.md o consulta los `docs/qa/`.
