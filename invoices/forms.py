from pathlib import Path
from django import forms
from .models import FactureFournisseur


class FactureFournisseurForm(forms.ModelForm):
    pdf = forms.FileField(label="Document PDF", required=False, widget=forms.FileInput(attrs={"accept": ".pdf,application/pdf"}))

    class Meta:
        model = FactureFournisseur
        fields = ("numero", "fournisseur", "commande", "dossier", "date_facture", "montant", "devise", "statut_traitement", "statut_paiement", "commentaire")
        labels = {"numero": "Numéro de facture", "fournisseur": "Fournisseur", "commande": "Commande fournisseur", "dossier": "Dossier administratif", "date_facture": "Date de facture", "montant": "Montant", "devise": "Devise", "statut_traitement": "Statut de traitement", "statut_paiement": "Statut de paiement", "commentaire": "Commentaire"}
        widgets = {"date_facture": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}), "commentaire": forms.Textarea(attrs={"rows": 5})}
        error_messages = {"fournisseur": {"required": "Sélectionnez un fournisseur."}, "numero": {"required": "Indiquez le numéro de facture."}, "date_facture": {"required": "Indiquez la date de facture."}, "montant": {"required": "Indiquez le montant."}}

    def __init__(self, *args, can_add_pdf=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not can_add_pdf:
            self.fields.pop("pdf")
        for name in ("fournisseur", "commande", "dossier", "statut_traitement", "statut_paiement"):
            self.fields[name].widget.attrs["style"] = "font:inherit;display:block;width:100%;border:1px solid #aabcc6;border-radius:6px;padding:10px 12px;background:#fff;color:#183344"
        self.fields["fournisseur"].queryset = self.fields["fournisseur"].queryset.order_by("nom", "pk")
        self.fields["commande"].queryset = self.fields["commande"].queryset.order_by("numero", "pk")
        self.fields["dossier"].queryset = self.fields["dossier"].queryset.order_by("reference_odoo")
        self.fields["commande"].empty_label = "Aucune commande"
        self.fields["dossier"].empty_label = "Aucun dossier"

    def clean_pdf(self):
        pdf = self.cleaned_data.get("pdf")
        if pdf:
            signature = pdf.read(5)
            pdf.seek(0)
            if Path(pdf.name).suffix.lower() != ".pdf" or signature != b"%PDF-":
                raise forms.ValidationError("Sélectionnez un fichier PDF avec une extension et une signature valides.")
        return pdf
