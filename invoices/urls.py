from django.urls import path
from .views import FactureFournisseurListView, FactureFournisseurDetailView, FactureFournisseurCreateView, FactureFournisseurUpdateView

app_name = "invoices"
urlpatterns = [
    path("", FactureFournisseurListView.as_view(), name="list"),
    path("nouvelle/", FactureFournisseurCreateView.as_view(), name="create"),
    path("<int:pk>/", FactureFournisseurDetailView.as_view(), name="detail"),
    path("<int:pk>/modifier/", FactureFournisseurUpdateView.as_view(), name="update"),
]
