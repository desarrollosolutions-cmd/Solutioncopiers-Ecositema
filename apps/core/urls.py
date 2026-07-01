"""URLs del módulo Core."""
from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("sobre-nosotros/", views.AboutView.as_view(), name="about"),
    path("contacto/", views.ContactView.as_view(), name="contact"),
    path("soluciones-empresariales/", views.SolutionsHubView.as_view(), name="solutions_hub"),
    path("soluciones-empresariales/<slug:slug>/", views.SolutionDetailView.as_view(), name="solution_detail"),
    path("politica-de-privacidad/", views.PrivacyView.as_view(), name="privacy"),
    path("terminos-y-condiciones/", views.TermsView.as_view(), name="terms"),

    # Asistente virtual público
    path("asistente/chat/", views.PublicAssistantView.as_view(), name="assistant_chat"),
]
