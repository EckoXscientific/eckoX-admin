from django.core.exceptions import ValidationError
from django.db import models
from users.models import TrackedModel


OWNERS = ("dossier", "commande", "reception", "facture_fournisseur", "facture_client")


def exactly_one_owner():
    condition = models.Q()
    for owner in OWNERS:
        condition |= models.Q(**{f"{field}__isnull": field != owner for field in OWNERS})
    return condition


class Document(TrackedModel):
    nom = models.CharField(max_length=255)
    categorie = models.CharField(max_length=100)
    fichier = models.FileField(upload_to="documents/%Y/%m/", max_length=255)
    dossier = models.ForeignKey("orders.DossierAdministratif", on_delete=models.PROTECT, null=True, blank=True, related_name="documents")
    commande = models.ForeignKey("orders.CommandeFournisseur", on_delete=models.PROTECT, null=True, blank=True, related_name="documents")
    reception = models.ForeignKey("receptions.Reception", on_delete=models.PROTECT, null=True, blank=True, related_name="documents")
    facture_fournisseur = models.ForeignKey("invoices.FactureFournisseur", on_delete=models.PROTECT, null=True, blank=True, related_name="documents")
    facture_client = models.ForeignKey("invoices.FactureClient", on_delete=models.PROTECT, null=True, blank=True, related_name="documents")

    class Meta:
        constraints = [models.CheckConstraint(condition=exactly_one_owner(), name="document_exactly_one_owner")]

    def clean(self):
        super().clean()
        if sum(getattr(self, f"{owner}_id") is not None for owner in OWNERS) != 1:
            raise ValidationError("Un document doit appartenir à exactement un élément.")

    def __str__(self):
        return self.nom
