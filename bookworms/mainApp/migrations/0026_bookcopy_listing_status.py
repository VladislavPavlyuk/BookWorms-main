from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0025_book_price_evaluation"),
    ]

    operations = [
        migrations.AddField(
            model_name="bookcopy",
            name="listing_status",
            field=models.CharField(
                choices=[
                    ("fee_sharing", "Free sharing "),
                    ("hidden", "Hidden"),
                    ("for_sale", "For sale"),
                    ("for_rent", "For rent"),
                    ("as_gift", "As a gift"),
                    ("for_exchange", "For exchange"),
                    ("free_of_deposit", "Free of deposit"),
                ],
                db_index=True,
                default="fee_sharing",
                help_text="Режим на полиці власника: видимість, продаж, оренда, обмін тощо.",
                max_length=32,
                verbose_name="Статус примірника",
            ),
        ),
        migrations.AddField(
            model_name="bookcopy",
            name="sale_price",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Обов’язково для статусу For sale (UAH).",
                max_digits=12,
                null=True,
                verbose_name="Ціна продажу",
            ),
        ),
        migrations.AddField(
            model_name="bookcopy",
            name="rent_price_per_day",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Обов’язково для статусу For rent (UAH/день).",
                max_digits=12,
                null=True,
                verbose_name="Оренда за день",
            ),
        ),
    ]
