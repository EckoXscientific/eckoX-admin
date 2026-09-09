from django.core.validators import RegexValidator
from django.db import models
from orders.models import SupplierLinkedModel
from users.models import TrackedModel


class InvoiceFields(models.Model):
    numero = models.CharField(max_length=100)
    montant = models.DecimalField(max_digits=18, decimal_places=2)
    devise = models.CharField(max_length=3, blank=True, validators=[RegexValidator(r"^[A-Z]{3}$", "Utilisez un code devise de trois lettres majuscules.")])

    class Meta:
        abstract = True

    def __str__(self):
        return self.numero


class FactureFournisseur(InvoiceFields, SupplierLinkedModel):
    class Traitement(models.TextChoices):
        A_TRAITER = "a_traiter", "À traiter"
        TRAITEE = "traitee", "Traitée"

    class Paiement(models.TextChoices):
        A_PAYER = "a_payer", "À payer"
        PAYE = "paye", "Payé"

    date_facture = models.DateField()
    commande = models.ForeignKey("orders.CommandeFournisseur", on_delete=models.PROTECT, null=True, blank=True, related_name="factures")
    statut_traitement = models.CharField(max_length=20, choices=Traitement.choices, default=Traitement.A_TRAITER)
    statut_paiement = models.CharField(max_length=20, choices=Paiement.choices, default=Paiement.A_PAYER)
    commentaire = models.TextField(blank=True)

    @property
    def trimestre(self):
        return (self.date_facture.month - 1) // 3 + 1 if self.date_facture else None

    @property
    def annee(self):
        return self.date_facture.year if self.date_facture else None


class FactureClient(InvoiceFields, TrackedModel):
    class Paiement(models.TextChoices):
        NON_PAYE = "non_paye", "Non payé"
        PARTIEL = "partiel", "Partiel"
        PAYE = "paye", "Payé"

    date_facture = models.DateField()
    dossier = models.ForeignKey("orders.DossierAdministratif", on_delete=models.PROTECT, related_name="factures_clients")
    statut_paiement = models.CharField(max_length=20, choices=Paiement.choices, default=Paiement.NON_PAYE)
