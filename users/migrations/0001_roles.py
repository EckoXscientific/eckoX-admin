from django.db import migrations


MODELS = {
    "suppliers": ("fournisseur",),
    "orders": ("dossieradministratif", "commandefournisseur"),
    "receptions": ("reception",),
    "invoices": ("facturefournisseur", "factureclient"),
    "documents": ("document",),
}


def create_roles(apps, schema_editor):
    alias = schema_editor.connection.alias
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    internal, _ = Group.objects.using(alias).get_or_create(name="Utilisateur interne")
    admin, _ = Group.objects.using(alias).get_or_create(name="Administrateur")
    for app_label, names in {**MODELS, "auth": ("user", "group")}.items():
        for name in names:
            ct, _ = ContentType.objects.using(alias).get_or_create(app_label=app_label, model=name)
            for action in ("add", "view", "change", "delete"):
                permission, _ = Permission.objects.using(alias).get_or_create(
                    content_type=ct, codename=f"{action}_{name}",
                    defaults={"name": f"Can {action} {name}"},
                )
                admin.permissions.add(permission)
                if app_label in MODELS:
                    if action != "delete":
                        internal.permissions.add(permission)
                    else:
                        internal.permissions.remove(permission)


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        *[(app, "0001_initial") for app in MODELS],
    ]
    # Preserve accounts/groups and their assignments when rolling back schema.
    operations = [migrations.RunPython(create_roles, migrations.RunPython.noop)]
