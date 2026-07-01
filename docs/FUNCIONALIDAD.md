# Documentación de Funcionalidad — Solution Copiers

> Documento vivo. Describe el comportamiento y la funcionalidad del sistema tal como existen al **30 de junio de 2026**. Actualizar cada vez que se agregue o cambie una funcionalidad relevante.

---

## 1. Visión general del negocio

**Solution Copiers** es un integrador tecnológico B2B con sede en Medellín, Colombia, que combina dos líneas de negocio bajo una misma marca:

- **Hardware**: alquiler y venta de fotocopiadoras/multifuncionales (Ricoh, Kyocera, Canon, HP, etc.), venta de consumibles e insumos, servicio técnico, cableado estructurado Cat6/6A.
- **Software**: desarrollo de software a la medida, diseño web, apps móviles, diseño de bases de datos.

El proyecto es una plataforma Django monolítica que cubre tres frentes:
1. **Sitio público** — captación de leads, catálogo, cotizador, blog, checkout de consumibles.
2. **CRM / ERP interno** — tres portales con autenticación separada según el rol del usuario.
3. **Automatizaciones de negocio** — scoring de leads, renovación de contratos, notificaciones, encuestas de satisfacción.

---

## 2. Arquitectura técnica

| Capa | Tecnología |
|---|---|
| Backend | Django 5.1 + Python 3.12 |
| Base de datos | PostgreSQL (SQLite en desarrollo local) |
| Frontend | Tailwind CSS + Alpine.js + GSAP, HTML servido por Django Templates |
| Build de assets | esbuild + PostCSS |
| Imágenes | django-imagekit (auto-compresión a WebP, specs: thumbnail/card/hero) |
| Pagos | Wompi (pasarela colombiana) — checkout link + webhook firmado |
| IA | Groq (Llama 3.3 70B, gratis) con fallback a Anthropic Claude |
| WhatsApp | CallMeBot API (notificaciones 1-a-1) |
| Estáticos en prod | WhiteNoise |
| Errores en prod | Sentry |
| Hosting objetivo | Render.com + Supabase (Postgres) |

### Apps Django (`apps/`)

| App | Responsabilidad |
|---|---|
| `core` | Home, modelos base abstractos (SEO, slugs, publicación), SiteSettings, Testimonial, mixins compartidos, asistente IA público |
| `catalog` | Catálogo de fotocopiadoras, consumibles y cableado estructurado (Silo 1: Hardware) |
| `services` | Catálogo de servicios de software/web/móvil/BD (Silo 2: Software) |
| `leads` | CRM completo: Lead, Quote, RentalContract, ServiceTicket, scoring, automatizaciones |
| `blog` | Sistema de contenidos para SEO |
| `seo` | Sitemaps, robots.txt, redirecciones dinámicas, Design Tokens |
| `encuestas` | Encuestas de satisfacción post-servicio |
| `dashboard` | Los tres portales internos (`/dashadmin/`, `/panel/`, `/campo/`), permisos, asistentes IA internos |
| `payments` | Checkout público, Orders, Invoices DIAN, integración Wompi, contabilidad Colombia |

---

## 3. Sitio público

### 3.1 Home (`/`)
Bento Grid con: copiadoras destacadas, consumibles aleatorios (8 de un pool de 80 con imagen), servicios de cableado/software/web/móvil/BD destacados, casos de éxito, testimonios, tecnologías (stack), últimos posts del blog. JSON-LD `@graph` completo (LocalBusiness + Corporation + WebSite + WebPage).

### 3.2 Catálogo — Hardware (`apps/catalog`)
- **Alquiler** (`/alquiler-fotocopiadoras-medellin/`) y **Venta** (`/venta-fotocopiadoras-medellin/`): listados paginados (12/página) con filtros por categoría, tipo de tóner, tamaño de papel, rango de precio y velocidad; búsqueda por texto. Caché HTTP 15 min.
- **Detalle de equipo** (`.../modelo/{slug}/`): ficha técnica completa, galería de imágenes, datasheet PDF, equipos relacionados, JSON-LD Product. Caché 10 min.
- **Consumibles** (`/consumibles-toner-ricoh/`): catálogo de tóner/repuestos con 3 niveles de precio (público, empresa, mayorista), filtrable por tipo, con modelos de copiadora compatibles (M2M).
- **Cableado estructurado** (`/cableado-estructurado-medellin/`): listado y detalle de servicios de red, con `requires_quote` para servicios que no tienen precio fijo.
- **Búsqueda global** (`/buscar/?q=...`): API AJAX que retorna top 6 consumibles + top 4 copiadoras.
- **Servicio técnico** (`/servicio-tecnico-fotocopiadoras/`): página estática informativa con JSON-LD Service.

