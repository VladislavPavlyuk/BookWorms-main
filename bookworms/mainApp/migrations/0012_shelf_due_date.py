from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0011_alter_book_id_alter_bookexchangerequest_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="shelf",
            name="due_date",
            field=models.DateField(
                blank=True,
                help_text="Заповнюється при позиці. Обмін без позики — порожнє.",
                null=True,
                verbose_name="Термін повернення",
            ),
        ),
    ]
