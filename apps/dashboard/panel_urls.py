"""URLs del panel de asesoras — /panel/"""
from django.urls import path
from . import views

app_name = "panel"

urlpatterns = [
    # Auth
    path("acceso/", views.PanelLoginView.as_view(),  name="login"),
    path("salir/",  views.PanelLogoutView.as_view(), name="logout"),

    # Home
    path("", views.PanelHomeView.as_view(), name="home"),

    # Cotizaciones
    path("cotizaciones/",          views.PanelQuoteListView.as_view(),   name="quotes"),
    path("cotizaciones/<int:pk>/", views.PanelQuoteDetailView.as_view(), name="quote_detail"),

    # Clientes
    path("clientes/",                          views.PanelClientListView.as_view(),    name="clients"),
    path("clientes/<int:pk>/",                 views.PanelClientDetailView.as_view(),  name="client_detail"),
    path("clientes/<int:pk>/actividad/",       views.PanelActivityCreateView.as_view(), name="client_activity_create"),
    path("clientes/<int:pk>/tarea/",           views.PanelTaskCreateView.as_view(),    name="client_task_create"),
    path("tareas/<int:pk>/toggle/",            views.PanelTaskToggleView.as_view(),    name="task_toggle"),

    # Tickets
    path("tickets/",           views.PanelTicketListView.as_view(),   name="tickets"),
    path("tickets/nuevo/",     views.PanelTicketCreateView.as_view(), name="ticket_create"),
    path("tickets/<int:pk>/",  views.PanelTicketDetailView.as_view(), name="ticket_detail"),

    # Contratos
    path("contratos/", views.PanelContractListView.as_view(), name="contracts"),

    # Insumos
    path("insumos/",               views.PanelConsumableListView.as_view(),         name="consumables"),
    path("insumos/autocomplete/",  views.PanelConsumableAutocompleteView.as_view(), name="consumables_autocomplete"),

    # Facturas
    path("facturas/",                        views.PanelInvoiceListView.as_view(),         name="invoices"),
    path("facturas/nueva/",                  views.PanelInvoiceCreateView.as_view(),       name="invoice_create"),
    path("facturas/<int:pk>/",               views.PanelInvoiceDetailView.as_view(),       name="invoice_detail"),
    path("facturas/<int:pk>/estado/",        views.PanelInvoiceStatusUpdateView.as_view(), name="invoice_status"),

    # Asistente virtual
    path("asistente/chat/", views.PanelAssistantView.as_view(), name="assistant_chat"),

    # Notificaciones CRM (campana panel asesoras)
    path("notificaciones/json/",              views.PanelNotificationsJsonView.as_view(),       name="notifications_json"),
    path("notificaciones/<int:pk>/leer/",     views.PanelNotificationMarkReadView.as_view(),    name="notification_read"),
    path("notificaciones/leer-todas/",        views.PanelNotificationMarkAllReadView.as_view(), name="notifications_read_all"),

    # Turno y GPS (técnicos y mensajeros desde el panel)
    path("turno/",                           views.PanelTurnoView.as_view(),             name="turno"),
    path("turno/inicio/",                    views.PanelShiftStartView.as_view(),        name="shift_start"),
    path("turno/fin/",                       views.PanelShiftEndView.as_view(),          name="shift_end"),
    path("ubicacion/",                       views.PanelUbicacionView.as_view(),         name="ubicacion"),
    path("entregas/<int:pk>/completar/",     views.PanelDeliveryCompleteView.as_view(),  name="delivery_complete"),
]
