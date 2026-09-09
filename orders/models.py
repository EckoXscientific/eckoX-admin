from django.core.exceptions import ValidationError
from django.db import models
from users.models import TrackedModel


class DossierAdministratif(TrackedModel):
    reference_odoo = models.CharField(max_length=100, unique=True)
    nom_client = models.CharField(max_length=255)
    transporteur = models.CharField(max_length=255, blank=True)
    statut = models.CharField(max_length=100)
    observations = models.TextField(blank=True)

    def __str__(self):
        return self.reference_odoo


class CommandeFournisseur(TrackedModel):
    class Statut(models.TextChoices):
        COMMANDEE = "commandee", "Commandée"
        EXPEDIEE = "expediee", "Expédiée"
        RECUE = "recue", "Reçue"

    numero = models.CharField(max_length=100)
    fournisseur = models.ForeignKey("suppliers.Fournisseur", on_delete=models.PROTECT, related_name="commandes")
    dossier = models.ForeignKey(DossierAdministratif, on_delete=models.PROTECT, null=True, blank=True, related_name="commandes_fournisseurs")
    date = models.DateField()
    date_prevue = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.COMMANDEE)
    commentaire = models.TextField(blank=True)

    def clean(self):
        super().clean()
        if self.pk:
            for related in (self.receptions, self.factures):
                if related.exclude(fournisseur_id=self.fournisseur_id).exists():
                    raise ValidationError({"fournisseur": "Le fournisseur diffère de celui d'une réception ou facture liée."})
                if self.dossier_id and related.exclude(dossier_id=self.dossier_id).exists():
                    raise ValidationError({"dossier": "Le dossier diffère de celui d'une réception ou facture liée."})

    def __str__(self):
        return self.numero


class SupplierLinkedModel(TrackedModel):
    fournisseur = models.ForeignKey("suppliers.Fournisseur", on_delete=models.PROTECT, related_name="%(app_label)s_%(class)s_items")
    commande = models.ForeignKey(CommandeFournisseur, on_delete=models.PROTECT, null=True, blank=True, related_name="%(app_label)s_%(class)s_items")
    dossier = models.ForeignKey(DossierAdministratif, on_delete=models.PROTECT, null=True, blank=True, related_name="%(app_label)s_%(class)s_items")

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if not self.commande_id:
            return
        commande = CommandeFournisseur.objects.filter(pk=self.commande_id).first()
        if commande is None:
            return  # Foreign-key validation reports the missing order.
        errors = {}
        if self.fournisseur_id != commande.fournisseur_id:
            errors["fournisseur"] = "Le fournisseur doit correspondre à celui de la commande."
        if commande.dossier_id and self.dossier_id != commande.dossier_id:
            errors["dossier"] = "Le dossier doit correspondre à celui de la commande."
        if errors:
            raise ValidationError(errors)
