"""URLs CRM del módulo de facturación (montadas bajo /dashadmin/facturacion/)."""
from django.urls import path
from . import views

urlpatterns = [
    # Dashboard AR
    path("",                           views.ARDashboardView.as_view(),       name="ar_dashboard"),

    # Facturas
    path("facturas/",                  views.InvoiceListView.as_view(),       name="invoice_list"),
    path("facturas/nueva/",            views.InvoiceCreateView.as_view(),     name="invoice_create"),
    path("facturas/<int:pk>/",         views.InvoiceDetailView.as_view(),     name="invoice_detail"),
    path("facturas/<int:pk>/estado/",  views.InvoiceStatusUpdateView.as_view(), name="invoice_status"),

    # Pedidos online
    path("pedidos/",                            views.OrderListView.as_view(),   name="order_list"),
    path("pedidos/<str:reference>/",            views.OrderDetailView.as_view(), name="order_detail"),
]
