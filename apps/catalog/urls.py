"""URLs del Silo 1: Hardware."""
from django.urls import path
from . import views

app_name = "catalog"

urlpatterns = [
    # Alquiler
    path("alquiler-fotocopiadoras-medellin/", views.RentalListView.as_view(), name="rental_list"),
    path("alquiler-fotocopiadoras-medellin/modelo/<slug:slug>/", views.CopierDetailView.as_view(), name="copier_detail_rental"),
    path("alquiler-fotocopiadoras-medellin/<slug:category_slug>/", views.RentalCategoryView.as_view(), name="rental_category"),

    # Venta
    path("venta-fotocopiadoras-medellin/", views.SaleListView.as_view(), name="sale_list"),
    path("venta-fotocopiadoras-medellin/<slug:slug>/", views.CopierDetailView.as_view(), name="copier_detail_sale"),

    # Servicio técnico
    path("servicio-tecnico-fotocopiadoras/", views.TechnicalServiceView.as_view(), name="technical_service"),

    # Consumibles
    path("consumibles-toner-ricoh/", views.ConsumablesListView.as_view(), name="consumables_list"),
    path("consumibles-toner-ricoh/<slug:slug>/", views.ConsumableDetailView.as_view(), name="consumable_detail"),

    # Cableado estructurado — silo raíz con keyword+localización
    path("cableado-estructurado-medellin/", views.StructuredCablingView.as_view(), name="structured_cabling"),
    path("cableado-estructurado-medellin/<slug:slug>/", views.CablingDetailView.as_view(), name="cabling_detail"),

    # Búsqueda global pública
    path("buscar/", views.PublicSearchView.as_view(), name="search"),
]