Modelos clave: `Copier` (specs técnicas + precio renta/venta), `CopierCategory`, `CopierImage`, `Consumable` (precios escalonados, stock), `CopierUnit` (inventario físico por serial, contador de páginas), `StockMovement` (auditoría de entradas/salidas), `CablingService`.

### 3.3 Servicios — Software (`apps/services`)
Cuatro silos de servicio (`SoftwareService`, `WebService`, `MobileService`, `DatabaseService`) compartiendo una base abstracta (`DigitalServiceBase`) con: tagline, beneficios, entregables, duración estimada, precio inicial, stack tecnológico (M2M a `Technology`). Cada uno tiene listado + detalle con JSON-LD Service y casos de éxito (`CaseStudy`) relacionados.

URLs: `/desarrollo-software-medellin/`, `/diseno-paginas-web-medellin/`, `/desarrollo-aplicaciones-moviles/`, `/bases-de-datos-empresariales/` (+ detalle por slug en cada una).

### 3.4 Cotizador / Wizard (`apps/leads`)
Flujo de 3 pasos guardado en sesión (`quote_wizard_data`):
1. **Área de interés**: rental, sale, consumables, cabling, software, web, mobile, database, full_office.
2. **Detalles específicos** según el área (formulario distinto por tipo).
3. **Datos de contacto**.

Al enviar (`QuoteSubmitView`), se crea `Lead` + `Quote` + `QuoteItem` en una transacción atómica (`LeadCreator`), se dispara notificación por email al equipo de ventas y un mensaje de WhatsApp automático (CallMeBot) — ambos en threads separados para no bloquear la respuesta. Redirige a página de agradecimiento.

`QuoteCalculator` calcula estimaciones en vivo:
- **Renta**: precio mensual del equipo × cantidad + (páginas de exceso × tarifa de exceso).
- **Cableado**: $180.000 COP/punto lógico + $220.000 COP/punto eléctrico.
- **Software**: rangos fijos (bajo $8M, medio $25M, alto $60M, enterprise $150M COP).

### 3.5 Checkout público de consumibles (`apps/payments`)
- **Carrito** (`/pago/carrito/`): sesión de Django (`sc_cart`), agregar/actualizar/quitar ítems vía AJAX.
- **Checkout** (`/pago/checkout/`): formulario de datos del comprador → crea `Order` + `OrderItem`s, vincula o crea `Lead` automáticamente por email, crea `Payment` pendiente, redirige a Wompi.
- **Confirmación** (`/pago/confirmacion/<reference>/`): Wompi redirige aquí tras el pago; si sigue pendiente, consulta el estado vía API de Wompi.
- **Webhook** (`/pago/webhook/wompi/`): recibe eventos `transaction.updated` con firma HMAC-SHA256 verificada (`verify_webhook_signature`). Si el pago se aprueba, actualiza `Order`/`Payment` y **genera automáticamente una factura DIAN en borrador** (`_auto_generate_invoice`).

### 3.6 Blog (`apps/blog`)
Listado paginado (9/página) con búsqueda y tags populares, filtrado por categoría/tag, detalle de post con JSON-LD Article y posts relacionados.

### 3.7 Encuestas de satisfacción (`apps/encuestas`)
Formulario público (`/encuesta/`) con calificación 1-5 en cuatro dimensiones (atención, servicio técnico, tiempo de respuesta, precio/calidad) + recomendación + comentarios. Se dispara automáticamente al cerrar un `ServiceTicket` (signal `on_ticket_resolved`). Panel de estadísticas solo para staff (`/encuesta/panel/`) con promedios, % de recomendación y desglose por tipo de servicio.

### 3.8 Asistente virtual público
Widget de chat sin autenticación (`/asistente/chat/`), límite de 30 mensajes por sesión, usa el mismo motor IA (`_call_ai`) que los asistentes internos pero con un system prompt orientado a atención al cliente y captación.

### 3.9 Legales
`/terminos-y-condiciones/` y `/politica-de-privacidad/` — 15 cláusulas cubriendo uso del sitio, contratos de arrendamiento, venta de consumibles, servicio técnico, pagos vía Wompi, protección de datos (Ley 1581/2012), jurisdicción Medellín/Colombia.

