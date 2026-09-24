# Generated manually for LoanHandoff + CopyEvent handoff codes

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0021_copy_queue_and_transmit"),
    ]

    operations = [
        migrations.AlterField(
            model_name="copyevent",
            name="code",
            field=models.CharField(
                choices=[
                    ("added", "Додано на полицю"),
                    ("removed", "Знято з полиці"),
                    ("loaned", "Видано в позику"),
                    ("return_requested", "Ініційовано повернення"),
                    ("returned", "Повернено власнику"),
                    ("exchanged", "Обмін (передача власності)"),
                    ("transmitted", "Передано третій особі (з дозволу власника)"),
                    (
                        "handoff_approved",
                        "Власник схвалив передачу (очікує фізичну передачу)",
                    ),
                    (
                        "handoff_given",
                        "Попередній позичальник підтвердив віддачу",
                    ),
                ],
                max_length=32,
                verbose_name="Подія",
            ),
        ),
        migrations.CreateModel(
            name="LoanHandoff",
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
                    "status",
                    models.CharField(
                        choices=[
                            ("awaiting_give", "Очікує віддачі"),
                            ("awaiting_receive", "Очікує отримання"),
                            ("completed", "Завершено"),
                            ("cancelled", "Скасовано"),
                        ],
                        db_index=True,
                        default="awaiting_give",
                        max_length=32,
                    ),
                ),
                ("giver_confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("receiver_confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "copy",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="handoffs",
                        to="mainApp.bookcopy",
                        verbose_name="Примірник",
                    ),
                ),
                (
                    "exchange_request",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="handoffs",
                        to="mainApp.bookexchangerequest",
                        verbose_name="Запит",
                    ),
                ),
                (
                    "from_shelf",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="outgoing_handoffs",
                        to="mainApp.shelf",
                        verbose_name="Рядок полиці поточного тримача",
                    ),
                ),
                (
                    "from_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="handoffs_as_giver",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Від кого (поточний тримач)",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="owned_handoffs",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Власник",
                    ),
                ),
                (
                    "to_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="handoffs_as_receiver",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Кому (наступний позичальник)",
                    ),
                ),
            ],
            options={
                "verbose_name": "фізична передача позики",
                "verbose_name_plural": "фізичні передачі позик",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="loanhandoff",
            constraint=models.UniqueConstraint(
                condition=models.Q(status__in=["awaiting_give", "awaiting_receive"]),
                fields=("copy",),
                name="unique_active_loan_handoff_per_copy",
            ),
        ),
    ]
