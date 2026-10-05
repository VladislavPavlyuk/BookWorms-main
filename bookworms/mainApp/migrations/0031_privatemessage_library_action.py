from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0030_privatemessage_library_invite"),
    ]

    operations = [
        migrations.AddField(
            model_name="privatemessage",
            name="library_action",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="private_messages",
                to="mainApp.libraryaction",
                verbose_name="Дія спільної бібліотеки",
            ),
        ),
    ]
