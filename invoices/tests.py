from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase, Client
from django.urls import reverse
from suppliers.models import Fournisseur
from orders.models import DossierAdministratif, CommandeFournisseur
from documents.models import Document
from .models import FactureFournisseur
from .forms import FactureFournisseurForm


class FactureFournisseurPageTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        setting=self.settings(MEDIA_ROOT=self.temp.name)
        setting.enable()
        self.addCleanup(setting.disable)
        self.user=get_user_model().objects.create_user(username="interne")
        self.user.groups.add(Group.objects.get(name="Utilisateur interne"))
        self.admin=get_user_model().objects.create_user(username="admin")
        self.admin.groups.add(Group.objects.get(name="Administrateur"))
        self.supplier=self.make(Fournisseur,nom="Fournisseur")
        self.dossier=self.make(DossierAdministratif,reference_odoo="SO1",nom_client="Client",statut="Libre")
        self.order=self.make(CommandeFournisseur,numero="PO1",fournisseur=self.supplier,dossier=self.dossier,date=date(2026,9,10))
        self.invoice=self.make(FactureFournisseur,numero="INV1",fournisseur=self.supplier,date_facture=date(2026,9,10),montant=10)
        self.data=dict(numero="INV2",fournisseur=self.supplier.pk,commande="",dossier="",date_facture="2026-09-10",montant="24.50",devise="",statut_traitement="a_traiter",statut_paiement="a_payer",commentaire="")
        self.urls=[reverse("invoices:list"),reverse("invoices:detail",args=[self.invoice.pk]),reverse("invoices:create"),reverse("invoices:update",args=[self.invoice.pk])]

    def make(self,model,**kwargs):
        obj=model(**kwargs); obj.save(user=self.user); return obj

    def pdf(self):
        return SimpleUploadedFile("facture.pdf",b"%PDF-1.4\n%%EOF",content_type="application/pdf")

    def test_access_permissions(self):
        for url in self.urls:
            self.assertTrue(self.client.get(url).url.startswith("/connexion/?next="))
        for user in (self.user,self.admin):
            self.client.force_login(user)
            for url in self.urls:
                self.assertEqual(self.client.get(url).status_code,200)
        denied=get_user_model().objects.create_user(username="sans-droits")
        self.client.force_login(denied)
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code,403)
        for url in self.urls[2:]:
            self.assertEqual(self.client.post(url,self.data).status_code,403)

    def test_read_only(self):
        user=get_user_model().objects.create_user(username="lecture")
        user.user_permissions.add(Permission.objects.get(codename="view_facturefournisseur"))
        self.client.force_login(user)
        for url in self.urls[:2]:
            r=self.client.get(url); self.assertEqual(r.status_code,200)
            self.assertNotContains(r,self.urls[2]); self.assertNotContains(r,self.urls[3])
        for url in self.urls[2:]:
            self.assertEqual(self.client.post(url,self.data).status_code,403)

    def test_create_optional_relations_and_authors(self):
        self.client.force_login(self.user)
        for relation in ({},{"commande":self.order.pk,"dossier":self.dossier.pk}):
            r=self.client.post(self.urls[2],{**self.data,**relation,"created_by":self.admin.pk,"updated_by":self.admin.pk})
            obj=FactureFournisseur.objects.latest("pk")
            self.assertRedirects(r,reverse("invoices:detail",args=[obj.pk]))
            self.assertEqual(obj.created_by,self.user); self.assertEqual(obj.updated_by,self.user)
            self.assertEqual(obj.commande_id,relation.get("commande"))
            self.assertEqual(obj.devise,"")
        self.assertEqual(FactureFournisseur.objects.filter(numero="INV2").count(),2)

    def test_update_and_computed_period(self):
        self.client.force_login(self.admin)
        original=self.invoice.created_at
        r=self.client.post(self.urls[3],{**self.data,"date_facture":"2027-01-15","statut_traitement":"traitee","statut_paiement":"paye","devise":"USD"})
        self.assertEqual(r.status_code,302)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.created_at,original); self.assertEqual(self.invoice.created_by,self.user)
        self.assertEqual(self.invoice.updated_by,self.admin)
        self.assertEqual(self.invoice.trimestre,1); self.assertEqual(self.invoice.annee,2027)
        self.assertContains(self.client.get(self.urls[1]),"T1 2027")
        self.assertContains(self.client.get(self.urls[3]),'value="2027-01-15"')

    def test_defaults_and_fields(self):
        form=FactureFournisseurForm()
        self.assertEqual(form["statut_traitement"].value(),"a_traiter")
        self.assertEqual(form["statut_paiement"].value(),"a_payer")
        self.assertEqual(set(form.fields),set(self.data))

    def test_validation(self):
        self.client.force_login(self.user)
        for field,value in (("fournisseur",""),("numero",""),("montant","abc"),("date_facture","incorrect"),("devise","EURO"),("statut_traitement","inconnu"),("statut_paiement","inconnu"),("commande",99999),("dossier",99999)):
            r=self.client.post(self.urls[2],{**self.data,field:value})
            self.assertEqual(r.status_code,200); self.assertIn(field,r.context["form"].errors)
        self.assertEqual(FactureFournisseur.objects.count(),1)

    def test_coherence(self):
        self.client.force_login(self.user)
        other=self.make(Fournisseur,nom="Autre")
        for fields,key in (({"commande":self.order.pk},"dossier"),({"commande":self.order.pk,"dossier":self.dossier.pk,"fournisseur":other.pk},"fournisseur")):
            r=self.client.post(self.urls[2],{**self.data,**fields})
            self.assertIn(key,r.context["form"].errors)

    def test_pdf_upload_read_and_owner(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.urls[2],{**self.data,"pdf":self.pdf()}).status_code,302)
        d=Document.objects.get()
        self.assertEqual(d.categorie,"Facture fournisseur PDF"); self.assertEqual(d.facture_fournisseur.numero,"INV2")
        self.assertIsNone(d.dossier_id); self.assertIsNone(d.reception_id)
        self.assertEqual(d.created_by,self.user); self.assertEqual(d.updated_by,self.user)
        url=reverse("documents:facture_pdf",args=[d.pk]); r=self.client.get(url)
        self.assertEqual(r["Content-Type"],"application/pdf")
        self.assertTrue(b"".join(r.streaming_content).startswith(b"%PDF-")); r.close()
        self.client.logout(); self.assertEqual(self.client.get(url).status_code,302)
        with self.settings(DEBUG=True):
            self.assertEqual(self.client.get("/media/"+d.fichier.name).status_code,404)

    def test_invalid_pdf(self):
        self.client.force_login(self.user)
        for name,data in (("fake.pdf",b"invalid"),("fake.txt",b"%PDF-1.4")):
            r=self.client.post(self.urls[2],{**self.data,"pdf":SimpleUploadedFile(name,data)})
            self.assertIn("pdf",r.context["form"].errors)
        self.assertEqual(FactureFournisseur.objects.count(),1)
        self.assertFalse(Document.objects.exists())

    def test_document_permissions(self):
        user=get_user_model().objects.create_user(username="sans-documents")
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label="invoices",content_type__model="facturefournisseur"))
        self.client.force_login(user)
        self.assertNotContains(self.client.get(self.urls[2]),'name="pdf"')
        self.assertEqual(self.client.post(self.urls[2],{**self.data,"pdf":self.pdf()}).status_code,403)
        d=self.make(Document,nom="f.pdf",categorie="Facture fournisseur PDF",facture_fournisseur=self.invoice,fichier=self.pdf())
        self.assertEqual(self.client.get(reverse("documents:facture_pdf",args=[d.pk])).status_code,403)
        self.assertNotContains(self.client.get(self.urls[1]),"Documents PDF")

    def test_rollback_and_retry(self):
        self.client.force_login(self.user)
        for url in self.urls[2:]:
            with patch("documents.models.Document.save",side_effect=IntegrityError("test")):
                r=self.client.post(url,{**self.data,"pdf":self.pdf()})
            self.assertEqual(r.status_code,200)
            self.assertEqual(FactureFournisseur.objects.count(),1)
            self.assertFalse(Document.objects.exists())
            self.assertFalse(any(f.is_file() for f in Path(self.temp.name).rglob("*")))
            self.invoice.refresh_from_db(); self.assertEqual(self.invoice.numero,"INV1")
            if url==self.urls[2]:
                self.assertIsNone(r.context["view"].object)
                self.assertContains(r,"Créer une facture")
            else:
                self.assertContains(r,"Modifier la facture")
        self.assertEqual(self.client.post(self.urls[2],self.data).status_code,302)

    def test_multiple_documents_on_update(self):
        self.client.force_login(self.admin)
        for _ in range(2):
            self.assertEqual(self.client.post(self.urls[3],{**self.data,"pdf":self.pdf()}).status_code,302)
        self.assertEqual(self.invoice.documents.count(),2)

    def test_missing_empty_and_csrf(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("invoices:detail",args=[99999])).status_code,404)
        self.assertEqual(self.client.get(reverse("documents:facture_pdf",args=[99999])).status_code,404)
        c=Client(enforce_csrf_checks=True); c.force_login(self.user)
        for url in self.urls[2:]: self.assertEqual(c.post(url,self.data).status_code,403)
        self.invoice.delete(); self.assertContains(self.client.get(self.urls[0]),"Aucune facture pour le moment")
