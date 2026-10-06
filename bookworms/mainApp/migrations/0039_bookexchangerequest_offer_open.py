# Generated manually — offer_open for owner-picked exchange from requester library.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0038_userclientprofile"),
    ]

    operations = [
        migrations.AddField(
            model_name="bookexchangerequest",
            name="offer_open",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    "True = позичальник пропонує обмін і дозволяє власнику вибрати "
                    "примірник зі своєї (запитувача) полиці в діалозі."
                ),
                verbose_name="Власник може обрати книгу з полиці запитувача",
            ),
        ),
    ]
