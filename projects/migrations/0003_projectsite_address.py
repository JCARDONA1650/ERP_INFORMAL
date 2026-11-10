from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0002_projectsite_out_of_zone_policy"),
    ]

    operations = [
        migrations.AddField(
            model_name="projectsite",
            name="address",
            field=models.CharField(blank=True, max_length=255, verbose_name="Dirección"),
        ),
    ]
