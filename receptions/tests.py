from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PIL import Image
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from documents.models import Document
from orders.models import CommandeFournisseur, DossierAdministratif
from suppliers.models import Fournisseur
from .models import Reception
from .forms import ReceptionForm


class ReceptionPageTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        override = self.settings(MEDIA_ROOT=self.temp.name)
        override.enable()
        self.addCleanup(override.disable)
        self.user = get_user_model().objects.create_user(username="interne")
        self.user.groups.add(Group.objects.get(name="Utilisateur interne"))
        self.admin = get_user_model().objects.create_user(username="admin")
        self.admin.groups.add(Group.objects.get(name="Administrateur"))
        self.supplier = self.make(Fournisseur, nom="Fournisseur")
        self.dossier = self.make(DossierAdministratif, reference_odoo="SO1", nom_client="Client", statut="Libre")
        self.order = self.make(CommandeFournisseur, numero="PO1", fournisseur=self.supplier, dossier=self.dossier, date=date(2026,9,9))
        self.reception = self.make(Reception, reference="REC1", fournisseur=self.supplier, receptionne_par=self.admin, date_reception=timezone.now(), etat_colis="Bon", statut="Libre")
        self.payload = dict(reference="REC2", fournisseur=self.supplier.pk, receptionne_par=self.admin.pk, date_reception="2026-09-09T10:30:00", etat_colis="Bon", statut="Libre", commande="", dossier="", tracking="", commentaire="")
        self.urls = [reverse("receptions:list"), reverse("receptions:detail", args=[self.reception.pk]), reverse("receptions:create"), reverse("receptions:update", args=[self.reception.pk])]

    def make(self, model, **kwargs):
        obj = model(**kwargs)
        obj.save(user=self.user)
        return obj

    def photo(self):
        data = BytesIO()
        Image.new("RGB", (4,4), "green").save(data, format="PNG")
        return SimpleUploadedFile("colis.png", data.getvalue(), content_type="image/png")

    def test_groups_and_anonymous_access(self):
        for url in self.urls:
            self.assertTrue(self.client.get(url).url.startswith("/connexion/?next="))
        for user in (self.user, self.admin):
            self.client.force_login(user)
            for url in self.urls:
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_denied_and_read_only(self):
        reader = get_user_model().objects.create_user(username="lecture")
        self.client.force_login(reader)
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code,403)
        reader.user_permissions.add(Permission.objects.get(codename="view_reception"))
        for url in self.urls[:2]:
            response = self.client.get(url)
            self.assertEqual(response.status_code,200)
            self.assertNotContains(response,self.urls[2])
            self.assertNotContains(response,self.urls[3])
        for url in self.urls[2:]:
            self.assertEqual(self.client.post(url,self.payload).status_code,403)

    def test_optional_relations_photo_and_audit(self):
        self.client.force_login(self.user)
        response = self.client.post(self.urls[2], {**self.payload,"created_by":self.admin.pk,"updated_by":self.admin.pk})
        obj=Reception.objects.get(reference="REC2")
        self.assertRedirects(response,reverse("receptions:detail",args=[obj.pk]))
        self.assertIsNone(obj.commande_id)
        self.assertIsNone(obj.dossier_id)
        self.assertFalse(obj.documents.exists())
        self.assertEqual(obj.created_by,self.user)
        self.assertEqual(obj.updated_by,self.user)
        self.assertEqual(obj.receptionne_par,self.admin)

    def test_update_preserves_creation(self):
        self.client.force_login(self.admin)
        created=self.reception.created_at
        response=self.client.post(self.urls[3],self.payload)
        self.assertEqual(response.status_code,302)
        self.reception.refresh_from_db()
        self.assertEqual(self.reception.created_at,created)
        self.assertEqual(self.reception.created_by,self.user)
        self.assertEqual(self.reception.updated_by,self.admin)
        self.assertContains(self.client.get(self.urls[3]),'value="2026-09-09T10:30:00"')

    def test_required_and_invalid_fields(self):
        self.client.force_login(self.user)
        for field,value in (("reference",""),("fournisseur",""),("receptionne_par",""),("etat_colis",""),("statut",""),("date_reception","incorrect"),("commande",99999),("dossier",99999)):
            response=self.client.post(self.urls[2],{**self.payload,field:value})
            self.assertEqual(response.status_code,200)
            self.assertIn(field,response.context["form"].errors)
        self.assertNotIn("quantite",ReceptionForm().fields)

    def test_relation_coherence(self):
        self.client.force_login(self.user)
        other=self.make(Fournisseur,nom="Autre")
        for fields,error in (({"commande":self.order.pk},"dossier"),({"commande":self.order.pk,"dossier":self.dossier.pk,"fournisseur":other.pk},"fournisseur")):
            response=self.client.post(self.urls[2],{**self.payload,**fields})
            self.assertIn(error,response.context["form"].errors)
        self.assertEqual(self.client.post(self.urls[2],{**self.payload,"commande":self.order.pk,"dossier":self.dossier.pk}).status_code,302)

    def test_upload_and_protected_read(self):
        self.client.force_login(self.user)
        response=self.client.post(self.urls[2],{**self.payload,"photo":self.photo()})
        self.assertEqual(response.status_code,302)
        doc=Document.objects.get()
        self.assertEqual(doc.categorie,"Photo du colis")
        self.assertEqual(doc.reception.reference,"REC2")
        self.assertIsNone(doc.dossier_id)
        self.assertEqual(doc.created_by,self.user)
        self.assertEqual(doc.updated_by,self.user)
        url=reverse("documents:photo",args=[doc.pk])
        response=self.client.get(url)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response["Content-Type"],"image/png")
        self.assertTrue(b"".join(response.streaming_content).startswith(b"\x89PNG"))
        response.close()
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code,302)
        with self.settings(DEBUG=True):
            self.assertEqual(self.client.get("/media/"+doc.fichier.name).status_code,404)

    def test_document_permissions_and_forged_upload(self):
        user=get_user_model().objects.create_user(username="sans-documents")
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label="receptions"))
        self.client.force_login(user)
        self.assertNotContains(self.client.get(self.urls[2]),'name="photo"')
        self.assertEqual(self.client.post(self.urls[2],{**self.payload,"photo":self.photo()}).status_code,403)
        self.assertEqual(Reception.objects.count(),1)
        doc=self.make(Document,nom="Photo",categorie="Photo du colis",reception=self.reception,fichier=self.photo())
        self.assertEqual(self.client.get(reverse("documents:photo",args=[doc.pk])).status_code,403)
        self.assertNotContains(self.client.get(self.urls[1]),"Photos du colis")
        self.assertEqual(self.client.post(self.urls[2],self.payload).status_code,302)

    def test_invalid_image_leaves_no_reception_or_file(self):
        self.client.force_login(self.user)
        fake=SimpleUploadedFile("photo.png",b"not an image",content_type="image/png")
        response=self.client.post(self.urls[2],{**self.payload,"photo":fake})
        self.assertEqual(response.status_code,200)
        self.assertIn("photo",response.context["form"].errors)
        self.assertEqual(Reception.objects.count(),1)
        self.assertFalse(Document.objects.exists())

    def test_update_adds_photo_without_removing_existing(self):
        self.client.force_login(self.admin)
        for _ in range(2):
            self.assertEqual(self.client.post(self.urls[3],{**self.payload,"photo":self.photo()}).status_code,302)
        self.assertEqual(self.reception.documents.count(),2)
        self.assertTrue(all(d.created_by==self.admin for d in self.reception.documents.all()))

    def test_rollback_removes_written_file(self):
        self.client.force_login(self.user)
        with patch("documents.models.Document.save",side_effect=IntegrityError("test")):
            response=self.client.post(self.urls[2],{**self.payload,"photo":self.photo()})
        self.assertEqual(response.status_code,200)
        self.assertEqual(Reception.objects.count(),1)
        self.assertFalse(Document.objects.exists())
        self.assertFalse(any(f.is_file() for f in Path(self.temp.name).rglob("*")))
        self.assertIsNone(response.context["view"].object)
        self.assertIsNone(response.context["form"].instance.pk)
        self.assertContains(response, "Créer une réception")
        self.assertNotContains(response, "Modifier la réception")
        self.assertNotContains(response, 'href="/receptions/2/"')
        self.assertContains(response, 'value="REC2"')
        self.assertEqual(self.client.post(self.urls[2], self.payload).status_code, 302)

    def test_failed_update_keeps_existing_detail_link(self):
        self.client.force_login(self.user)
        with patch("documents.models.Document.save", side_effect=IntegrityError("test")):
            response = self.client.post(self.urls[3], {**self.payload, "photo": self.photo()})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Modifier la réception")
        self.assertContains(response, 'href="' + self.urls[1] + '"')
        self.reception.refresh_from_db()
        self.assertEqual(self.reception.reference, "REC1")
        self.assertFalse(Document.objects.exists())


    def test_missing_or_unrelated_document(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("documents:photo",args=[9999])).status_code,404)
        doc=self.make(Document,nom="Autre",categorie="Photo du colis",dossier=self.dossier,fichier=self.photo())
        self.assertEqual(self.client.get(reverse("documents:photo",args=[doc.pk])).status_code,404)

    def test_csrf_empty_list_and_missing_reception(self):
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for url in self.urls[2:]:
            self.assertEqual(client.post(url,self.payload).status_code,403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("receptions:detail",args=[9999])).status_code,404)
        self.reception.delete()
        self.assertContains(self.client.get(self.urls[0]),"Aucune réception pour le moment")
