from datetime import date
from decimal import Decimal
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from documents.models import Document
from invoices.models import FactureClient, FactureFournisseur
from orders.models import CommandeFournisseur, DossierAdministratif
from receptions.models import Reception
from suppliers.models import Fournisseur


class V1ModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="interne")
        self.other = get_user_model().objects.create_user(username="autre")
        self.supplier = self.make(Fournisseur, nom="Fournisseur")
        self.dossier = self.make(DossierAdministratif, reference_odoo="SO001", nom_client="Client", statut="en cours")
        self.order = self.make(CommandeFournisseur, numero="PO001", fournisseur=self.supplier, dossier=self.dossier, date=date(2026, 9, 9))

    def make(self, model, **fields):
        item = model(**fields)
        item.save(user=self.user)
        return item

    def reception(self, **fields):
        values = dict(reference="REC001", fournisseur=self.supplier, date_reception=timezone.now(), receptionne_par=self.other, etat_colis="bon", statut="reçu")
        values.update(fields)
        return self.make(Reception, **values)

    def invoice(self, **fields):
        values = dict(numero="INV001", fournisseur=self.supplier, date_facture=date(2026, 9, 9), montant=Decimal("2450.00"), statut_paiement="a_payer")
        values.update(fields)
        return self.make(FactureFournisseur, **values)

    def test_reception_without_order_photo_or_quantity(self):
        obj = self.reception()
        self.assertIsNone(obj.commande_id)
        self.assertFalse(obj.documents.exists())
        self.assertNotIn("quantite", {f.name for f in Reception._meta.fields})
        self.assertEqual(obj.receptionne_par, self.other)
        self.assertEqual(obj.created_by, self.user)

    def test_multiple_orders_receptions_invoices_and_client_invoices(self):
        self.make(CommandeFournisseur, numero="PO002", fournisseur=self.supplier, dossier=self.dossier, date=date(2026, 9, 9))
        for index in range(2):
            self.reception(reference=f"REC{index}", commande=self.order, dossier=self.dossier)
            self.invoice(numero=f"INV{index}", commande=self.order, dossier=self.dossier)
            self.make(FactureClient, date_facture=date(2026, 9, 9), numero=f"FC{index}", montant=10, dossier=self.dossier, statut_paiement="partiel")
        self.assertEqual(self.order.receptions.count(), 2)
        self.assertEqual(self.order.factures.count(), 2)
        self.assertEqual(self.dossier.commandes_fournisseurs.count(), 2)
        self.assertEqual(self.dossier.factures_clients.count(), 2)

    def test_child_consistency(self):
        supplier = self.make(Fournisseur, nom="Autre")
        for factory in (self.reception, self.invoice):
            with self.subTest(factory=factory.__name__, field="fournisseur"):
                with self.assertRaises(ValidationError):
                    factory(commande=self.order, dossier=self.dossier, fournisseur=supplier)
            with self.subTest(factory=factory.__name__, field="dossier"):
                with self.assertRaises(ValidationError):
                    factory(commande=self.order)

    def test_parent_change_checks_both_child_types(self):
        supplier = self.make(Fournisseur, nom="Autre")
        dossier = self.make(DossierAdministratif, reference_odoo="SO002", nom_client="Autre", statut="en cours")
        for factory in (self.reception, self.invoice):
            obj = factory(commande=self.order, dossier=self.dossier)
            self.order.fournisseur = supplier
            with self.assertRaises(ValidationError):
                self.order.save(user=self.user)
            self.order.refresh_from_db()
            self.order.dossier = dossier
            with self.assertRaises(ValidationError):
                self.order.save(user=self.user)
            self.order.refresh_from_db()
            obj.delete()

    def test_audit_and_partial_update(self):
        original_time = self.supplier.created_at
        self.supplier.nom = "Modifié"
        self.supplier.save(user=self.other, update_fields=["nom"])
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.created_by, self.user)
        self.assertEqual(self.supplier.updated_by, self.other)
        self.assertEqual(self.supplier.created_at, original_time)
        self.assertGreaterEqual(self.supplier.updated_at, original_time)
        self.supplier.created_by = self.other
        with self.assertRaises(ValidationError):
            self.supplier.save(user=self.other)

    def test_author_required(self):
        with self.assertRaises(ValidationError):
            Fournisseur(nom="Sans auteur").save()

    def test_quarters_and_currency_and_separate_statuses(self):
        obj = self.invoice()
        self.assertEqual(obj.devise, "")
        for month in range(1, 13):
            obj.date_facture = date(2026, month, 1)
            self.assertEqual(obj.trimestre, (month - 1) // 3 + 1)
            self.assertEqual(obj.annee, 2026)
        obj.devise = "USD"
        obj.statut_traitement = "traitee"
        obj.save(user=self.user)
        self.assertEqual(obj.statut_paiement, "a_payer")

    def test_unique_odoo_reference(self):
        with self.assertRaises(ValidationError):
            self.make(DossierAdministratif, reference_odoo="SO001", nom_client="Autre", statut="en cours")

    def test_protected_deletion(self):
        for obj in (self.supplier, self.dossier, self.user):
            with self.assertRaises(ProtectedError):
                obj.delete()
        self.reception(commande=self.order, dossier=self.dossier)
        with self.assertRaises(ProtectedError):
            self.order.delete()

    def test_documents_all_owners_and_media(self):
        reception = self.reception()
        invoice = self.invoice()
        client_invoice = self.make(FactureClient, date_facture=date(2026, 9, 9), numero="FC1", montant=10, dossier=self.dossier, statut_paiement="paye")
        owners = dict(dossier=self.dossier, commande=self.order, reception=reception, facture_fournisseur=invoice, facture_client=client_invoice)
        with TemporaryDirectory() as folder, self.settings(MEDIA_ROOT=folder):
            for name, owner in owners.items():
                with self.subTest(owner=name):
                    for i in range(2):
                        doc = self.make(Document, nom=f"Pièce {i}", categorie="À classer", fichier=SimpleUploadedFile("piece.txt", b"test"), **{name: owner})
                        self.assertTrue(doc.fichier.storage.exists(doc.fichier.name))
                    self.assertEqual(owner.documents.count(), 2)
                    with self.assertRaises(ProtectedError):
                        owner.delete()

    def test_document_exactly_one_owner_in_model_and_database(self):
        for owners in ({}, {"dossier": self.dossier, "commande": self.order}):
            with self.subTest(owners=list(owners)):
                doc = Document(nom="Pièce", categorie="Test", fichier="documents/test.pdf", created_by=self.user, updated_by=self.user, **owners)
                with self.assertRaises(ValidationError):
                    doc.save()
                with self.assertRaises(IntegrityError), transaction.atomic():
                    Document.objects.bulk_create([doc])

    def test_role_permissions(self):
        self.user.groups.add(Group.objects.get(name="Utilisateur interne"))
        self.other.groups.add(Group.objects.get(name="Administrateur"))
        for model in (Fournisseur, DossierAdministratif, CommandeFournisseur, Reception, FactureFournisseur, FactureClient, Document):
            prefix = model._meta.app_label
            name = model._meta.model_name
            for action in ("add", "view", "change"):
                self.assertTrue(self.user.has_perm(f"{prefix}.{action}_{name}"))
            self.assertFalse(self.user.has_perm(f"{prefix}.delete_{name}"))
            self.assertTrue(self.other.has_perm(f"{prefix}.delete_{name}"))
        self.assertTrue(self.other.has_perm("auth.change_user"))
        self.assertFalse(self.user.has_perm("auth.change_user"))

    def test_invoice_payment_defaults(self):
        supplier_invoice = self.make(FactureFournisseur, numero="DEFAULT-S", fournisseur=self.supplier, date_facture=date(2026, 9, 9), montant=10)
        client_invoice = self.make(FactureClient, numero="DEFAULT-C", dossier=self.dossier, date_facture=date(2026, 9, 9), montant=10)
        supplier_invoice.refresh_from_db()
        client_invoice.refresh_from_db()
        self.assertEqual(supplier_invoice.statut_paiement, "a_payer")
        self.assertEqual(client_invoice.statut_paiement, "non_paye")

    def test_client_invoice_requires_date(self):
        with self.assertRaises(ValidationError) as error:
            self.make(FactureClient, numero="NO-DATE", dossier=self.dossier, montant=10)
        self.assertIn("date_facture", error.exception.message_dict)
