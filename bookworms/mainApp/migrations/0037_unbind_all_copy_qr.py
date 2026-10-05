# Generated manually — unbind all QR from BookCopy (late-binding reset).

from django.db import migrations


def unbind_all_qr(apps, schema_editor):
    BookCopy = apps.get_model("mainApp", "BookCopy")
    PreprintedQrToken = apps.get_model("mainApp", "PreprintedQrToken")

    BookCopy.objects.exclude(qr_token__isnull=True, qr_attached_at__isnull=True).update(
        qr_token=None,
        qr_attached_at=None,
    )
    # Return claimed pool stickers to unbound stock (no copy link).
    PreprintedQrToken.objects.exclude(copy__isnull=True, claimed_at__isnull=True).update(
        copy=None,
        claimed_at=None,
    )


def noop_reverse(apps, schema_editor):
    # Irreversible: previous bindings are not reconstructed.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0036_preprintedqrtoken"),
    ]

    operations = [
        migrations.RunPython(unbind_all_qr, noop_reverse),
    ]
