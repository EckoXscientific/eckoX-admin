from django import forms
from .models import CommandeFournisseur, DossierAdministratif


class DossierForm(forms.ModelForm):
    class Meta:
        model = DossierAdministratif
        fields = ("reference_odoo", "nom_client", "transporteur", "statut", "observations")
        labels = {"reference_odoo": "Référence de commande Odoo", "nom_client": "Nom du client", "transporteur": "Transporteur", "statut": "Statut", "observations": "Observations"}
        widgets = {"observations": forms.Textarea(attrs={"rows": 5})}
        error_messages = {
            "reference_odoo": {"required": "Indiquez la référence Odoo.", "unique": "Un dossier utilise déjà cette référence Odoo."},
            "nom_client": {"required": "Indiquez le nom du client."},
            "statut": {"required": "Indiquez le statut du dossier."},
        }


class CommandeForm(forms.ModelForm):
    class Meta:
        model = CommandeFournisseur
        fields = ("numero", "fournisseur", "dossier", "date", "date_prevue", "statut", "commentaire")
        labels = {"numero": "Numéro de commande", "fournisseur": "Fournisseur", "dossier": "Dossier administratif", "date": "Date de commande", "date_prevue": "Date prévue", "statut": "Statut", "commentaire": "Commentaire"}
        widgets = {"date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}), "date_prevue": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}), "commentaire": forms.Textarea(attrs={"rows": 5})}
        error_messages = {"fournisseur": {"required": "Sélectionnez un fournisseur."}, "numero": {"required": "Indiquez le numéro de commande."}, "date": {"required": "Indiquez la date de commande."}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fournisseur"].queryset = self.fields["fournisseur"].queryset.order_by("nom", "pk")
        self.fields["dossier"].queryset = self.fields["dossier"].queryset.order_by("reference_odoo")
        self.fields["dossier"].empty_label = "Aucun dossier"
        # Reuse existing input styling without changing the shared CSS.
        for name in ("fournisseur", "dossier", "statut"):
            self.fields[name].widget.attrs["style"] = "font:inherit;display:block;width:100%;border:1px solid #aabcc6;border-radius:6px;padding:10px 12px;background:#fff;color:#183344"
