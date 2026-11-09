from django.db import migrations

ROLES = ("Supervisor", "Administrador", "RRHH")


def create_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in ROLES:
        Group.objects.get_or_create(name=name)


def noop(apps, schema_editor):
    # No se eliminan los grupos al revertir para no perder asignaciones de usuarios.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [migrations.RunPython(create_groups, noop)]
