from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0009_completion_photo_b64"),
    ]

    operations = [
        migrations.AddField(
            model_name="deliverytask",
            name="client_name",
            field=models.CharField(blank=True, max_length=200, verbose_name="cliente"),
        ),
        migrations.AddField(
            model_name="deliverytask",
            name="payment_method",
            field=models.CharField(
                blank=True,
                choices=[("efectivo", "Efectivo"), ("banco", "Banco"), ("cxc", "CXC")],
                max_length=20,
                verbose_name="método de pago",
            ),
        ),
    ]
