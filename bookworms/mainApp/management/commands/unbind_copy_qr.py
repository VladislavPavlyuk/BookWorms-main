"""Force-unbind all BookCopy QR tokens (late-binding reset)."""
from django.core.management.base import BaseCommand
from django.db import transaction

from mainApp.models import BookCopy, PreprintedQrToken


class Command(BaseCommand):
    help = "Clear qr_token/qr_attached_at on all BookCopy; unclaim PreprintedQrToken."

    def handle(self, *args, **options):
        with transaction.atomic():
            n_copies = BookCopy.objects.exclude(
                qr_token__isnull=True, qr_attached_at__isnull=True
            ).update(qr_token=None, qr_attached_at=None)
            n_pool = PreprintedQrToken.objects.exclude(
                copy__isnull=True, claimed_at__isnull=True
            ).update(copy=None, claimed_at=None)
        left_bound = BookCopy.objects.exclude(qr_token__isnull=True).count()
        left_claimed = PreprintedQrToken.objects.exclude(copy__isnull=True).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"cleared_copies={n_copies} unclaimed_pool={n_pool} "
                f"remaining_bound={left_bound} remaining_claimed={left_claimed}"
            )
        )
