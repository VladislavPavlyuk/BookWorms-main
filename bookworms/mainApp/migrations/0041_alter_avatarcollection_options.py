# Generated manually — AvatarCollection default ordering.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0040_librarymergecode"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="avatarcollection",
            options={
                "ordering": ["name", "id"],
                "verbose_name": "Аватар з колекції",
                "verbose_name_plural": "Колекція аватарів",
            },
        ),
    ]
