# Generated for model metadata drift vs 0032 (help_text / choices / verbose_name).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0032_bookexchangerequest_proposed_due_date"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bookcopy",
            name="rent_price_per_day",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Обов’язково якщо For rent (UAH/день).",
                max_digits=12,
                null=True,
                verbose_name="Оренда за день",
            ),
        ),
        migrations.AlterField(
            model_name="bookcopy",
            name="sale_price",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Обов’язково якщо For sale (UAH).",
                max_digits=12,
                null=True,
                verbose_name="Ціна продажу",
            ),
        ),
        migrations.AlterField(
            model_name="libraryinvite",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Очікує"),
                    ("awaiting_isbn", "Очікує ISBN від адміна"),
                    ("accepted", "Прийнято"),
                    ("rejected", "Відхилено"),
                    ("cancelled", "Скасовано"),
                ],
                db_index=True,
                default="pending",
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="post",
            name="book",
            field=models.ForeignKey(
                blank=True,
                help_text="ISBN-каталог (Book), не примірник. Вподобайки/коментарі — до поста цієї книги.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="posts",
                to="mainApp.book",
                verbose_name="Книга у пості",
            ),
        ),
    ]
