from django.conf import settings
from django.db import models


class PanelPermissions(models.Model):
    """
    Modelo sin tabla (managed=False) usado solo para registrar permisos
    personalizados del portal de empleados en el sistema de permisos de Django.
    """

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            # Ventas
            ("panel_cotizaciones", "Panel: Cotizaciones — ver, asignar y gestionar estados"),
            ("panel_clientes",     "Panel: Clientes — ver perfiles e historial"),
            ("panel_actividades",  "Panel: Actividades — registrar llamadas, notas y tareas"),
            # Operaciones
            ("panel_tickets",      "Panel: Tickets — ver, crear y actualizar servicio"),
            ("panel_contratos",    "Panel: Contratos — ver lista de alquileres"),
            ("panel_insumos",      "Panel: Insumos — ver catálogo de consumibles"),
            # Datos
            ("panel_reportes",     "Panel: Reportes — ver estadísticas y métricas"),
            ("panel_exportar",     "Panel: Exportar — descargar datos en CSV"),
            # Facturación
            ("panel_facturacion",  "Panel: Facturación — crear y gestionar facturas propias"),
        ]


# ---------------------------------------------------------------------------
# Etiquetas, descripciones y metadatos para la UI
# ---------------------------------------------------------------------------

PANEL_PERM_LABELS = {
    "panel_cotizaciones": "Cotizaciones",
    "panel_clientes":     "Clientes",
    "panel_actividades":  "Actividades y tareas",
    "panel_tickets":      "Tickets de servicio",
    "panel_contratos":    "Contratos de alquiler",
    "panel_insumos":      "Insumos y consumibles",
    "panel_reportes":     "Reportes",
    "panel_exportar":     "Exportar datos",
    "panel_facturacion":  "Facturación",
}

PANEL_PERM_DESCRIPTIONS = {
    "panel_cotizaciones": "Ver lista, detalle, cambiar estado y asignarse cotizaciones.",
    "panel_clientes":     "Ver perfiles completos e historial de cada cliente.",
    "panel_actividades":  "Registrar llamadas, emails, notas y tareas de seguimiento en clientes.",
    "panel_tickets":      "Ver tickets, crear nuevos y actualizar estado, prioridad y notas.",
    "panel_contratos":    "Ver lista de contratos activos y fechas de vencimiento.",
    "panel_insumos":      "Consultar el catálogo de consumibles y su disponibilidad.",
    "panel_reportes":     "Ver estadísticas de ventas, conversión y rendimiento del equipo.",
    "panel_exportar":     "Descargar listas de clientes, cotizaciones y contratos en CSV.",
    "panel_facturacion":  "Crear facturas manuales, ver sus propias facturas y actualizar el estado de cobro.",
}

# Grupos de permisos por categoría (para la UI del formulario)
PANEL_PERM_GROUPS = [
    {
        "key":   "ventas",
        "label": "Ventas y CRM",
        "color": "#3B82F6",
        "perms": ["panel_cotizaciones", "panel_clientes", "panel_actividades", "panel_facturacion"],
    },
    {
        "key":   "operaciones",
        "label": "Operaciones",
        "color": "#10B981",
        "perms": ["panel_tickets", "panel_contratos", "panel_insumos"],
    },
    {
        "key":   "datos",
        "label": "Reportes y datos",
        "color": "#8B5CF6",
        "perms": ["panel_reportes", "panel_exportar"],
    },
]

# Roles predefinidos (preset de permisos)
PANEL_ROLES = [
    {
        "key":         "asesora",
        "label":       "Asesor Comercial",
        "description": "Gestiona pipeline, clientes, contratos, tickets y facturas.",
        "color":       "#3B82F6",
        "perms":       ["panel_cotizaciones", "panel_clientes", "panel_actividades",
                        "panel_tickets", "panel_contratos", "panel_insumos", "panel_facturacion"],
    },
    {
        "key":         "tecnico",
        "label":       "Técnico",
        "description": "Solo ve y gestiona sus tickets asignados. Turno via /panel/turno/.",
        "color":       "#10B981",
        "perms":       ["panel_tickets"],
    },
    {
        "key":         "supervisor",
        "label":       "Supervisor",
        "description": "Acceso completo a todas las secciones del panel.",
        "color":       "#7C3AED",
        "perms":       ["panel_cotizaciones", "panel_clientes", "panel_actividades",
                        "panel_tickets", "panel_contratos", "panel_insumos",
                        "panel_reportes", "panel_exportar", "panel_facturacion"],
    },
    {
        "key":         "lectura",
        "label":       "Solo lectura",
        "description": "Puede ver cotizaciones y clientes sin modificar nada.",
        "color":       "#6B7280",
        "perms":       ["panel_cotizaciones", "panel_clientes"],
    },
]


class EmployeeActivity(models.Model):
    class Action(models.TextChoices):
        LOGIN            = "login",            "Inicio de sesión"
        LOGOUT           = "logout",           "Cierre de sesión"
        VIEW_QUOTE       = "view_quote",       "Ver cotización"
        UPDATE_QUOTE     = "update_quote",     "Actualizar cotización"
        ASSIGN_QUOTE     = "assign_quote",     "Asignarse cotización"
        VIEW_TICKET      = "view_ticket",      "Ver ticket"
        CREATE_TICKET    = "create_ticket",    "Crear ticket"
        UPDATE_TICKET    = "update_ticket",    "Actualizar ticket"
        VIEW_CLIENT      = "view_client",      "Ver cliente"
        VIEW_CONTRACT    = "view_contract",    "Ver contrato"
        VIEW_CONSUMABLES = "view_consumables", "Ver insumos"
        SEARCH_CONSUMABLES = "search_consumables", "Buscar insumos"

    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="panel_activities"
    )
    action      = models.CharField(max_length=25, choices=Action.choices)
    description = models.CharField(max_length=500, blank=True)
    related_pk  = models.PositiveIntegerField(null=True, blank=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Actividad del panel"
        verbose_name_plural = "Actividades del panel"
        ordering            = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} — {self.get_action_display()} ({self.created_at:%d/%m/%Y %H:%M})"


