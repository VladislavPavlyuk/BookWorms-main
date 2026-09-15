from django.core.management.base import BaseCommand

from mainApp.registration_service import (
    purge_expired_unactivated_users,
    purge_status,
)


class Command(BaseCommand):
    help = "Видаляє акаунти з email_confirmed=False старші за ACTIVATION_TIMEOUT_MINUTES."

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

        def once():
            st = purge_status()
            n = purge_expired_unactivated_users()
            line = (
                f"purge: deleted={n} pending_unconfirmed={st['pending_unconfirmed']} "
                f"expired_unconfirmed={st['expired_unconfirmed']} "
                f"inactive_users={st['inactive_users']} "
                f"timeout={st['activation_timeout_minutes']}m "
                f"skip_email_activation={st['skip_email_activation']}"
            )
            self.stdout.write(line)
            print(line, flush=True)

        if interval <= 0:
            once()
            return

        self.stdout.write(f"purge loop every {interval}s")
        while True:
            try:
                once()
            except Exception as e:
                self.stderr.write(f"purge error: {e}")
                print(f"purge error: {e}", flush=True)
            time.sleep(interval)
