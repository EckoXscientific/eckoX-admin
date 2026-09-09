from django.conf import settings
from django.db import models
from orders.models import SupplierLinkedModel


class Reception(SupplierLinkedModel):
    reference = models.CharField(max_length=100, unique=True)
    date_reception = models.DateTimeField()
    receptionne_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="receptions_effectuees")
    commande = models.ForeignKey("orders.CommandeFournisseur", on_delete=models.PROTECT, null=True, blank=True, related_name="receptions")
    tracking = models.CharField(max_length=255, blank=True)
    etat_colis = models.CharField(max_length=100)
    statut = models.CharField(max_length=100)
    commentaire = models.TextField(blank=True)

    def __str__(self):
        return self.reference
