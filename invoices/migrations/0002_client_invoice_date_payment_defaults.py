from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("invoices", "0001_initial")]

    operations = [
        # The existing client-invoice table is empty; no invented invoice date.
        migrations.AddField(
            model_name="factureclient",
            name="date_facture",
            field=models.DateField(),
        ),
        migrations.AlterField(
            model_name="facturefournisseur",
            name="statut_paiement",
            field=models.CharField(choices=[("a_payer", "À payer"), ("paye", "Payé")], default="a_payer", max_length=20),
        ),
        migrations.AlterField(
            model_name="factureclient",
            name="statut_paiement",
            field=models.CharField(choices=[("non_paye", "Non payé"), ("partiel", "Partiel"), ("paye", "Payé")], default="non_paye", max_length=20),
        ),
    ]
