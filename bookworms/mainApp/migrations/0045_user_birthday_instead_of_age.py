from datetime import date

from django.db import migrations, models


def forwards_age_to_birthday(apps, schema_editor):
    from mainApp.age_utils import approx_birthday_from_age

    User = apps.get_model("mainApp", "CustomUser")
    Sub = apps.get_model("mainApp", "UserSubProfile")
    today = date.today()
    for u in User.objects.exclude(age__isnull=True).iterator():
        u.birthday = approx_birthday_from_age(u.age, today=today)
        u.save(update_fields=["birthday"])
    for sp in Sub.objects.exclude(age__isnull=True).iterator():
        sp.birthday = approx_birthday_from_age(sp.age, today=today)
        sp.save(update_fields=["birthday"])


def backwards_birthday_to_age(apps, schema_editor):
    from mainApp.age_utils import age_from_birthday

    User = apps.get_model("mainApp", "CustomUser")
    Sub = apps.get_model("mainApp", "UserSubProfile")
    today = date.today()
    for u in User.objects.exclude(birthday__isnull=True).iterator():
        u.age = age_from_birthday(u.birthday, today=today)
        u.save(update_fields=["age"])
    for sp in Sub.objects.exclude(birthday__isnull=True).iterator():
        sp.age = age_from_birthday(sp.birthday, today=today)
        sp.save(update_fields=["age"])


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0044_user_profile_themes_subprofiles"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="birthday",
            field=models.DateField(
                blank=True,
                help_text="Вік рахується з дати народження (для стрічки / рекомендацій).",
                null=True,
                verbose_name="Дата народження",
            ),
        ),
        migrations.AddField(
            model_name="usersubprofile",
            name="birthday",
            field=models.DateField(
                blank=True,
                help_text="Вік рахується з дати народження.",
                null=True,
                verbose_name="Дата народження",
            ),
        ),
        migrations.RunPython(forwards_age_to_birthday, backwards_birthday_to_age),
        migrations.RemoveField(
            model_name="customuser",
            name="age",
        ),
        migrations.RemoveField(
            model_name="usersubprofile",
            name="age",
        ),
    ]
