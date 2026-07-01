from django.urls import path
from . import views

app_name = "encuestas"

urlpatterns = [
    path("", views.encuesta_form, name="form"),
    path("guardar/", views.encuesta_guardar, name="guardar"),
    path("gracias/", views.encuesta_exito, name="exito"),
    path("acceso/", views.panel_login, name="login"),
    path("panel/", views.panel, name="panel"),
]
