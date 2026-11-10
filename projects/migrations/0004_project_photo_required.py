from django.db import migrations, models


class Migration(migrations.Migration):
    """Agrega la opción de foto obligatoria por proyecto (por defecto True: conserva el comportamiento actual)."""

    dependencies = [
        ("projects", "0003_projectsite_address"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="photo_required",
            field=models.BooleanField(default=True, verbose_name="Foto obligatoria al marcar"),
        ),
    ]
