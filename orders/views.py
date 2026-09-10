from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from .forms import CommandeForm, DossierForm
from .models import CommandeFournisseur, DossierAdministratif


class DossierAccessMixin(LoginRequiredMixin, PermissionRequiredMixin):
    login_url = "login"
    model = DossierAdministratif


class DossierListView(DossierAccessMixin, ListView):
    permission_required = "orders.view_dossieradministratif"
    template_name = "orders/dossier_list.html"
    context_object_name = "dossiers"
    ordering = ("-created_at", "-pk")


class DossierDetailView(DossierAccessMixin, DetailView):
    permission_required = "orders.view_dossieradministratif"
    template_name = "orders/dossier_detail.html"
    context_object_name = "dossier"

    def get_queryset(self):
        return super().get_queryset().select_related("created_by", "updated_by")


    def get_context_data(self, **kwargs):
        from receptions.models import Reception
        from invoices.models import FactureFournisseur

        context = super().get_context_data(**kwargs)
        user = self.request.user
        dossier = self.object
        context["commandes_liees"] = dossier.commandes_fournisseurs.select_related("fournisseur").order_by("-date", "-pk") if user.has_perm("orders.view_commandefournisseur") else ()
        context["receptions_liees"] = Reception.objects.filter(dossier=dossier).select_related("fournisseur", "receptionne_par").order_by("-date_reception", "-pk") if user.has_perm("receptions.view_reception") else ()
        context["factures_liees"] = FactureFournisseur.objects.filter(dossier=dossier).select_related("fournisseur").order_by("-date_facture", "-pk") if user.has_perm("invoices.view_facturefournisseur") else ()
        context["documents_directs"] = dossier.documents.order_by("nom", "pk") if user.has_perm("documents.view_document") else ()
        return context


class DossierSaveMixin:
    form_class = DossierForm
    template_name = "orders/dossier_form.html"

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.save(user=self.request.user)
        return HttpResponseRedirect(reverse("orders:dossier_detail", kwargs={"pk": self.object.pk}))


class DossierCreateView(DossierAccessMixin, DossierSaveMixin, CreateView):
    permission_required = ("orders.view_dossieradministratif", "orders.add_dossieradministratif")


class DossierUpdateView(DossierAccessMixin, DossierSaveMixin, UpdateView):
    permission_required = ("orders.view_dossieradministratif", "orders.change_dossieradministratif")


class CommandeAccessMixin(LoginRequiredMixin, PermissionRequiredMixin):
    login_url = "login"
    model = CommandeFournisseur

    def get_queryset(self):
        return super().get_queryset().select_related("fournisseur", "dossier", "created_by", "updated_by")


class CommandeListView(CommandeAccessMixin, ListView):
    permission_required = "orders.view_commandefournisseur"
    template_name = "orders/commande_list.html"
    context_object_name = "commandes"
    ordering = ("-created_at", "-pk")


class CommandeDetailView(CommandeAccessMixin, DetailView):
    permission_required = "orders.view_commandefournisseur"
    template_name = "orders/commande_detail.html"
    context_object_name = "commande"


class CommandeSaveMixin:
    form_class = CommandeForm
    template_name = "orders/commande_form.html"

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.save(user=self.request.user)
        return HttpResponseRedirect(reverse("orders:commande_detail", kwargs={"pk": self.object.pk}))


class CommandeCreateView(CommandeAccessMixin, CommandeSaveMixin, CreateView):
    permission_required = ("orders.view_commandefournisseur", "orders.add_commandefournisseur")


class CommandeUpdateView(CommandeAccessMixin, CommandeSaveMixin, UpdateView):
    permission_required = ("orders.view_commandefournisseur", "orders.change_commandefournisseur")
