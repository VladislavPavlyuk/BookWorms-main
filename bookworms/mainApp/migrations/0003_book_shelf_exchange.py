# Міграція: розділяємо дані на Book + Shelf, додаємо BookExchangeRequest, переносимо рядки з ShelfBook, потім видаляємо ShelfBook.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def shelfbook_to_book_shelf(apps, schema_editor):
    ShelfBook = apps.get_model("mainApp", "ShelfBook")
    Book = apps.get_model("mainApp", "Book")
    Shelf = apps.get_model("mainApp", "Shelf")
    for sb in ShelfBook.objects.all().order_by("id"):
        book, _ = Book.objects.get_or_create(
            isbn=sb.isbn,
            defaults={
                "title": sb.title,
                "authors": sb.authors or "",
                "publisher": sb.publisher or "",
                "publish_date": sb.publish_date or "",
                "cover_url": sb.cover_url or "",
                "info_url": sb.info_url or "",
            },
        )
        if not Shelf.objects.filter(user_id=sb.user_id, book_id=book.id).exists():
            Shelf.objects.create(
                user_id=sb.user_id,
                book_id=book.id,
                added_at=sb.added_at,
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0002_shelfbook"),
    ]

    operations = [
        migrations.CreateModel(
            name="Book",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("isbn", models.CharField(db_index=True, max_length=13, unique=True, verbose_name="ISBN")),
                ("title", models.CharField(max_length=500, verbose_name="Назва")),
                ("authors", models.CharField(blank=True, max_length=500, verbose_name="Автори")),
                ("publisher", models.CharField(blank=True, max_length=300, verbose_name="Видавець")),
                ("publish_date", models.CharField(blank=True, max_length=64, verbose_name="Дата видання")),
                ("cover_url", models.URLField(blank=True, max_length=500, verbose_name="Обкладинка (URL)")),
                ("info_url", models.URLField(blank=True, max_length=500, verbose_name="Open Library")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "книга",
                "verbose_name_plural": "книги",
                "ordering": ["title"],
            },
        ),
        migrations.CreateModel(
            name="Shelf",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                (
                    "book",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shelf_entries",
                        to="mainApp.book",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shelf_entries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "полиця",
                "verbose_name_plural": "полиці",
                "ordering": ["-added_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="shelf",
            constraint=models.UniqueConstraint(fields=("user", "book"), name="unique_shelf_user_book"),
        ),
        migrations.CreateModel(
            name="BookExchangeRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Очікує"),
                            ("accepted", "Прийнято"),
                            ("rejected", "Відхилено"),
                            ("cancelled", "Скасовано"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "offer_shelf",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="offered_in_exchange_requests",
                        to="mainApp.shelf",
                        verbose_name="Книга з вашої полиці в обмін (необов'язково)",
                    ),
                ),
                (
                    "requester",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sent_exchange_requests",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Хто запитує",
                    ),
                ),
                (
                    "target_shelf",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="incoming_exchange_requests",
                        to="mainApp.shelf",
                        verbose_name="Чия книга запитується",
                    ),
                ),
                (
                    "shelf_owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Власник на момент запиту",
                    ),
                ),
            ],
            options={
                "verbose_name": "запит на обмін",
                "verbose_name_plural": "запити на обмін",
                "ordering": ["-created_at"],
            },
        ),
        migrations.RunPython(shelfbook_to_book_shelf, noop_reverse),
        migrations.DeleteModel(name="ShelfBook"),
    ]
