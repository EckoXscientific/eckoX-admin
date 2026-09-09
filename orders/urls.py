from django.urls import path
from .views import DossierListView, DossierDetailView, DossierCreateView, DossierUpdateView

from .views import CommandeListView, CommandeDetailView, CommandeCreateView, CommandeUpdateView

app_name = "orders"
urlpatterns = [
    path("commandes/", CommandeListView.as_view(), name="commande_list"),
    path("commandes/nouvelle/", CommandeCreateView.as_view(), name="commande_create"),
    path("commandes/<int:pk>/", CommandeDetailView.as_view(), name="commande_detail"),
    path("commandes/<int:pk>/modifier/", CommandeUpdateView.as_view(), name="commande_update"),
    path("", DossierListView.as_view(), name="dossier_list"),
    path("dossiers/nouveau/", DossierCreateView.as_view(), name="dossier_create"),
    path("dossiers/<int:pk>/", DossierDetailView.as_view(), name="dossier_detail"),
    path("dossiers/<int:pk>/modifier/", DossierUpdateView.as_view(), name="dossier_update"),
]
