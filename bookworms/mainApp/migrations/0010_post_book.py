# Post optional link to Book (post about a read book).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0009_book_reader_age_min_max"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="book",
            field=models.ForeignKey(
                blank=True,
                help_text="Якщо пост про прочитану книгу з полиці.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="posts",
                to="mainApp.book",
                verbose_name="Книга у пості",
            ),
        ),
    ]
