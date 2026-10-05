# Due-date negotiation fields on BookExchangeRequest

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0033_alter_bookcopy_rent_price_per_day_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="bookexchangerequest",
            name="due_date_proposer",
            field=models.CharField(
                blank=True,
                choices=[("requester", "Позичальник"), ("owner", "Власник")],
                default="requester",
                max_length=16,
                verbose_name="Хто запропонував термін",
            ),
        ),
        migrations.AddField(
            model_name="bookexchangerequest",
            name="due_date_confirmed",
            field=models.BooleanField(
                default=False,
                help_text="True після confirm-due від сторони, яка не робила останню пропозицію.",
                verbose_name="Інша сторона погодила термін",
            ),
        ),
        migrations.AlterField(
            model_name="bookexchangerequest",
            name="proposed_due_date",
            field=models.DateField(
                blank=True,
                help_text="Поточна пропозиція терміну для позики (хто запропонував — due_date_proposer).",
                null=True,
                verbose_name="Запропонований термін повернення",
            ),
        ),
    ]
