from django.core.management.base import BaseCommand
from django.conf import settings

from mainApp.registration_service import purge_expired_unactivated_users


class Command(BaseCommand):
    help = (
        "Видаляє неактивовані акаунти старші за ACTIVATION_TIMEOUT_MINUTES. "
        "З --loop N повторює кожні N секунд."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--loop",
            type=int,
            default=0,
            help="Якщо >0 — крутитись у фоні з інтервалом у секундах",
        )

    def handle(self, *args, **options):
        import time

        interval = int(options["loop"] or 0)
        minutes = getattr(settings, "ACTIVATION_TIMEOUT_MINUTES", 5)

        def once():
            n = purge_expired_unactivated_users()
            if n:
                self.stdout.write(self.style.WARNING(f"purged {n} unactivated user(s) (>{minutes} min)"))
            else:
                self.stdout.write(f"purge: 0 (timeout={minutes}m)")

        if interval <= 0:
            once()
            return

        self.stdout.write(f"purge loop every {interval}s, timeout={minutes}m")
        while True:
            try:
                once()
            except Exception as e:
                self.stderr.write(f"purge error: {e}")
            time.sleep(interval)
