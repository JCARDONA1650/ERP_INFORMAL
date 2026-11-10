from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="projectsite",
            name="out_of_zone_policy",
            field=models.CharField(
                choices=[
                    ("block", "Rechazar marcación fuera de la zona"),
                    ("review", "Permitir y marcar para revisión"),
                ],
                default="block",
                max_length=10,
                verbose_name="Política fuera de zona",
            ),
        ),
    ]
