from django.urls import path
from . import views
from apps.payments import views as billing_views

app_name = "dashboard"

urlpatterns = [
    # Auth
    path("acceso/",  views.DashboardLoginView.as_view(),  name="login"),
    path("salir/",   views.DashboardLogoutView.as_view(), name="logout"),

    # Home
    path("", views.DashboardHomeView.as_view(), name="home"),

    # Reportes
    path("reportes/", views.ReportsView.as_view(), name="reports"),

    # Tickets de servicio
    path("tickets/",           views.TicketListView.as_view(),   name="tickets"),
    path("tickets/nuevo/",     views.TicketCreateView.as_view(), name="ticket_create"),
    path("tickets/<int:pk>/",  views.TicketDetailView.as_view(), name="ticket_detail"),

    # Contratos de alquiler
    path("contratos/",           views.ContractListView.as_view(),   name="contracts"),
    path("contratos/nuevo/",     views.ContractCreateView.as_view(), name="contract_create"),
    path("contratos/<int:pk>/",  views.ContractDetailView.as_view(), name="contract_detail"),

    # Clientes
    path("clientes/autocomplete/",                  views.ClientAutocompleteView.as_view(), name="client_autocomplete"),
    path("clientes/",                               views.ClientListView.as_view(),    name="clients"),
    path("clientes/<int:pk>/",                      views.ClientDetailView.as_view(),  name="client_detail"),
    path("clientes/<int:pk>/rescore/",              views.ClientRescoreView.as_view(), name="client_rescore"),
    path("clientes/<int:pk>/actividad/",            views.ActivityCreateView.as_view(), name="client_activity_create"),
    path("clientes/<int:pk>/tarea/",                views.TaskCreateView.as_view(),     name="client_task_create"),
    path("tareas/<int:pk>/toggle/",                 views.TaskToggleView.as_view(),     name="task_toggle"),

    # Exportar CSV
    path("exportar/leads/",      views.ExportLeadsCSVView.as_view(),     name="export_leads"),
    path("exportar/cotizaciones/",views.ExportQuotesCSVView.as_view(),   name="export_quotes"),
    path("exportar/contratos/",  views.ExportContractsCSVView.as_view(), name="export_contracts"),

    # Cotizaciones
    path("cotizaciones/",                    views.QuoteListView.as_view(),          name="quotes"),
    path("cotizaciones/pipeline/",           views.PipelineView.as_view(),           name="pipeline"),
    path("cotizaciones/<int:pk>/",           views.QuoteDetailView.as_view(),        name="quote_detail"),
    path("cotizaciones/<int:pk>/estado/",    views.QuoteStatusUpdateView.as_view(),  name="quote_status"),
    path("cotizaciones/<int:pk>/notas/",     views.QuoteNotesUpdateView.as_view(),   name="quote_notes"),
    path("cotizaciones/<int:pk>/mover/",     views.QuotePipelineMoveView.as_view(),  name="quote_move"),
    path("cotizaciones/<int:pk>/propuesta/", views.QuoteProposalView.as_view(),      name="quote_proposal"),

    # Consumibles
    path("consumibles/",              views.ConsumableListView.as_view(),   name="consumables"),
    path("consumibles/nuevo/",        views.ConsumableCreateView.as_view(), name="consumable_create"),
    path("consumibles/<int:pk>/",     views.ConsumableUpdateView.as_view(), name="consumable_edit"),
    path("consumibles/<int:pk>/borrar/", views.ConsumableDeleteView.as_view(), name="consumable_delete"),

    # Gestión de stock
    path("stock/",                    views.StockManageView.as_view(),      name="stock"),
    path("stock/autocomplete/",       views.StockAutocompleteView.as_view(), name="stock_autocomplete"),
    path("stock/<int:pk>/ajuste/",    views.StockAdjustView.as_view(),      name="stock_adjust"),
    path("stock/<int:pk>/historial/", views.StockHistoryView.as_view(),     name="stock_history"),

    # Actividad de asesoras
    path("actividad/", views.EmployeeActivityView.as_view(), name="activity"),

    # Fotocopiadoras
    path("fotocopiadoras/",          views.CopierListView.as_view(),   name="copiers"),
    path("fotocopiadoras/nuevo/",    views.CopierCreateView.as_view(), name="copier_create"),
    path("fotocopiadoras/<int:pk>/", views.CopierUpdateView.as_view(), name="copier_edit"),
    path("fotocopiadoras/<int:pk>/borrar/", views.CopierDeleteView.as_view(), name="copier_delete"),

    # Blog
    path("blog/",            views.BlogPostListView.as_view(), name="blog"),
    path("blog/<int:pk>/",   views.BlogPostEditView.as_view(), name="blog_edit"),

    # Encuestas
    path("encuestas/", views.SurveysStatsView.as_view(), name="surveys"),

    # Notificaciones automáticas
    path("notificaciones/", views.NotificationsView.as_view(), name="notifications"),

    # Gestión de empleados (asesoras)
    path("empleados/",           views.EmployeeListView.as_view(),   name="employees"),
    path("empleados/nuevo/",     views.EmployeeCreateView.as_view(), name="employee_create"),
    path("empleados/<int:pk>/",  views.EmployeeDetailView.as_view(), name="employee_detail"),

    # Gestión de administradores (solo superusuarios)
    path("administradores/",           views.AdminUserListView.as_view(),   name="admins"),
    path("administradores/nuevo/",     views.AdminUserCreateView.as_view(), name="admin_create"),
    path("administradores/<int:pk>/",  views.AdminUserEditView.as_view(),   name="admin_detail"),

    # Configuración
    path("configuracion/", views.SettingsView.as_view(), name="settings"),

    # Asistente virtual
    path("asistente/chat/", views.AdminAssistantView.as_view(), name="assistant_chat"),

    # Búsqueda global Ctrl+K
    path("buscar/", views.GlobalSearchView.as_view(), name="global_search"),

    # Notificaciones CRM (campana)
    path("crm/notificaciones/json/",          views.CrmNotificationsJsonView.as_view(),      name="crm_notifications_json"),
    path("crm/notificaciones/<int:pk>/leer/", views.CrmNotificationMarkReadView.as_view(),    name="crm_notification_read"),
    path("crm/notificaciones/leer-todas/",    views.CrmNotificationMarkAllReadView.as_view(), name="crm_notifications_read_all"),

    # Plantillas de mensajes
    path("plantillas/",           views.MessageTemplateListView.as_view(),   name="message_templates"),
    path("plantillas/nueva/",     views.MessageTemplateCreateView.as_view(), name="message_template_create"),
    path("plantillas/<int:pk>/",  views.MessageTemplateEditView.as_view(),   name="message_template_edit"),
    path("plantillas/api/",       views.MessageTemplateApiView.as_view(),    name="message_template_api"),

    # KPIs de asesoras
    path("kpis/", views.KPIsView.as_view(), name="kpis"),

    # Lecturas de contador
    path("contratos/<int:contract_pk>/lecturas/", views.MeterReadingCreateView.as_view(), name="meter_reading_create"),
    path("medidores/", views.MeterReadingsDashboardView.as_view(), name="meter_dashboard"),

    # Unidades de equipos
    path("equipos/",           views.CopierUnitListView.as_view(),   name="copier_units"),
    path("equipos/nuevo/",     views.CopierUnitCreateView.as_view(), name="copier_unit_create"),
    path("equipos/<int:pk>/",  views.CopierUnitEditView.as_view(),   name="copier_unit_edit"),

    # Facturación y pagos
    path("facturacion/",                            billing_views.ARDashboardView.as_view(),        name="ar_dashboard"),
    path("facturacion/facturas/",                   billing_views.InvoiceListView.as_view(),        name="invoice_list"),
    path("facturacion/facturas/nueva/",             billing_views.InvoiceCreateView.as_view(),      name="invoice_create"),
    path("facturacion/facturas/<int:pk>/",          billing_views.InvoiceDetailView.as_view(),      name="invoice_detail"),
    path("facturacion/facturas/<int:pk>/estado/",   billing_views.InvoiceStatusUpdateView.as_view(), name="invoice_status"),
    path("facturacion/pedidos/",                    billing_views.OrderListView.as_view(),          name="order_list"),
    path("facturacion/pedidos/<str:reference>/",    billing_views.OrderDetailView.as_view(),        name="order_detail"),

    # Personal de campo — mapa en tiempo real
    path("campo/",                           views.CampoMapView.as_view(),              name="campo_map"),
    path("campo/json/",                      views.CampoLocationsJsonView.as_view(),    name="campo_locations_json"),
    path("campo/usuarios/",                  views.CampoUserListView.as_view(),         name="campo_users"),
    path("campo/usuarios/nuevo/",            views.CampoUserCreateView.as_view(),       name="campo_user_create"),
    path("campo/usuarios/<int:pk>/",         views.CampoUserDetailView.as_view(),       name="campo_user_detail"),
    path("campo/tareas/",                    views.CampoTaskListView.as_view(),         name="campo_tasks"),
    path("campo/tareas/<int:pk>/",           views.CampoTaskDetailView.as_view(),       name="campo_task_detail"),
    path("campo/rutas/",                     views.CampoRouteHistoryView.as_view(),     name="campo_routes"),
    path("campo/rutas/json/",                views.CampoRouteJsonView.as_view(),        name="campo_routes_json"),

    # Contabilidad Colombia
    path("contabilidad/",                           billing_views.ContabilidadView.as_view(),       name="contabilidad"),
    path("contabilidad/libro-ventas/",              billing_views.LibroVentasView.as_view(),        name="libro_ventas"),
    path("contabilidad/iva/",                       billing_views.IVAReportView.as_view(),          name="iva_report"),
    path("contabilidad/retenciones/",               billing_views.RetencionesSufridasView.as_view(), name="retenciones"),
]