# ---------------------------------------------------------------------------
# Notificaciones internas
# ---------------------------------------------------------------------------

class Notification(models.Model):
    class Type(models.TextChoices):
        TASK_OVERDUE       = "task_overdue",       "Tarea vencida"
        CONTRACT_EXPIRING  = "contract_expiring",  "Contrato por vencer"
        CONTRACT_RENEWAL   = "contract_renewal",   "Renovación de contrato"
        NEW_QUOTE          = "new_quote",          "Nueva cotización"
        QUOTE_STALE        = "quote_stale",        "Cotización sin atender"
        LEAD_COLD          = "lead_cold",          "Lead sin actividad"
        TASK_ASSIGNED      = "task_assigned",      "Nueva tarea asignada"

    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="crm_notifications"
    )
    type       = models.CharField(max_length=25, choices=Type.choices)
    title      = models.CharField(max_length=200)
    message    = models.TextField(blank=True)
    link       = models.CharField(max_length=300, blank=True)
    is_read    = models.BooleanField(default=False, db_index=True)
    read_at    = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Notificación"
        verbose_name_plural = "Notificaciones"
        ordering            = ["-created_at"]
        indexes             = [models.Index(fields=["user", "is_read", "-created_at"])]

    def __str__(self):
        return f"{self.user.username} — {self.title}"

    @classmethod
    def push(cls, user, type, title, message="", link=""):
        """Crea notificación solo si no existe ya una igual sin leer."""
        exists = cls.objects.filter(
            user=user, type=type, title=title, is_read=False
        ).exists()
        if not exists:
            cls.objects.create(
                user=user, type=type, title=title, message=message, link=link
            )


# ---------------------------------------------------------------------------
# Templates de mensajes / plantillas rápidas
# ---------------------------------------------------------------------------

class MessageTemplate(models.Model):
    class TemplateType(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL    = "email",    "Email"
        NOTE     = "note",     "Nota interna"
        CALL     = "call",     "Guión de llamada"

    name      = models.CharField("nombre", max_length=100)
    type      = models.CharField(max_length=15, choices=TemplateType.choices)
    body      = models.TextField("contenido")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Plantilla de mensaje"
        verbose_name_plural = "Plantillas de mensajes"
        ordering            = ["type", "name"]

    def __str__(self):
        return f"[{self.get_type_display()}] {self.name}"


# ---------------------------------------------------------------------------
# Usuarios de campo (mensajeros y técnicos)
# ---------------------------------------------------------------------------

class FieldUser(models.Model):
    class Role(models.TextChoices):
        MENSAJERO = "mensajero", "Mensajero"
        TECNICO   = "tecnico",   "Técnico"

    user  = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="field_profile"
    )
    role  = models.CharField(max_length=15, choices=Role.choices)
    phone = models.CharField("teléfono", max_length=20, blank=True)

    class Meta:
        verbose_name        = "Usuario de campo"
        verbose_name_plural = "Usuarios de campo"

    def __str__(self):
        return f"{self.get_role_display()} — {self.user.get_full_name() or self.user.username}"


class FieldUserLocation(models.Model):
    user        = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="field_location"
    )
    latitude    = models.DecimalField(max_digits=10, decimal_places=7)
    longitude   = models.DecimalField(max_digits=10, decimal_places=7)
    accuracy    = models.FloatField(null=True, blank=True)
    is_on_shift = models.BooleanField(default=False, db_index=True)
    battery     = models.PositiveSmallIntegerField(null=True, blank=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Ubicación de campo"
        verbose_name_plural = "Ubicaciones de campo"

    def __str__(self):
        return f"{self.user.username} ({self.latitude}, {self.longitude})"


class DeliveryTask(models.Model):
    class Status(models.TextChoices):
        PENDING   = "pending",   "Pendiente"
        DONE      = "done",      "Completada"
        CANCELLED = "cancelled", "Cancelada"

    field_user         = models.ForeignKey(
        FieldUser, on_delete=models.CASCADE, related_name="delivery_tasks"
    )
    title              = models.CharField("título", max_length=200)
    description        = models.TextField("descripción", blank=True)
    address            = models.CharField("dirección", max_length=300, blank=True)
    order              = models.PositiveSmallIntegerField("orden", default=0)
    status             = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    due_date           = models.DateField("fecha", null=True, blank=True, db_index=True)
    created_by         = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="created_delivery_tasks"
    )
    created_at         = models.DateTimeField(auto_now_add=True)
    completed_at       = models.DateTimeField(null=True, blank=True)
    completion_notes     = models.TextField("notas de entrega", blank=True)
    completion_invoice   = models.CharField("# factura / remisión", max_length=100, blank=True)
    completion_photo     = models.ImageField(upload_to="delivery_proofs/%Y/%m/", null=True, blank=True)
    completion_signature = models.TextField("firma del receptor", blank=True)

    class Meta:
        ordering            = ["order", "created_at"]
        verbose_name        = "Tarea de entrega"
        verbose_name_plural = "Tareas de entrega"

    def __str__(self):
        return f"{self.title} — {self.field_user.user.get_full_name() or self.field_user.user.username}"
