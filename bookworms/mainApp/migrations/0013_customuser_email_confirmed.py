from django.db import migrations, models


def mark_existing(apps, schema_editor):
    User = apps.get_model("mainApp", "CustomUser")
    # Уже активні / суперюзери вважаємо підтвердженими.
    User.objects.filter(is_active=True).update(email_confirmed=True)
    User.objects.filter(is_superuser=True).update(email_confirmed=True)
    # Неактивні без суперправ — чекають підтвердження.
    User.objects.filter(is_active=False, is_superuser=False).update(email_confirmed=False)


class Migration(migrations.Migration):
    dependencies = [
        ("mainApp", "0012_shelf_due_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="email_confirmed",
            field=models.BooleanField(
                db_index=True,
                default=True,
                help_text="False після реєстрації до активації; True для суперюзерів і після confirm.",
                verbose_name="Email підтверджено",
            ),
        ),
        migrations.RunPython(mark_existing, migrations.RunPython.noop),
    ]
