from django.db import migrations, models


def forwards_from_listing_status(apps, schema_editor):
    BookCopy = apps.get_model("mainApp", "BookCopy")
    for copy in BookCopy.objects.all().iterator():
        status = getattr(copy, "listing_status", None) or "fee_sharing"
        copy.is_fee_sharing = status == "fee_sharing" or status not in (
            "hidden",
            "for_sale",
            "for_rent",
            "as_gift",
            "for_exchange",
            "free_of_deposit",
        )
        # Keep fee_sharing as soft default alongside the primary mode when it was sole status.
        if status == "fee_sharing":
            copy.is_fee_sharing = True
            copy.is_hidden = False
            copy.is_for_sale = False
            copy.is_for_rent = False
            copy.is_as_gift = False
            copy.is_for_exchange = False
            copy.is_free_of_deposit = False
        elif status == "hidden":
            copy.is_fee_sharing = True
            copy.is_hidden = True
            copy.is_for_sale = False
            copy.is_for_rent = False
            copy.is_as_gift = False
            copy.is_for_exchange = False
            copy.is_free_of_deposit = False
        elif status == "for_sale":
            copy.is_fee_sharing = False
            copy.is_hidden = False
            copy.is_for_sale = True
            copy.is_for_rent = False
            copy.is_as_gift = False
            copy.is_for_exchange = False
            copy.is_free_of_deposit = False
        elif status == "for_rent":
            copy.is_fee_sharing = False
            copy.is_hidden = False
            copy.is_for_sale = False
            copy.is_for_rent = True
            copy.is_as_gift = False
            copy.is_for_exchange = False
            copy.is_free_of_deposit = False
        elif status == "as_gift":
            copy.is_fee_sharing = False
            copy.is_hidden = False
            copy.is_for_sale = False
            copy.is_for_rent = False
            copy.is_as_gift = True
            copy.is_for_exchange = False
            copy.is_free_of_deposit = False
        elif status == "for_exchange":
            copy.is_fee_sharing = False
            copy.is_hidden = False
            copy.is_for_sale = False
            copy.is_for_rent = False
            copy.is_as_gift = False
            copy.is_for_exchange = True
            copy.is_free_of_deposit = False
        elif status == "free_of_deposit":
            copy.is_fee_sharing = True
            copy.is_hidden = False
            copy.is_for_sale = False
            copy.is_for_rent = False
            copy.is_as_gift = False
            copy.is_for_exchange = False
            copy.is_free_of_deposit = True
        copy.save(
            update_fields=[
                "is_fee_sharing",
                "is_hidden",
                "is_for_sale",
                "is_for_rent",
                "is_as_gift",
                "is_for_exchange",
                "is_free_of_deposit",
            ]
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0026_bookcopy_listing_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="bookcopy",
            name="is_fee_sharing",
            field=models.BooleanField(
                default=True,
                help_text="Типовий режим спільного користування.",
                verbose_name="Free sharing ",
            ),
        ),
        migrations.AddField(
            model_name="bookcopy",
            name="is_hidden",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Не показувати в пошуку/каталозі інших користувачів.",
                verbose_name="Hidden",
            ),
        ),
        migrations.AddField(
            model_name="bookcopy",
            name="is_for_sale",
            field=models.BooleanField(
                default=False,
                help_text="Взаємовиключно з As a gift.",
                verbose_name="For sale",
            ),
        ),
        migrations.AddField(
            model_name="bookcopy",
            name="is_for_rent",
            field=models.BooleanField(default=False, verbose_name="For rent"),
        ),
        migrations.AddField(
            model_name="bookcopy",
            name="is_as_gift",
            field=models.BooleanField(
                default=False,
                help_text="Взаємовиключно з For sale.",
                verbose_name="As a gift",
            ),
        ),
        migrations.AddField(
            model_name="bookcopy",
            name="is_for_exchange",
            field=models.BooleanField(default=False, verbose_name="For exchange"),
        ),
        migrations.AddField(
            model_name="bookcopy",
            name="is_free_of_deposit",
            field=models.BooleanField(
                default=False,
                help_text="Позика без банківського депозиту.",
                verbose_name="Free of deposit",
            ),
        ),
        migrations.RunPython(forwards_from_listing_status, noop_reverse),
        migrations.RemoveField(
            model_name="bookcopy",
            name="listing_status",
        ),
    ]
