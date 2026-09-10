from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import Client, TestCase
from django.urls import reverse
from .forms import DossierForm
from .models import DossierAdministratif


class DossierPageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="interne", password="test-password-123")
        self.user.groups.add(Group.objects.get(name="Utilisateur interne"))
        self.admin = get_user_model().objects.create_user(username="gestionnaire")
        self.admin.groups.add(Group.objects.get(name="Administrateur"))
        self.dossier = DossierAdministratif(reference_odoo="SO100", nom_client="Client test", statut="À suivre")
        self.dossier.save(user=self.user)
        self.payload = dict(reference_odoo="SO200", nom_client="Autre client", transporteur="", statut="Statut libre", observations="Note")

    def urls(self):
        return [reverse("orders:dossier_list"), reverse("orders:dossier_detail", args=[self.dossier.pk]), reverse("orders:dossier_create"), reverse("orders:dossier_update", args=[self.dossier.pk])]

    def test_anonymous_redirects_to_application_login(self):
        for url in self.urls():
            for method in (self.client.get, self.client.post):
                response = method(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith("/connexion/?next="))

    def test_no_permissions_returns_403(self):
        user = get_user_model().objects.create_user(username="sans-droits")
        self.client.force_login(user)
        for url in self.urls():
            self.assertEqual(self.client.get(url).status_code, 403)
        for url in self.urls()[2:]:
            self.assertEqual(self.client.post(url, self.payload).status_code, 403)
        self.assertEqual(DossierAdministratif.objects.count(), 1)

    def test_groups_can_access_pages(self):
        for user in (self.user, self.admin):
            self.client.force_login(user)
            for url in self.urls():
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_view_only_cannot_create_or_modify(self):
        reader = get_user_model().objects.create_user(username="lecture")
        reader.user_permissions.add(Permission.objects.get(codename="view_dossieradministratif"))
        self.client.force_login(reader)
        for url in self.urls()[:2]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, reverse("orders:dossier_create"))
            self.assertNotContains(response, reverse("orders:dossier_update", args=[self.dossier.pk]))
        for url in self.urls()[2:]:
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, self.payload).status_code, 403)

    def test_create_sets_authenticated_author_and_ignores_forged_fields(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("orders:dossier_create"), {**self.payload, "created_by": self.admin.pk, "updated_by": self.admin.pk})
        created = DossierAdministratif.objects.get(reference_odoo="SO200")
        self.assertRedirects(response, reverse("orders:dossier_detail", args=[created.pk]))
        self.assertEqual(created.created_by, self.user)
        self.assertEqual(created.updated_by, self.user)
        self.assertEqual(created.statut, "Statut libre")

    def test_update_preserves_creation_and_records_editor(self):
        self.client.force_login(self.admin)
        created_at = self.dossier.created_at
        response = self.client.post(reverse("orders:dossier_update", args=[self.dossier.pk]), self.payload)
        self.assertEqual(response.status_code, 302)
        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.created_by, self.user)
        self.assertEqual(self.dossier.created_at, created_at)
        self.assertEqual(self.dossier.updated_by, self.admin)
        self.assertEqual(self.dossier.reference_odoo, "SO200")

    def test_required_and_duplicate_errors_are_displayed(self):
        self.client.force_login(self.user)
        url = reverse("orders:dossier_create")
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Indiquez la référence Odoo.")
        response = self.client.post(url, {**self.payload, "reference_odoo": "SO100"})
        self.assertContains(response, "Un dossier utilise déjà cette référence Odoo.")
        self.assertEqual(DossierAdministratif.objects.count(), 1)

    def test_edit_unchanged_reference_and_optional_fields(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("orders:dossier_update", args=[self.dossier.pk]), dict(reference_odoo="SO100", nom_client="Client", statut="Libre"))
        self.assertEqual(response.status_code, 302)

    def test_form_exposes_only_business_fields(self):
        self.assertEqual(set(DossierForm().fields), {"reference_odoo", "nom_client", "statut", "transporteur", "observations"})

    def test_missing_dossier_and_escaped_content(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("orders:dossier_detail", args=[9999])).status_code, 404)
        self.dossier.observations = "<script>alert(1)</script>"
        self.dossier.save(user=self.user)
        response = self.client.get(reverse("orders:dossier_detail", args=[self.dossier.pk]))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>")

    def test_empty_list(self):
        self.dossier.delete()
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("orders:dossier_list")), "Aucun dossier pour le moment")

    def test_native_login_and_next(self):
        target = reverse("orders:dossier_detail", args=[self.dossier.pk])
        self.assertContains(self.client.get(reverse("login")), "Se connecter")
        response = self.client.post(reverse("login"), dict(username="interne", password="test-password-123", next=target))
        self.assertRedirects(response, target)
        self.assertFalse(self.user.is_staff)

    def test_login_rejects_bad_password_and_external_redirect(self):
        response = self.client.post(reverse("login"), dict(username="interne", password="incorrect"))
        self.assertContains(response, "Le nom d’utilisateur ou le mot de passe est incorrect.")
        response = self.client.post(reverse("login"), dict(username="interne", password="test-password-123", next="https://example.org/"))
        self.assertRedirects(response, reverse("orders:dossier_list"))

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(reverse("login"), dict(username="interne", password="test-password-123"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_csrf_required_on_login_and_save(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("login"), {}).status_code, 403)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse("orders:dossier_create"), self.payload).status_code, 403)
        self.assertEqual(client.post(reverse("orders:dossier_update", args=[self.dossier.pk]), self.payload).status_code, 403)