### 3.10 SEO e infraestructura técnica (`apps/seo`)
- **12 sitemaps XML** automáticos (estáticas, copiadoras, categorías, consumibles, cableado, 4 tipos de servicio de software, case studies, blog posts, categorías de blog).
- **`robots.txt` dinámico**, cacheado 24h, con disallow a rutas administrativas y APIs internas.
- **Redirecciones dinámicas** (`RedirectRule` + `DynamicRedirectMiddleware`): intercepta 404s, redirige 301/302 según reglas configuradas en BD, cuenta hits.
- **Design Tokens** (`DesignTokens`, modelo singleton editable desde admin): paleta de color corporativa (rojo `#C4121A` primario, dorado `#C47A0A` acento), tipografías (Fraunces display, Inter body, JetBrains mono), spacing, glassmorphism, sombras y flags de animación. Se inyectan como variables CSS (`:root`) vía context processor en cada página.
- **JSON-LD automático** en +100 páginas vía `JsonLDMixin` + `BreadcrumbMixin`. La serialización usa `_safe_json_script()` que escapa `</` y `<!--` para prevenir XSS al embeber JSON dentro de `<script>`.

---

## 4. Sistema CRM — modelos de negocio (`apps/leads`)

| Modelo | Propósito | Campos / lógica clave |
|---|---|---|
| `Lead` | Cliente potencial o existente | `score` (0-100, recalculado por comando), `source`, `company_size`, `nit`, `notes_internal` |
| `LeadActivity` | Bitácora de interacciones | tipos: llamada, email, reunión, nota, WhatsApp, visita |
| `FollowUpTask` | Recordatorio con fecha límite | `assigned_to`, `is_done`, `due_date` — usado también por mensajeros en `/panel/turno/` |
| `Quote` | Cotización | pipeline de 6 estados (nueva→revisión→enviada→negociación→ganada/perdida), `lost_category`, `close_probability` |
| `RentalContract` | Contrato de alquiler activo | `monthly_rate`, `copies_included`, `copy_overage_rate`, propiedades `is_expiring_soon`/`is_overdue` |
| `ServiceTicket` | Ticket de soporte técnico | `priority`, `status` (5 estados), `assigned_to`, `scheduled_for` — corazón del flujo técnico/mensajero |
| `MeterReading` | Lectura de contador de copias | calcula `overage_pages` y `overage_charge` automáticamente |
| `QuoteItem` | Línea de cotización | Generic FK a Copier/Consumable/etc. |
| `EmailLog` | Auditoría de correos enviados | `status`, `error_msg` |

### Flujo típico de un lead
1. Cliente llena el cotizador → `Lead` + `Quote` en estado "Nueva".
2. Asesora la toma → "En revisión" → envía propuesta → "Enviada"/"Negociación".
3. Si cierra: "Ganada" → admin crea `RentalContract`.
4. Si hay problema técnico con contrato activo: asesora crea `ServiceTicket` y lo asigna a un técnico.
5. Si no cierra: "Perdida" con categoría obligatoria (precio, competencia, sin presupuesto, mal momento, sin necesidad, perdió contacto, otro).

### Automatizaciones (`apps/leads/management/commands/`)
| Comando | Qué hace |
|---|---|
| `update_lead_scores` | Recalcula el score 0-100 de cada lead: +2 por campo completo, +25 actividad ≤7d, +15 ≤30d, +15 si tiene cotización, +10 si está en negociación/ganada, +20 contrato activo, +5 ticket, +5 fuente de calidad, -10 si lleva >60d frío, -5 sin contacto |
| `contract_renewal_tasks` | Crea `FollowUpTask` + `Notification` en umbrales de 60/30/15 días antes del vencimiento de un contrato; marca como vencidos los que ya pasaron |
| `send_followup_emails` | Alertas internas de cotizaciones sin atender |
| `assign_leads_roundrobin` | Reparte leads nuevos entre asesoras |
| `check_stock_alerts` | Alertas de stock bajo de consumibles |
| `generate_notifications` | Genera notificaciones generales del CRM |

---

## 5. Portales internos — visión general

El sistema tiene **tres entradas de autenticación independientes**, cada una con su propio login y middleware de acceso:

