from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0035_bookcopy_qr_token"),
    ]

    operations = [
        migrations.CreateModel(
            name="PreprintedQrToken",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "token",
                    models.CharField(
                        db_index=True,
                        max_length=64,
                        unique=True,
                        verbose_name="QR-токен",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("claimed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "copy",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="claimed_preprint_tokens",
                        to="mainApp.bookcopy",
                        verbose_name="Примірник (після прив’язки)",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="preprinted_qr_tokens",
                        to="mainApp.customuser",
                        verbose_name="Власник",
                    ),
                ),
            ],
            options={
                "verbose_name": "заздалегідь надрукований QR",
                "verbose_name_plural": "заздалегідь надруковані QR",
                "ordering": ["id"],
            },
        ),
    ]
