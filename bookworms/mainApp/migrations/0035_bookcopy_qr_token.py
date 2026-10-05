from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0034_bookexchangerequest_due_negotiation"),
    ]

    operations = [
        migrations.AddField(
            model_name="bookcopy",
            name="qr_token",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Унікальний секрет у QR-наклейці (BW1.<token>).",
                max_length=64,
                null=True,
                unique=True,
                verbose_name="QR-токен примірника",
            ),
        ),
        migrations.AddField(
            model_name="bookcopy",
            name="qr_attached_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Коли власник відсканував наклейку на цьому примірнику.",
                null=True,
                verbose_name="QR приклеєно",
            ),
        ),
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
                    ("qr_attached", "QR-наклейку прив’язано до примірника"),
                ],
                max_length=32,
                verbose_name="Подія",
            ),
        ),
    ]
