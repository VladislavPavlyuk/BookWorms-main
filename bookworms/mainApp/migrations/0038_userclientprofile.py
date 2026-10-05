# Generated manually for UserClientProfile analytics.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0037_unbind_all_copy_qr"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserClientProfile",
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
                    "last_ip",
                    models.CharField(blank=True, db_index=True, default="", max_length=64),
                ),
                (
                    "country",
                    models.CharField(blank=True, db_index=True, default="", max_length=64),
                ),
                (
                    "country_code",
                    models.CharField(blank=True, default="", max_length=8),
                ),
                ("region", models.CharField(blank=True, default="", max_length=64)),
                (
                    "city",
                    models.CharField(blank=True, db_index=True, default="", max_length=64),
                ),
                (
                    "device_type",
                    models.CharField(
                        blank=True, db_index=True, default="unknown", max_length=16
                    ),
                ),
                (
                    "device_brand",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                (
                    "os_family",
                    models.CharField(blank=True, db_index=True, default="", max_length=32),
                ),
                ("os_version", models.CharField(blank=True, default="", max_length=32)),
                (
                    "browser_family",
                    models.CharField(blank=True, default="", max_length=32),
                ),
                (
                    "language_code",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=16
                    ),
                ),
                (
                    "accept_language",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "user_agent",
                    models.CharField(blank=True, default="", max_length=512),
                ),
                ("hit_count", models.PositiveIntegerField(default=0)),
                ("first_seen_at", models.DateTimeField(blank=True, null=True)),
                (
                    "last_seen_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="client_profile",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Користувач",
                    ),
                ),
            ],
            options={
                "verbose_name": "клієнтський профіль",
                "verbose_name_plural": "аналітика клієнтів",
                "ordering": ["-last_seen_at"],
            },
        ),
    ]
