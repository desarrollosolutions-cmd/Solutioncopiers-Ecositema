"""URLs del Silo 2: Software."""
from django.urls import path
from . import views

app_name = "services"

urlpatterns = [
    path("desarrollo-software-medellin/", views.SoftwareDevelopmentView.as_view(), name="software_development"),
    path("desarrollo-software-medellin/<slug:slug>/", views.SoftwareServiceDetailView.as_view(), name="software_detail"),

    path("diseno-paginas-web-medellin/", views.WebDesignView.as_view(), name="web_design"),
    path("diseno-paginas-web-medellin/<slug:slug>/", views.WebDesignDetailView.as_view(), name="web_design_detail"),

    path("desarrollo-aplicaciones-moviles/", views.MobileAppsView.as_view(), name="mobile_apps"),
    path("desarrollo-aplicaciones-moviles/<slug:slug>/", views.MobileAppDetailView.as_view(), name="mobile_app_detail"),

    path("bases-de-datos-empresariales/", views.DatabaseServicesView.as_view(), name="database_services"),
    path("bases-de-datos-empresariales/<slug:slug>/", views.DatabaseServiceDetailView.as_view(), name="database_detail"),
]
