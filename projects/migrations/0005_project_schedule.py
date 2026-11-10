from django.db import migrations, models


class Migration(migrations.Migration):
    """Jornada del proyecto: días laborales y horario (vacíos = sin restricción, conserva lo actual)."""

    dependencies = [
        ("projects", "0004_project_photo_required"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="work_days",
            field=models.JSONField(blank=True, default=list, verbose_name="Días laborales"),
        ),
        migrations.AddField(
            model_name="project",
            name="work_start",
            field=models.TimeField(blank=True, null=True, verbose_name="Inicio de jornada"),
        ),
        migrations.AddField(
            model_name="project",
            name="work_end",
            field=models.TimeField(blank=True, null=True, verbose_name="Fin de jornada"),
        ),
    ]
