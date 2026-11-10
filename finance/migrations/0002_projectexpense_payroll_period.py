import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Enlaza los gastos generados por el cierre de nómina con su periodo (nulo en los gastos manuales)."""

    dependencies = [
        ("finance", "0001_initial"),
        ("payroll", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="projectexpense",
            name="payroll_period",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="expenses",
                to="payroll.payrollperiod",
                verbose_name="Periodo de nómina",
            ),
        ),
    ]
