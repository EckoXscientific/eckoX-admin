from django import forms
from .models import Reception


class ReceptionForm(forms.ModelForm):
    photo = forms.ImageField(label="Photo du colis", required=False, error_messages={"invalid_image": "Sélectionnez une image valide."})

    class Meta:
        model = Reception
        fields = ("reference", "date_reception", "fournisseur", "receptionne_par", "commande", "dossier", "tracking", "etat_colis", "statut", "commentaire")
        labels = {"reference": "Référence de réception", "date_reception": "Date et heure de réception", "fournisseur": "Fournisseur", "receptionne_par": "Personne ayant réceptionné", "commande": "Commande fournisseur", "dossier": "Dossier administratif", "tracking": "Numéro de tracking", "etat_colis": "État du colis", "statut": "Statut", "commentaire": "Commentaire"}
        widgets = {"date_reception": forms.DateTimeInput(format="%Y-%m-%dT%H:%M:%S", attrs={"type": "datetime-local", "step": "1"}), "commentaire": forms.Textarea(attrs={"rows": 5})}
        error_messages = {"reference": {"unique": "Cette référence de réception existe déjà.", "required": "Indiquez une référence."}, "fournisseur": {"required": "Sélectionnez un fournisseur."}, "receptionne_par": {"required": "Sélectionnez la personne ayant réceptionné."}}

    def __init__(self, *args, can_add_photo=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not can_add_photo:
            self.fields.pop("photo")
        for name in ("fournisseur", "receptionne_par", "commande", "dossier"):
            self.fields[name].widget.attrs["style"] = "font:inherit;display:block;width:100%;border:1px solid #aabcc6;border-radius:6px;padding:10px 12px;background:#fff;color:#183344"
        self.fields["fournisseur"].queryset = self.fields["fournisseur"].queryset.order_by("nom", "pk")
        self.fields["commande"].queryset = self.fields["commande"].queryset.order_by("numero", "pk")
        self.fields["dossier"].queryset = self.fields["dossier"].queryset.order_by("reference_odoo")
        self.fields["commande"].empty_label = "Aucune commande"
        self.fields["dossier"].empty_label = "Aucun dossier"