from datetime import date
from django.utils import timezone
from suppliers.models import Fournisseur
from receptions.models import Reception
from invoices.models import FactureFournisseur
from .models import CommandeFournisseur
from .forms import CommandeForm


class CommandePageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="interne")
        self.user.groups.add(Group.objects.get(name="Utilisateur interne"))
        self.admin = get_user_model().objects.create_user(username="admin")
        self.admin.groups.add(Group.objects.get(name="Administrateur"))
        self.supplier = Fournisseur(nom="Fournisseur A")
        self.supplier.save(user=self.user)
        self.dossier = DossierAdministratif(reference_odoo="SO1", nom_client="Client", statut="Libre")
        self.dossier.save(user=self.user)
        self.order = CommandeFournisseur(numero="PO1", fournisseur=self.supplier, date=date(2026, 9, 9))
        self.order.save(user=self.user)
        self.payload = dict(numero="PO2", fournisseur=self.supplier.pk, dossier="", date="2026-09-09", date_prevue="", statut="commandee", commentaire="Texte")
        self.urls = [reverse("orders:commande_list"), reverse("orders:commande_detail", args=[self.order.pk]), reverse("orders:commande_create"), reverse("orders:commande_update", args=[self.order.pk])]

    def test_anonymous_and_denied_access(self):
        for url in self.urls:
            self.assertTrue(self.client.get(url).url.startswith("/connexion/?next="))
        for url in self.urls[2:]:
            self.assertEqual(self.client.post(url, self.payload).status_code, 302)
        denied = get_user_model().objects.create_user(username="sans-droits")
        self.client.force_login(denied)
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 403)
        for url in self.urls[2:]:
            self.assertEqual(self.client.post(url, self.payload).status_code, 403)
        self.assertEqual(CommandeFournisseur.objects.count(), 1)

    def test_both_groups_access_pages(self):
        for user in (self.user, self.admin):
            self.client.force_login(user)
            for url in self.urls:
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_read_only_permissions(self):
        reader = get_user_model().objects.create_user(username="lecture")
        reader.user_permissions.add(Permission.objects.get(codename="view_commandefournisseur"))
        self.client.force_login(reader)
        for url in self.urls[:2]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, self.urls[2])
            self.assertNotContains(response, self.urls[3])
        for url in self.urls[2:]:
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, self.payload).status_code, 403)

    def test_create_with_optional_dossier_and_authenticated_author(self):
        self.client.force_login(self.user)
        for dossier in ("", self.dossier.pk):
            response = self.client.post(self.urls[2], {**self.payload, "dossier": dossier, "created_by": self.admin.pk, "updated_by": self.admin.pk})
            obj = CommandeFournisseur.objects.latest("pk")
            self.assertRedirects(response, reverse("orders:commande_detail", args=[obj.pk]))
            self.assertEqual(obj.dossier_id, dossier or None)
            self.assertEqual(obj.created_by, self.user)
            self.assertEqual(obj.updated_by, self.user)
        self.assertEqual(CommandeFournisseur.objects.filter(numero="PO2").count(), 2)

    def test_update_and_trace(self):
        self.client.force_login(self.admin)
        created_at = self.order.created_at
        response = self.client.post(self.urls[3], {**self.payload, "statut": "expediee", "date_prevue": "2026-09-15", "dossier": self.dossier.pk})
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.created_by, self.user)
        self.assertEqual(self.order.created_at, created_at)
        self.assertEqual(self.order.updated_by, self.admin)
        self.assertEqual(self.order.statut, "expediee")
        response = self.client.get(self.urls[3])
        self.assertContains(response, 'value="2026-09-15"')
        self.assertContains(response, 'value="2026-09-09"')

    def test_invalid_fields_do_not_save(self):
        self.client.force_login(self.user)
        for field, value in (("fournisseur", ""), ("fournisseur", 99999), ("dossier", 99999), ("date", "incorrect"), ("statut", "inconnu"), ("numero", "")):
            response = self.client.post(self.urls[2], {**self.payload, field: value})
            self.assertEqual(response.status_code, 200)
            self.assertIn(field, response.context["form"].errors)
        self.assertEqual(CommandeFournisseur.objects.count(), 1)

    def test_statuts_and_form_scope(self):
        self.assertEqual(set(CommandeForm().fields), {"numero", "fournisseur", "dossier", "date", "date_prevue", "statut", "commentaire"})
        self.client.force_login(self.user)
        for statut in ("commandee", "expediee", "recue"):
            self.assertEqual(self.client.post(self.urls[3], {**self.payload, "statut": statut}).status_code, 302)
            self.order.refresh_from_db()
            self.assertEqual(self.order.statut, statut)

    def test_existing_children_prevent_inconsistent_edit(self):
        self.client.force_login(self.user)
        self.order.dossier = self.dossier
        self.order.save(user=self.user)
        other = Fournisseur(nom="Autre")
        other.save(user=self.user)
        dossier = DossierAdministratif(reference_odoo="SO2", nom_client="Autre", statut="Libre")
        dossier.save(user=self.user)
        children = [Reception(reference="REC1", fournisseur=self.supplier, commande=self.order, dossier=self.dossier, date_reception=timezone.now(), receptionne_par=self.user, etat_colis="Bon", statut="Reçu"), FactureFournisseur(numero="INV1", fournisseur=self.supplier, commande=self.order, dossier=self.dossier, date_facture=date(2026,9,9), montant=10)]
        for child in children:
            child.save(user=self.user)
            for field, value in (("fournisseur", other.pk), ("dossier", dossier.pk)):
                response = self.client.post(self.urls[3], {**self.payload, "dossier": self.dossier.pk, field: value})
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context["form"].errors)
            child.delete()
        self.order.refresh_from_db()
        self.assertEqual(self.order.fournisseur, self.supplier)
        self.assertEqual(self.order.dossier, self.dossier)

    def test_empty_list_missing_order_and_csrf(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("orders:commande_detail", args=[99999])).status_code, 404)
        secure_client = Client(enforce_csrf_checks=True)
        secure_client.force_login(self.user)
        for url in self.urls[2:]:
            self.assertEqual(secure_client.post(url, self.payload).status_code, 403)
        self.order.delete()
        self.assertContains(self.client.get(self.urls[0]), "Aucune commande pour le moment")


