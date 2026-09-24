# Generated manually for CopyQueueEntry + CopyEvent.TRANSMITTED

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0020_customuser_last_watched_post"),
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
                ],
                max_length=32,
                verbose_name="Подія",
            ),
        ),
        migrations.CreateModel(
            name="CopyQueueEntry",
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
                            ("waiting", "У черзі"),
                            ("offered", "Запропоновано (ваша черга)"),
                            ("fulfilled", "Отримано"),
                            ("cancelled", "Скасовано"),
                        ],
                        db_index=True,
                        default="waiting",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "copy",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="queue_entries",
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
                        related_name="queue_entries",
                        to="mainApp.bookexchangerequest",
                        verbose_name="Пов’язаний запит",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="copy_queue_entries",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Хто чекає",
                    ),
                ),
            ],
            options={
                "verbose_name": "запис черги примірника",
                "verbose_name_plural": "черга примірників",
                "ordering": ["created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="copyqueueentry",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status__in", ["waiting", "offered"])),
                fields=("copy", "user"),
                name="unique_active_copy_queue_user",
            ),
        ),
    ]
