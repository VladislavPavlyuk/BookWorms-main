from django.db import migrations


def restore_owner_shelves_for_active_loans(apps, schema_editor):
    """
    Стара логіка позики переносила Shelf до позичальника — власник «втрачав» книгу.
    Відновлюємо рядок власника для кожної активної позики, якщо його немає.
    """
    Shelf = apps.get_model("mainApp", "Shelf")
    for loan in Shelf.objects.filter(borrowed_from_id__isnull=False).iterator():
        exists = Shelf.objects.filter(
            user_id=loan.borrowed_from_id,
            book_id=loan.book_id,
            borrowed_from_id__isnull=True,
        ).exists()
        if not exists:
            Shelf.objects.create(
                user_id=loan.borrowed_from_id,
                book_id=loan.book_id,
                borrowed_from_id=None,
                return_pending=False,
                due_date=None,
            )


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0015_backfill_is_system_all"),
    ]

    operations = [
        migrations.RunPython(restore_owner_shelves_for_active_loans, migrations.RunPython.noop),
    ]