from documents.models import Document


class DossierOverviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="overview")
        self.user.groups.add(Group.objects.get(name="Utilisateur interne"))
        self.dossier = self.make(DossierAdministratif, reference_odoo="SO-OVERVIEW", nom_client="Client", statut="En cours")
        self.other = self.make(DossierAdministratif, reference_odoo="SO-OTHER", nom_client="Autre", statut="En cours")
        self.supplier = self.make(Fournisseur, nom="Fournisseur")
        for dossier, suffix in ((self.dossier,"LINKED"),(self.other,"OTHER")):
            order = self.make(CommandeFournisseur, numero="PO-"+suffix, fournisseur=self.supplier, dossier=dossier, date=date(2026,9,10))
            self.make(Reception, reference="REC-"+suffix, fournisseur=self.supplier, dossier=dossier, date_reception=timezone.now(), receptionne_par=self.user, etat_colis="Bon", statut="Reçu")
            self.make(FactureFournisseur, numero="INV-"+suffix, fournisseur=self.supplier, dossier=dossier, date_facture=date(2026,9,10), montant=10)
            self.make(Document, nom="DOC-"+suffix, categorie="Export", dossier=dossier, fichier="demo.pdf")
            self.make(Document, nom="INDIRECT-"+suffix, categorie="Bon de commande", commande=order, fichier="indirect.pdf")
        self.url=reverse("orders:dossier_detail",args=[self.dossier.pk])

    def make(self,model,**values):
        obj=model(**values); obj.save(user=self.user); return obj

    def test_only_direct_links_and_detail_urls(self):
        self.client.force_login(self.user)
        response=self.client.get(self.url)
        self.assertEqual(response.status_code,200)
        for prefix in ("PO-","REC-","INV-","DOC-"):
            self.assertContains(response,prefix+"LINKED")
            self.assertNotContains(response,prefix+"OTHER")
        self.assertNotContains(response,"INDIRECT-")
        self.assertContains(response,reverse("orders:commande_detail",args=[CommandeFournisseur.objects.get(numero="PO-LINKED").pk]))
        self.assertContains(response,reverse("receptions:detail",args=[Reception.objects.get(reference="REC-LINKED").pk]))
        self.assertContains(response,reverse("invoices:detail",args=[FactureFournisseur.objects.get(numero="INV-LINKED").pk]))

    def test_permissions_hide_sections_and_data(self):
        reader=get_user_model().objects.create_user(username="reader")
        reader.user_permissions.add(Permission.objects.get(codename="view_dossieradministratif"))
        self.client.force_login(reader)
        response=self.client.get(self.url)
        for heading in ("Commandes fournisseurs liées","Réceptions liées","Factures fournisseurs liées","Documents du dossier"):
            self.assertNotContains(response,heading)
        for prefix in ("PO-","REC-","INV-","DOC-"):
            self.assertNotContains(response,prefix+"LINKED")
        for key in ("commandes_liees","receptions_liees","factures_liees","documents_directs"):
            self.assertEqual(response.context[key],())

    def test_each_permission_independently(self):
        for permission,visible in (("view_commandefournisseur","PO-"),("view_reception","REC-"),("view_facturefournisseur","INV-"),("view_document","DOC-")):
            reader=get_user_model().objects.create_user(username=permission)
            reader.user_permissions.add(Permission.objects.get(codename="view_dossieradministratif"),Permission.objects.get(codename=permission))
            self.client.force_login(reader)
            response=self.client.get(self.url)
            for prefix in ("PO-","REC-","INV-","DOC-"):
                if prefix==visible: self.assertContains(response,prefix+"LINKED")
                else: self.assertNotContains(response,prefix+"LINKED")

    def test_empty_sections(self):
        empty=self.make(DossierAdministratif,reference_odoo="SO-EMPTY",nom_client="Vide",statut="Libre")
        self.client.force_login(self.user)
        response=self.client.get(reverse("orders:dossier_detail",args=[empty.pk]))
        for text in ("Aucune commande fournisseur liée","Aucune réception liée","Aucune facture fournisseur liée","Aucun document directement rattaché"):
            self.assertContains(response,text)

    def test_read_does_not_modify_audit(self):
        before=(self.dossier.created_at,self.dossier.updated_at,self.dossier.updated_by_id)
        self.client.force_login(self.user); self.client.get(self.url)
        self.dossier.refresh_from_db()
        self.assertEqual(before,(self.dossier.created_at,self.dossier.updated_at,self.dossier.updated_by_id))
