# Злиття двох гілок міграцій: 0006_merge (аватари/лайки) та 0006_shelf_return_pending.
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("mainApp", "0006_merge_20260405_2144"),
        ("mainApp", "0006_shelf_return_pending"),
    ]

    operations = []
