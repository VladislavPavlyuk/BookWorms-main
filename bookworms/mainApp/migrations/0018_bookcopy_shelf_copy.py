# Generated manually for BookCopy physical instances

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_book_copies(apps, schema_editor):
    Shelf = apps.get_model("mainApp", "Shelf")
    BookCopy = apps.get_model("mainApp", "BookCopy")

    # Owned shelves first → one BookCopy each
    owned_by_key = {}  # (owner_id, book_id) -> first owned shelf's copy for loans without owner row
    for shelf in Shelf.objects.filter(borrowed_from_id__isnull=True).iterator():
        copy = BookCopy.objects.create(book_id=shelf.book_id, owner_id=shelf.user_id)
        Shelf.objects.filter(pk=shelf.pk).update(copy_id=copy.pk)
        owned_by_key[(shelf.user_id, shelf.book_id)] = copy.pk

    # Loan shelves → share owner's copy for that book; create copy if owner row missing
    for shelf in Shelf.objects.filter(borrowed_from_id__isnull=False).iterator():
        key = (shelf.borrowed_from_id, shelf.book_id)
        copy_id = owned_by_key.get(key)
        if copy_id is None:
            # Prefer existing owner shelf copy created above
            owner_shelf = (
                Shelf.objects.filter(
                    user_id=shelf.borrowed_from_id,
                    book_id=shelf.book_id,
                    borrowed_from_id__isnull=True,
                    copy_id__isnull=False,
                )
                .order_by("pk")
                .first()
            )
            if owner_shelf:
                copy_id = owner_shelf.copy_id
            else:
                copy = BookCopy.objects.create(
                    book_id=shelf.book_id,
                    owner_id=shelf.borrowed_from_id,
                )
                copy_id = copy.pk
                owned_by_key[key] = copy_id
        Shelf.objects.filter(pk=shelf.pk).update(copy_id=copy_id)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0017_privatemessage_related_shelf"),
    ]

    operations = [
        migrations.CreateModel(
            name="BookCopy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "book",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="copies",
                        to="mainApp.book",
                        verbose_name="Книга (ISBN)",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="owned_copies",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Власник",
                    ),
                ),
            ],
            options={
                "verbose_name": "примірник книги",
                "verbose_name_plural": "примірники книг",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddField(
            model_name="shelf",
            name="copy",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="shelf_entries",
                to="mainApp.bookcopy",
                verbose_name="Примірник",
            ),
        ),
        migrations.RunPython(backfill_book_copies, noop_reverse),
        migrations.AlterField(
            model_name="shelf",
            name="copy",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="shelf_entries",
                to="mainApp.bookcopy",
                verbose_name="Примірник",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="shelf",
            name="unique_shelf_user_book",
        ),
        migrations.AddConstraint(
            model_name="shelf",
            constraint=models.UniqueConstraint(
                fields=("user", "copy"),
                name="unique_shelf_user_copy",
            ),
        ),
    ]
