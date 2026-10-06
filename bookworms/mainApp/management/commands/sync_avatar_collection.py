"""Sync AvatarCollection from packaged seed PNGs (cut from avatar sheets)."""
from __future__ import annotations

from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand

from mainApp.models import AvatarCollection

SEED_DIR = Path(__file__).resolve().parents[2] / "seed_data" / "default_avatars"


class Command(BaseCommand):
    help = "Load / refresh AvatarCollection from mainApp/seed_data/default_avatars/"

    def add_arguments(self, parser):
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete existing AvatarCollection rows first.",
        )

    def handle(self, *args, **options):
        if not SEED_DIR.is_dir():
            self.stderr.write(self.style.ERROR(f"Seed dir missing: {SEED_DIR}"))
            return

        files = sorted(SEED_DIR.glob("avatar_*.png"))
        if not files:
            self.stderr.write(self.style.ERROR(f"No avatar_*.png in {SEED_DIR}"))
            return

        if options["replace"]:
            n = AvatarCollection.objects.count()
            AvatarCollection.objects.all().delete()
            self.stdout.write(f"Deleted {n} existing avatars.")

        created = 0
        updated = 0
        for path in files:
            name = path.stem.replace("_", " ").title()
            existing = AvatarCollection.objects.filter(name=name).first()
            if existing:
                with path.open("rb") as fh:
                    existing.image.save(path.name, File(fh), save=True)
                updated += 1
                continue
            obj = AvatarCollection(name=name)
            with path.open("rb") as fh:
                obj.image.save(path.name, File(fh), save=True)
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Avatar collection: +{created} created, {updated} updated "
                f"({len(files)} files)."
            )
        )
