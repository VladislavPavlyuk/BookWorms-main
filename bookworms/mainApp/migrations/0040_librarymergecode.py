# Generated manually — short-lived 4-digit library merge codes.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0039_bookexchangerequest_offer_open"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LibraryMergeCode",
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
                    "code",
                    models.CharField(db_index=True, max_length=4, verbose_name="Код"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "expires_at",
                    models.DateTimeField(db_index=True, verbose_name="Дійсний до"),
                ),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="library_merge_codes_created",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Хто згенерував",
                    ),
                ),
                (
                    "invite",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="merge_codes",
                        to="mainApp.libraryinvite",
                        verbose_name="Створене запрошення",
                    ),
                ),
                (
                    "library",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="merge_codes",
                        to="mainApp.library",
                        verbose_name="Цільова бібліотека",
                    ),
                ),
                (
                    "used_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="library_merge_codes_used",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Хто використав",
                    ),
                ),
            ],
            options={
                "verbose_name": "код об'єднання бібліотек",
                "verbose_name_plural": "коди об'єднання бібліотек",
                "ordering": ["-created_at"],
            },
        ),
    ]
