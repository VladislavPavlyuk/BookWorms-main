# Generated manually for proposed_due_date on BookExchangeRequest

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0031_privatemessage_library_action"),
    ]

    operations = [
        migrations.AddField(
            model_name="bookexchangerequest",
            name="proposed_due_date",
            field=models.DateField(
                blank=True,
                help_text="Для позики: дата, яку запропонував позичальник. Обмін — порожнє.",
                null=True,
                verbose_name="Запропонований термін повернення",
            ),
        ),
    ]
