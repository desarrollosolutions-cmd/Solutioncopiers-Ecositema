"""URLs del portal de campo — /campo/"""
from django.urls import path
from . import views

app_name = "campo"

urlpatterns = [
    path("acceso/",              views.CampoLoginView.as_view(),          name="login"),
    path("salir/",               views.CampoLogoutView.as_view(),         name="logout"),
    path("",                     views.CampoTurnoView.as_view(),          name="turno"),
    path("ubicacion/",           views.CampoUbicacionUpdateView.as_view(), name="ubicacion"),
    path("turno/inicio/",        views.CampoShiftStartView.as_view(),     name="shift_start"),
    path("turno/fin/",           views.CampoShiftEndView.as_view(),       name="shift_end"),
    path("tareas/<int:pk>/completar/", views.CampoTaskCompleteView.as_view(), name="task_complete"),
    path("tickets/<int:pk>/",          views.CampoTicketDetailView.as_view(),  name="ticket_detail"),
    path("mapa-ruta/",                 views.CampoTurnoMapView.as_view(),      name="turno_map"),
]