| Portal | URL base | Quién entra | Estado |
|---|---|---|---|
| **Admin** | `/dashadmin/` | `is_staff=True` (administradores/dueños) | Activo, sin cambios recientes |
| **Panel unificado** | `/panel/` | Empleados no-staff: asesoras, técnicos, mensajeros | **Activo — entrada recomendada para todo el personal operativo** |
| **Campo (legado)** | `/campo/` | Técnicos y mensajeros (`FieldUser`) | Activo en paralelo por compatibilidad — se recomienda migrar a `/panel/` |

### 5.1 Portal Admin (`/dashadmin/`)
Acceso exclusivo `is_staff`. Secciones: Home (KPIs), Pipeline Kanban de cotizaciones, Cotizaciones, Clientes, Contratos, Tickets, Consumibles, Stock (con historial de movimientos), Fotocopiadoras, **Empleados** (crear cuentas, asignar rol y permisos), **Campo — mapa GPS en tiempo real**, Actividad (auditoría), Reportes, Notificaciones, Configuración, y **Facturación y Contabilidad** (ver sección 7).

### 5.2 Portal unificado `/panel/` — roles

Desde la unificación de portales, **un solo punto de entrada** sirve tres dashboards distintos según el perfil del usuario:

#### Rol: Asesora/Asesor (sin `FieldUser`)
Acceso completo al CRM vía permisos granulares (`PanelPermissions`): cotizaciones, clientes, actividades, tickets, contratos, insumos, facturación. **Es la única que puede crear tickets y asignarlos a un técnico.**

#### Rol: Técnico (`FieldUser.role = "tecnico"`)
- Ve **solo sus tickets asignados**. Puede cambiar estado y agregar notas de resolución.
- **No puede** crear tickets, asignarlos, cambiar prioridad ni agendar visita — esos campos no aparecen en su formulario.
- Permiso único preasignado: `panel_tickets`.
- Tiene acceso a `/panel/turno/` para iniciar/finalizar turno GPS.

#### Rol: Mensajero (`FieldUser.role = "mensajero"`)
- **Sin acceso al CRM** (cero permisos de panel). Al entrar a `/panel/` se le redirige automáticamente a `/panel/turno/`.
- Ve sus `FollowUpTask` asignadas y gestiona su turno GPS.

#### `/panel/turno/` — Mi Turno
Pantalla compartida por técnicos y mensajeros:
- **Estado GPS**: botón "Iniciar turno" / "Finalizar turno". Al iniciar, el navegador reporta ubicación + batería automáticamente cada ~2 minutos mientras el turno esté activo (`FieldUserLocation.is_on_shift=True`).
- **Mi Ruta**: lista combinada de tickets de servicio asignados (prioritarios, con fecha agendada si la tienen) y tareas de seguimiento (`FollowUpTask`), con acceso directo al detalle.

### 5.3 Portal de Campo legado (`/campo/`)
Predecesor del `/panel/turno/` unificado, sigue activo en paralelo. Su `CampoTurnoView` es más completo: combina `FollowUpTask` + `ServiceTicket` + **`DeliveryTask`** (modelo exclusivo de este portal, con foto de evidencia de entrega, número de factura/remisión y dirección — pensado para mensajeros con rutas de reparto físico de insumos). El admin también tiene aquí su propio mapa GPS y listado de tareas de entrega (`/dashadmin/campo/`).

> **Nota de arquitectura**: existen actualmente dos sistemas de "tareas de campo" en paralelo — `FollowUpTask` (genérico, del CRM, usado por `/panel/turno/`) y `DeliveryTask` (específico de reparto con evidencia fotográfica, usado por `/campo/`). Si se decide retirar `/campo/` en el futuro, hay que decidir si `DeliveryTask` se migra a `/panel/` o se descontinúa.

---

## 6. Sistema de permisos

`PanelPermissions` es un modelo sin tabla (`managed=False`) que solo registra 9 permisos personalizados de Django:

| Codename | Qué habilita |
|---|---|
| `panel_cotizaciones` | Ver, asignar y gestionar cotizaciones |
| `panel_clientes` | Ver perfiles e historial de clientes |
| `panel_actividades` | Registrar llamadas, notas y tareas |
| `panel_tickets` | Ver, crear y actualizar tickets de servicio |
| `panel_contratos` | Ver contratos de alquiler |
| `panel_insumos` | Ver catálogo de consumibles |
| `panel_reportes` | Ver estadísticas y métricas |
| `panel_exportar` | Exportar datos a CSV |
| `panel_facturacion` | Crear y gestionar facturas propias |

