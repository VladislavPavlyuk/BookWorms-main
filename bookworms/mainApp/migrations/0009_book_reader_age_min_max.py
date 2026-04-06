# Діапазон віку читача замість reader_age_brackets (JSON).

from django.db import migrations, models
import django.core.validators


BRACKET_RANGE = {
    "0-3": (0, 3),
    "3-5": (3, 5),
    "5-7": (5, 7),
    "7-10": (7, 10),
    "10-12": (10, 12),
    "12-15": (12, 15),
    "15-18": (15, 18),
    "18+": (18, 18),
}


def brackets_to_min_max(apps, schema_editor):
    Book = apps.get_model("mainApp", "Book")
    for book in Book.objects.all():
        raw = getattr(book, "reader_age_brackets", None) or []
        if not raw:
            book.min_readers_age = 0
            book.max_readers_age = 18
        else:
            lows, highs = [], []
            for code in raw:
                if code in BRACKET_RANGE:
                    lo, hi = BRACKET_RANGE[code]
                    lows.append(lo)
                    highs.append(hi)
            book.min_readers_age = min(lows) if lows else 0
            book.max_readers_age = max(highs) if highs else 18
        book.save(update_fields=["min_readers_age", "max_readers_age"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0008_book_reader_age_brackets"),
    ]

    operations = [
        migrations.AddField(
            model_name="book",
            name="min_readers_age",
            field=models.PositiveSmallIntegerField(
                default=0,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(18),
                ],
                verbose_name="Мінімальний рекомендований вік читача (років)",
                help_text="0–18; 18 у полі «максимум» означає 18+.",
            ),
        ),
        migrations.AddField(
            model_name="book",
            name="max_readers_age",
            field=models.PositiveSmallIntegerField(
                default=18,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(18),
                ],
                verbose_name="Максимальний рекомендований вік читача (років)",
                help_text="0–18; значення 18 — «18+».",
            ),
        ),
        migrations.RunPython(brackets_to_min_max, noop_reverse),
        migrations.RemoveField(
            model_name="book",
            name="reader_age_brackets",
        ),
    ]
