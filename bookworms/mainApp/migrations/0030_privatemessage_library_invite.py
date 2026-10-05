from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0029_library_admin_election"),
    ]

    operations = [
        migrations.AddField(
            model_name="privatemessage",
            name="library_invite",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="private_messages",
                to="mainApp.libraryinvite",
                verbose_name="Запрошення до бібліотеки",
            ),
        ),
    ]
