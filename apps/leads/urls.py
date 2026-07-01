"""URLs del módulo Leads."""
from django.urls import path
from . import views

app_name = "leads"

urlpatterns = [
    path("", views.QuoteWizardView.as_view(), name="wizard"),
    path("paso/<int:step>/", views.QuoteStepView.as_view(), name="step"),
    path("enviar/", views.QuoteSubmitView.as_view(), name="submit"),
    path("gracias/", views.ThankYouView.as_view(), name="thank_you"),
    path("api/calcular/", views.CalculateQuoteAPI.as_view(), name="api_calculate"),
    path("api/buscar-insumo/", views.SearchConsumableAPI.as_view(), name="api_search_consumable"),
]
