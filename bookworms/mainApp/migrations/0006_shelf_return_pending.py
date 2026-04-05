from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("mainApp", "0005_private_message"),
    ]

    operations = [
        migrations.AddField(
            model_name="shelf",
            name="return_pending",
            field=models.BooleanField(
                default=False,
                verbose_name="Очікує підтвердження повернення",
            ),
        ),
    ]
