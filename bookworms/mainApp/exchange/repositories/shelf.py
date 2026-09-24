"""Django ORM ShelfRepository (live DB)."""
from __future__ import annotations

from django.db.models import Exists, OuterRef, QuerySet

from ...models import Shelf
from .ports import IShelfRepository


class ShelfRepository(IShelfRepository):
    def find_available_owned(
        self, exclude_user_id: int | None = None
    ) -> QuerySet[Shelf]:
        active_loan = Shelf.objects.filter(
            copy_id=OuterRef("copy_id"),
            borrowed_from__isnull=False,
        ).exclude(copy_id__isnull=True)
        qs = Shelf.objects.filter(borrowed_from__isnull=True).exclude(
            Exists(active_loan)
        )
        if exclude_user_id is not None:
            qs = qs.exclude(user_id=exclude_user_id)
        return qs

    def find_physical_presence(
        self, exclude_user_id: int | None = None
    ) -> QuerySet[Shelf]:
        active_loan = Shelf.objects.filter(
            copy_id=OuterRef("copy_id"),
            borrowed_from__isnull=False,
        ).exclude(copy_id__isnull=True)
        at_owner = Shelf.objects.filter(borrowed_from__isnull=True).exclude(
            Exists(active_loan)
        )
        at_borrower = Shelf.objects.filter(borrowed_from__isnull=False)
        qs = (at_owner | at_borrower).distinct()
        if exclude_user_id is not None:
            qs = qs.exclude(user_id=exclude_user_id)
        return qs

    def exists_active_loan_for_copy(self, copy_id: int | None) -> bool:
        if not copy_id:
            return False
        return Shelf.objects.filter(
            copy_id=copy_id,
            borrowed_from__isnull=False,
        ).exists()

    def find_loan_rows_by_copy_ids(
        self, copy_ids: list[int]
    ) -> dict[int, Shelf]:
        if not copy_ids:
            return {}
        out: dict[int, Shelf] = {}
        for row in Shelf.objects.filter(
            copy_id__in=copy_ids, borrowed_from__isnull=False
        ).select_related("user", "book", "copy", "borrowed_from"):
            out[row.copy_id] = row
        return out

    def find_owner_shelf_ids_by_copy_ids(
        self, copy_ids: list[int]
    ) -> dict[int, int]:
        if not copy_ids:
            return {}
        out: dict[int, int] = {}
        for row in Shelf.objects.filter(
            copy_id__in=copy_ids, borrowed_from__isnull=True
        ).only("id", "copy_id"):
            if row.copy_id:
                out[row.copy_id] = row.id
        return out
