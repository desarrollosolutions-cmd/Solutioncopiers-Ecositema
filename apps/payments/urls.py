"""URLs del módulo de pagos."""
from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    # Carrito
    path("carrito/",             views.CartView.as_view(),       name="cart"),
    path("carrito/agregar/",     views.CartAddView.as_view(),    name="cart_add"),
    path("carrito/actualizar/",  views.CartUpdateView.as_view(), name="cart_update"),

    # Checkout
    path("checkout/",            views.CheckoutView.as_view(),   name="checkout"),

    # Confirmación post-Wompi
    path("confirmacion/<str:reference>/", views.OrderConfirmationView.as_view(), name="order_confirmation"),

    # Webhook Wompi
    path("webhook/wompi/",       views.WompiWebhookView.as_view(), name="wompi_webhook"),
]
