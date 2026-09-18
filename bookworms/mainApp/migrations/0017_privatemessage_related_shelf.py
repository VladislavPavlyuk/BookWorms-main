from django.db import migrations, models
import django.db.models.deletion


def backfill_return_shelves(apps, schema_editor):
    """Прив’язати існуючі сповіщення про повернення до return_pending рядків."""
    PrivateMessage = apps.get_model("mainApp", "PrivateMessage")
    Shelf = apps.get_model("mainApp", "Shelf")
    for msg in PrivateMessage.objects.filter(
        is_system=True,
        related_shelf_id__isnull=True,
        body__icontains="ініціював повернення",
    ).iterator():
        loan = (
            Shelf.objects.filter(
                user_id=msg.sender_id,
                borrowed_from_id=msg.recipient_id,
                return_pending=True,
            )
            .order_by("-added_at")
            .first()
        )
        if loan:
            PrivateMessage.objects.filter(pk=msg.pk).update(related_shelf_id=loan.pk)


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0016_restore_owner_shelves_on_loan"),
    ]

    operations = [
        migrations.AddField(
            model_name="privatemessage",
            name="related_shelf",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="related_private_messages",
                to="mainApp.shelf",
                verbose_name="Пов’язана полиця",
            ),
        ),
        migrations.RunPython(backfill_return_shelves, migrations.RunPython.noop),
    ]
