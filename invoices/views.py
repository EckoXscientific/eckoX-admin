from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction, IntegrityError
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from documents.models import Document
from .forms import FactureFournisseurForm
from .models import FactureFournisseur


class FactureFournisseurAccessMixin(LoginRequiredMixin, PermissionRequiredMixin):
    login_url = "login"
    model = FactureFournisseur

    def get_queryset(self):
        return super().get_queryset().select_related("fournisseur", "commande", "dossier", "created_by", "updated_by")


class FactureFournisseurListView(FactureFournisseurAccessMixin, ListView):
    permission_required = "invoices.view_facturefournisseur"
    template_name = "invoices/facture_fournisseur_list.html"
    context_object_name = "facturefournisseurs"
    ordering = ("-date_facture", "-pk")


class FactureFournisseurDetailView(FactureFournisseurAccessMixin, DetailView):
    permission_required = "invoices.view_facturefournisseur"
    template_name = "invoices/facture_fournisseur_detail.html"
    context_object_name = "facturefournisseur"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pdfs"] = self.object.documents.filter(categorie="Facture fournisseur PDF").order_by("created_at", "pk") if self.request.user.has_perm("documents.view_document") else Document.objects.none()
        return context


class FactureFournisseurSaveMixin:
    form_class = FactureFournisseurForm
    template_name = "invoices/facture_fournisseur_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        allowed = self.request.user.has_perm("documents.add_document")
        if self.request.FILES.get("pdf") and not allowed:
            raise PermissionDenied
        kwargs["can_add_pdf"] = allowed
        return kwargs

    def form_valid(self, form):
        document = None
        creating = form.instance._state.adding
        try:
            with transaction.atomic():
                self.object = form.save(commit=False)
                self.object.save(user=self.request.user)
                pdf = form.cleaned_data.get("pdf")
                if pdf:
                    document = Document(nom=pdf.name[:255], categorie="Facture fournisseur PDF", facture_fournisseur=self.object)
                    document.fichier.save(pdf.name, pdf, save=False)
                    document.save(user=self.request.user)
        except Exception as error:
            # A database rollback does not remove the file written by storage.
            if document and document.fichier and document.fichier._committed:
                document.fichier.delete(save=False)
            if isinstance(error, (ValidationError, IntegrityError, OSError)):
                if creating:
                    form.instance.pk = None
                    form.instance._state.adding = True
                    self.object = None
                form.add_error(None, "La facture n’a pas été enregistrée. Vérifiez les informations et réessayez.")
                return self.form_invalid(form)
            raise
        return HttpResponseRedirect(reverse("invoices:detail", kwargs={"pk": self.object.pk}))


class FactureFournisseurCreateView(FactureFournisseurAccessMixin, FactureFournisseurSaveMixin, CreateView):
    permission_required = ("invoices.view_facturefournisseur", "invoices.add_facturefournisseur")


class FactureFournisseurUpdateView(FactureFournisseurAccessMixin, FactureFournisseurSaveMixin, UpdateView):
    permission_required = ("invoices.view_facturefournisseur", "invoices.change_facturefournisseur")
