"""URLs del módulo WhatsApp CRM."""
from django.urls import path
from . import views
from .webhook import WhatsAppWebhookView

app_name = "wa"

urlpatterns = [
    # ── Webhook Meta (público, sin CSRF) ──
    path("webhook/",  WhatsAppWebhookView.as_view(), name="webhook"),

    # ── Panel — asesoras ──
    path("panel/inbox/",                    views.PanelWAInboxView.as_view(),        name="panel_inbox"),
    path("panel/conversacion/<int:pk>/",    views.PanelWAConversationView.as_view(), name="panel_conversation"),
    path("panel/simulador/",                views.WASimulatorView.as_view(),         name="simulator"),

    # ── Dashadmin — administración ──
    path("dash/",                           views.DashWAOverviewView.as_view(),      name="dash_overview"),
    path("dash/conversacion/<int:pk>/",     views.DashWAConversationView.as_view(),  name="dash_conversation"),
    path("dash/etiquetas/",                 views.DashWALabelsView.as_view(),        name="dash_labels"),
    path("dash/respuestas-rapidas/",        views.DashWAQuickRepliesView.as_view(),  name="dash_quick_replies"),
    path("dash/asignar/<int:pk>/",          views.DashWAAssignView.as_view(),    name="dash_assign"),
]
