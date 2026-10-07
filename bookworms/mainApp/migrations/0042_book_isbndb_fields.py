# Generated manually — ISBNdb Book schema fields on catalog Book.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0041_alter_avatarcollection_options"),
    ]

    operations = [
        migrations.AlterField(
            model_name="book",
            name="isbn",
            field=models.CharField(
                db_index=True, max_length=13, unique=True, verbose_name="ISBN-13"
            ),
        ),
        migrations.AlterField(
            model_name="book",
            name="info_url",
            field=models.URLField(
                blank=True, max_length=500, verbose_name="Сторінка в каталозі"
            ),
        ),
        migrations.AddField(
            model_name="book",
            name="isbn10",
            field=models.CharField(blank=True, max_length=10, verbose_name="ISBN-10"),
        ),
        migrations.AddField(
            model_name="book",
            name="title_long",
            field=models.CharField(blank=True, max_length=500, verbose_name="Повна назва"),
        ),
        migrations.AddField(
            model_name="book",
            name="binding",
            field=models.CharField(blank=True, max_length=64, verbose_name="Палітурка"),
        ),
        migrations.AddField(
            model_name="book",
            name="language",
            field=models.CharField(blank=True, max_length=32, verbose_name="Мова"),
        ),
        migrations.AddField(
            model_name="book",
            name="edition",
            field=models.CharField(blank=True, max_length=64, verbose_name="Видання"),
        ),
        migrations.AddField(
            model_name="book",
            name="pages",
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name="Сторінок"
            ),
        ),
        migrations.AddField(
            model_name="book",
            name="dimensions",
            field=models.CharField(blank=True, max_length=200, verbose_name="Розміри"),
        ),
        migrations.AddField(
            model_name="book",
            name="dimensions_data",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="ISBNdb dimensions_structured",
                verbose_name="Розміри (структуровані)",
            ),
        ),
        migrations.AddField(
            model_name="book",
            name="dewey_decimal",
            field=models.JSONField(blank=True, default=list, verbose_name="Dewey Decimal"),
        ),
        migrations.AddField(
            model_name="book",
            name="overview",
            field=models.TextField(blank=True, verbose_name="Огляд"),
        ),
        migrations.AddField(
            model_name="book",
            name="synopsis",
            field=models.TextField(blank=True, verbose_name="Синопсис"),
        ),
        migrations.AddField(
            model_name="book",
            name="excerpt",
            field=models.TextField(blank=True, verbose_name="Уривок"),
        ),
        migrations.AddField(
            model_name="book",
            name="msrp",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
                verbose_name="MSRP",
            ),
        ),
        migrations.AddField(
            model_name="book",
            name="subjects",
            field=models.JSONField(
                blank=True, default=list, verbose_name="Теми / категорії"
            ),
        ),
        migrations.AddField(
            model_name="book",
            name="other_isbns",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="ISBNdb other_isbns: [{isbn, binding}, …]",
                verbose_name="Інші ISBN (видання/формати)",
            ),
        ),
        migrations.AddField(
            model_name="book",
            name="cover_url_original",
            field=models.URLField(
                blank=True,
                max_length=500,
                verbose_name="Обкладинка original (тимчасовий URL)",
            ),
        ),
        migrations.AddField(
            model_name="book",
            name="catalog_source",
            field=models.CharField(
                blank=True,
                help_text="isbndb / openlibrary / googlebooks / …",
                max_length=64,
                verbose_name="Джерело метаданих",
            ),
        ),
    ]
