# Generated manually for BookPhoto

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0022_loan_handoff"),
    ]

    operations = [
        migrations.CreateModel(
            name="BookPhoto",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "image",
                    models.ImageField(
                        upload_to="book_photos/%Y/%m/", verbose_name="Фото"
                    ),
                ),
                (
                    "sort_order",
                    models.PositiveSmallIntegerField(default=0, verbose_name="Порядок"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "book",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="photos",
                        to="mainApp.book",
                        verbose_name="Книга",
                    ),
                ),
            ],
            options={
                "verbose_name": "фото книги",
                "verbose_name_plural": "фото книг",
                "ordering": ["sort_order", "id"],
            },
        ),
    ]