**Roles predefinidos** (`PANEL_ROLES`, usados como preset en el formulario de empleados):
- **Asesor Comercial**: cotizaciones + clientes + actividades + tickets + contratos + insumos + facturación.
- **Técnico**: solo `panel_tickets`.
- **Supervisor**: todos los permisos.
- **Solo lectura**: cotizaciones + clientes.

Toda asignación/edición se sincroniza vía `_sync_employee_perms(user, codenames)`, que escribe directamente sobre `user.user_permissions`.

---

## 7. Módulo de Pagos y Facturación (`apps/payments`)

### Modelos
- **`Order`** / **`OrderItem`**: pedido público del carrito de consumibles. Estados: pendiente, pagado, fallido, cancelado, reembolsado. Calcula IVA 19% automáticamente (`recalculate_totals`).
- **`Invoice`** / **`InvoiceItem`**: factura DIAN-ready. Campos para resolución DIAN, prefijo, consecutivo, CUFE, QR. Soporta retenciones colombianas: RteFuente, ReteICA (‰), ReteIVA, y calcula `net_received` (neto tras retenciones).
- **`Payment`**: transacción Wompi vinculada a `Order` o `Invoice`. Guarda `raw_payload` completo del webhook para auditoría.

### Flujo
1. Cliente compra en el carrito público → `Order` + `Payment` pendiente → redirige a Wompi.
2. Wompi procesa el pago y notifica vía **webhook firmado** (HMAC-SHA256 sobre `properties` + `timestamp` + `events_key`).
3. Si se aprueba, se actualiza el estado y se **genera automáticamente una `Invoice` en borrador**.
4. El equipo administrativo gestiona la factura desde `/dashadmin/facturacion/facturas/`.

### Vistas CRM (solo `is_staff`, protegidas por `CRMLoginMixin`)
- **AR Dashboard** (`/dashadmin/facturacion/`): resumen de facturas por estado, pedidos del mes, ingresos.
- **Facturas**: crear manual o ver generadas automáticamente.
- **Pedidos online**: estado de pago sincronizado con Wompi.
- **Contabilidad Colombia** (`/dashadmin/contabilidad/`): IVA generado/declarable por bimestre DIAN, retenciones sufridas, **libro auxiliar de ventas exportable a CSV**, reporte de IVA bimestral y de retenciones.

---

## 8. Asistentes de Inteligencia Artificial

Motor compartido `_call_ai()`: prioriza **Groq** (Llama 3.3 70B, gratis) y cae a **Anthropic Claude** si Groq no está configurado o falla. Cada asistente tiene su propio *system prompt* en español.

| Asistente | Dónde vive | Audiencia | Personalidad |
|---|---|---|---|
| Asistente público | `/asistente/chat/` (sin login) | Visitantes del sitio | Atención al cliente, captación, límite 30 msj/sesión |
| **Nexa (Admin)** | `/dashadmin/` | Administradores | Guía completa del panel admin + facturación + roles |
| **Nexa (Panel)** | `/panel/` | Asesoras, técnicos, mensajeros | **Role-aware**: el backend inyecta el rol real del usuario (`field_profile.role`) en cada petición, así Nexa sabe con certeza si habla con una asesora (coach comercial + guía), un técnico (solo tickets propios + turno) o un mensajero (solo tareas + turno), sin necesidad de adivinar |

Nexa (Panel) conoce en detalle: pipeline de cotizaciones, lead score, registro de actividades, tareas de seguimiento, reglas de asignación de tickets (solo asesoras/superadmin asignan), turno GPS, scripts de venta y manejo de objeciones.

---

## 9. Seguridad implementada

Auditoría OWASP Top 10 aplicada sobre todo el proyecto. Medidas activas:

