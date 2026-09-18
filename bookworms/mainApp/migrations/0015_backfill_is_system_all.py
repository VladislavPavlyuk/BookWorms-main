from django.db import migrations


def mark_all_existing_as_system(apps, schema_editor):
    """
    Усі історичні листи — сповіщення (бекфіл).
    Інакше is_system=False + mark_thread_read знову з’їдає весь badge при відкритті чату,
    а строгий filter is_system=True лишав inbox порожнім.
    Новий чат пише is_system=False; notify_* — True.
    """
    PM = apps.get_model("mainApp", "PrivateMessage")
    PM.objects.all().update(is_system=True)


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0014_privatemessage_is_system"),
    ]

    operations = [
        migrations.RunPython(mark_all_existing_as_system, migrations.RunPython.noop),
    ]
