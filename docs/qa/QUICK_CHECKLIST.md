# ⚡ Quick QA Checklist — Solution Copiers

> Versión resumida. Ejecutar antes de cada push importante.

## 🟢 1. AUTOMATIZADO (1 minuto)
- [ ] `pytest` → todo verde
- [ ] `python manage.py qa_check` → todo verde
- [ ] `python manage.py check --deploy` → sin warnings críticos

## 🟡 2. VISUAL (3 minutos)
- [ ] Home carga sin errores en consola
- [ ] Navbar cambia a glassmorphism al scroll
- [ ] Bento grid responsive (mobile + desktop)
- [ ] Footer con todos los enlaces

## 🟠 3. COTIZADOR (2 minutos)
- [ ] Wizard completa los 3 pasos
- [ ] Cálculo en vivo actualiza
- [ ] Submit crea Lead en admin
- [ ] Email llega a consola

## 🔴 4. SEO (1 minuto)
- [ ] `/sitemap.xml` responde
- [ ] `/robots.txt` correcto
- [ ] Home muestra meta title y description

## 🟣 5. SEGURIDAD (30 segundos)
- [ ] `DEBUG=False` antes de deploy
- [ ] `.env` no está en git
- [ ] `SECRET_KEY` no es la default

**Total: 8 minutos**. Si todo verde → deploy.