| Medida | Detalle |
|---|---|
| **Hashing de contraseñas** | Argon2 como hasher primario (`PASSWORD_HASHERS`), con fallback PBKDF2/BCrypt para hashes existentes |
| **Anti fuerza bruta** | Bloqueo de 15 min tras 5 intentos fallidos de login, por IP+usuario, en los 3 portales (`_is_locked_out`, `_record_failed_login`, cache-based) |
| **Anti Open Redirect** | `_safe_next()` valida que el parámetro `next` sea una ruta relativa interna antes de redirigir tras login |
| **Logout endurecido** | Las rutas de logout ya no aceptan GET (prevención de CSRF-via-GET); solo POST con CSRF token |
| **Control de acceso a facturación** | `CRMLoginMixin` verifica explícitamente `is_staff`, no solo `is_authenticated` (corrige una escalada de privilegios donde cualquier empleado autenticado podía ver facturas) |
| **XSS en JSON-LD** | `_safe_json_script()` escapa `</script>` y comentarios HTML antes de usar `mark_safe()` |
| **Webhook de Wompi** | Verificación de firma HMAC-SHA256 con `hmac.compare_digest` (constante en tiempo) |
| **Cabeceras HTTP** | CSP, Permissions-Policy, HSTS, X-Frame-Options=DENY, X-Content-Type-Options, Referrer-Policy estricto (vía `SecurityHeadersMiddleware`, solo producción) |
| **Cookies** | `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE`, `Secure` en producción |
| **Logging de auditoría** | Logger dedicado `apps.auth` registra cada login exitoso/fallido con IP, en los 3 portales |
| **Secretos** | `.env.example` sin credenciales reales (se detectó y corrigió una API key de Groq expuesta) |
| **Mensajes de error** | Sin stacktraces expuestos al usuario final (encuestas y otros formularios públicos) |

---

## 10. Integraciones externas

| Servicio | Uso | Configuración |
|---|---|---|
| **Wompi** | Pasarela de pagos (tarjeta, PSE, Nequi) | `WOMPI_PUBLIC_KEY`, `WOMPI_PRIVATE_KEY`, `WOMPI_INTEGRITY_KEY`, `WOMPI_EVENTS_KEY` |
| **Groq** | IA de los asistentes (gratis) | `GROQ_API_KEY` |
| **Anthropic** | IA fallback (pago) | `ANTHROPIC_API_KEY` (opcional) |
| **CallMeBot** | Notificaciones WhatsApp 1-a-1 sin riesgo de baneo | `CALLMEBOT_APIKEY`, `WHATSAPP_NOTIFY_PHONE` |
| **Sentry** | Monitoreo de errores en producción | `SENTRY_DSN` |
| **SMTP** | Envío de emails transaccionales en producción | `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` |

---

## 11. Resumen de URLs raíz

| Prefijo | App | Acceso |
|---|---|---|
| `/` | core, catalog, services, blog | Público |
| `/cotizador/` | leads | Público |
| `/pago/` | payments | Público (checkout) |
| `/encuesta/` | encuestas | Público + staff (panel) |
| `/blog/` | blog | Público |
| `/dashadmin/` | dashboard | Solo staff |
| `/panel/` | dashboard | Empleados no-staff (asesora/técnico/mensajero) |
| `/campo/` | dashboard | Técnicos/mensajeros (legado) |
| `/panel-admin-sc/` | Django admin | Superusuario |
| `/sitemap.xml`, `/robots.txt` | seo | Público (bots) |

---

## 12. Pendientes / deuda técnica conocida

- **Duplicidad `/panel/` vs `/campo/`**: ambos portales sirven a técnicos/mensajeros con lógica parecida pero no idéntica (ver sección 5.3). Definir si se retira `/campo/`.
- **`DeliveryTask` vs `FollowUpTask`**: dos modelos de "tarea" para personal de campo que no están unificados.
- **Rate limiting en formularios públicos** (cotizador, contacto, encuesta): solo el login tiene protección anti fuerza bruta; los formularios públicos de captación no tienen límite de envíos por IP.
- **MFA**: no implementado aún en ningún portal.

### Listo para producción vs. pendiente

✅ **Ya resuelto** (ver `render.yaml` + `build.sh` en la raíz del proyecto):
- Manifiesto de despliegue para Render (Blueprint)
- Build automatizado: instala dependencias, compila CSS/JS, corre `collectstatic` y `migrate` en cada deploy
- `manage.py check --deploy` no reporta issues de seguridad sobre `production.py` (más allá del `SECRET_KEY` de prueba usado para el chequeo)

🔴 **Pendiente — requiere decisión/credenciales humanas, no se puede resolver solo con código**:
- Generar y configurar `DJANGO_SECRET_KEY` real de producción
- Obtener claves reales de Wompi (actualmente son de sandbox)
- Configurar `DATABASE_URL` de Supabase y demás variables de entorno en el dashboard de Render
- **Almacenamiento persistente de `media/`**: Render usa disco efímero — cualquier imagen subida (productos, blog, comprobantes de entrega) se pierde en cada redeploy. Requiere migrar a storage S3-compatible (Supabase Storage es la opción más natural) antes de cargar contenido real en producción.
