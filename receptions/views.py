from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction, IntegrityError
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from documents.models import Document
from .forms import ReceptionForm
from .models import Reception


class ReceptionAccessMixin(LoginRequiredMixin, PermissionRequiredMixin):
    login_url = "login"
    model = Reception

    def get_queryset(self):
        return super().get_queryset().select_related("fournisseur", "commande", "dossier", "receptionne_par", "created_by", "updated_by")


class ReceptionListView(ReceptionAccessMixin, ListView):
    permission_required = "receptions.view_reception"
    template_name = "receptions/reception_list.html"
    context_object_name = "receptions"
    ordering = ("-date_reception", "-pk")


class ReceptionDetailView(ReceptionAccessMixin, DetailView):
    permission_required = "receptions.view_reception"
    template_name = "receptions/reception_detail.html"
    context_object_name = "reception"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["photos"] = self.object.documents.filter(categorie="Photo du colis").order_by("created_at", "pk") if self.request.user.has_perm("documents.view_document") else Document.objects.none()
        return context


class ReceptionSaveMixin:
    form_class = ReceptionForm
    template_name = "receptions/reception_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        allowed = self.request.user.has_perm("documents.add_document")
        if self.request.FILES.get("photo") and not allowed:
            raise PermissionDenied
        kwargs["can_add_photo"] = allowed
        return kwargs

    def form_valid(self, form):
        document = None
        creating = form.instance._state.adding
        try:
            with transaction.atomic():
                self.object = form.save(commit=False)
                self.object.save(user=self.request.user)
                photo = form.cleaned_data.get("photo")
                if photo:
                    document = Document(nom=photo.name[:255], categorie="Photo du colis", reception=self.object)
                    document.fichier.save(photo.name, photo, save=False)
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
                form.add_error(None, "La réception n’a pas été enregistrée. Vérifiez les informations et réessayez.")
                return self.form_invalid(form)
            raise
        return HttpResponseRedirect(reverse("receptions:detail", kwargs={"pk": self.object.pk}))


class ReceptionCreateView(ReceptionAccessMixin, ReceptionSaveMixin, CreateView):
    permission_required = ("receptions.view_reception", "receptions.add_reception")


class ReceptionUpdateView(ReceptionAccessMixin, ReceptionSaveMixin, UpdateView):
    permission_required = ("receptions.view_reception", "receptions.change_reception")
