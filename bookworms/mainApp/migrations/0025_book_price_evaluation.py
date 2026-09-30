from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0024_book_cover_text"),
    ]

    operations = [
        migrations.CreateModel(
            name="BookPriceEvaluation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Оцінка…"),
                            ("ready", "Є оцінка"),
                            ("missing", "Не знайдено"),
                            ("error", "Помилка"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("currency", models.CharField(default="UAH", max_length=8, verbose_name="Валюта")),
                (
                    "price_avg",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                        verbose_name="Середня ціна",
                    ),
                ),
                (
                    "price_min",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                        verbose_name="Мін. ціна",
                    ),
                ),
                (
                    "price_max",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                        verbose_name="Макс. ціна",
                    ),
                ),
                ("source_count", models.PositiveSmallIntegerField(default=0)),
                ("evaluated_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "book",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="price_evaluation",
                        to="mainApp.book",
                        verbose_name="Книга",
                    ),
                ),
            ],
            options={
                "verbose_name": "оцінка ціни книги",
                "verbose_name_plural": "оцінки цін книг",
            },
        ),
        migrations.CreateModel(
            name="BookPriceQuote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_name", models.CharField(max_length=120, verbose_name="Джерело")),
                ("source_url", models.URLField(blank=True, max_length=500, verbose_name="URL")),
                ("price", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="Ціна")),
                ("currency", models.CharField(default="UAH", max_length=8)),
                ("price_uah", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="Ціна (UAH)")),
                ("fetched_at", models.DateTimeField(auto_now_add=True)),
                (
                    "evaluation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="quotes",
                        to="mainApp.bookpriceevaluation",
                        verbose_name="Оцінка",
                    ),
                ),
            ],
            options={
                "verbose_name": "цінова пропозиція",
                "verbose_name_plural": "цінові пропозиції",
                "ordering": ["price_uah", "id"],
            },
        ),
    ]
