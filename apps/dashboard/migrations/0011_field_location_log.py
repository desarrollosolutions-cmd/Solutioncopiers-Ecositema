from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0010_deliverytask_client_payment"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FieldLocationLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("latitude", models.DecimalField(decimal_places=6, max_digits=9)),
                ("longitude", models.DecimalField(decimal_places=6, max_digits=9)),
                ("shift_date", models.DateField(db_index=True)),
                ("recorded_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="location_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Punto de ruta",
                "verbose_name_plural": "Historial de rutas",
                "ordering": ["recorded_at"],
            },
        ),
        migrations.AddIndex(
            model_name="fieldlocationlog",
            index=models.Index(fields=["user", "shift_date"], name="dashboard_f_user_id_shift_idx"),
        ),
    ]
