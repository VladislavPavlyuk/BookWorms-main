from django.db import migrations, models


NOTIFY_NEEDLES = (
    "ініціював повернення",
    "підтвердив отримання",
    "Запит на позику",
    "Запит на обмін",
    "скасував запит",
    "відхилено",
    "запит на позику прийнято",
    "запит на обмін прийнято",
    "Ваш запит на",
)


def backfill_system_flags(apps, schema_editor):
    PM = apps.get_model("mainApp", "PrivateMessage")
    PM.objects.filter(exchange_request_id__isnull=False).update(is_system=True)
    for needle in NOTIFY_NEEDLES:
        PM.objects.filter(body__icontains=needle).update(is_system=True)


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0013_customuser_email_confirmed"),
    ]

    operations = [
        migrations.AddField(
            model_name="privatemessage",
            name="is_system",
            field=models.BooleanField(default=False, verbose_name="Системне сповіщення"),
        ),
        migrations.RunPython(backfill_system_flags, migrations.RunPython.noop),
    ]
