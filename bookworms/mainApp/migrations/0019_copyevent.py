# Generated manually for CopyEvent (per-BookCopy history)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("mainApp", "0018_bookcopy_shelf_copy"),
    ]

    operations = [
        migrations.CreateModel(
            name="CopyEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "code",
                    models.CharField(
                        choices=[
                            ("added", "Додано на полицю"),
                            ("removed", "Знято з полиці"),
                            ("loaned", "Видано в позику"),
                            ("return_requested", "Ініційовано повернення"),
                            ("returned", "Повернено власнику"),
                            ("exchanged", "Обмін (передача власності)"),
                        ],
                        max_length=32,
                        verbose_name="Подія",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="copy_events_acted",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Ініціатор",
                    ),
                ),
                (
                    "copy",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="mainApp.bookcopy",
                        verbose_name="Примірник",
                    ),
                ),
                (
                    "counterparty",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="copy_events_counterparty",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Інший учасник",
                    ),
                ),
                (
                    "exchange_request",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="copy_events",
                        to="mainApp.bookexchangerequest",
                        verbose_name="Запит обміну",
                    ),
                ),
                (
                    "holder",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="copy_events_holder",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="На полиці",
                    ),
                ),
                (
                    "legal_owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="copy_events_owner",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Власник",
                    ),
                ),
                (
                    "previous_holder",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="copy_events_prev_holder",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Попередній тримач",
                    ),
                ),
                (
                    "previous_owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="copy_events_prev_owner",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Попередній власник",
                    ),
                ),
            ],
            options={
                "verbose_name": "подія примірника",
                "verbose_name_plural": "події примірників",
                "ordering": ["-created_at"],
            },
        ),
    ]
