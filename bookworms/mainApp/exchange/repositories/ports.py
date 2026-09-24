"""Repository interfaces (DIP) — DB access only."""
from __future__ import annotations

from abc import ABC, abstractmethod

from django.db.models import QuerySet

from ...models import Shelf


class IShelfRepository(ABC):
    @abstractmethod
    def find_available_owned(
        self, exclude_user_id: int | None = None
    ) -> QuerySet[Shelf]:
        """Owner rows that are not currently lent out."""

    @abstractmethod
    def find_physical_presence(
        self, exclude_user_id: int | None = None
    ) -> QuerySet[Shelf]:
        """Rows where the copy physically is (owner if free, borrower if lent)."""

    @abstractmethod
    def exists_active_loan_for_copy(self, copy_id: int | None) -> bool:
        """True if any Shelf has borrowed_from set for this copy."""

    @abstractmethod
    def find_loan_rows_by_copy_ids(
        self, copy_ids: list[int]
    ) -> dict[int, Shelf]:
        """copy_id → active loan Shelf row."""

    @abstractmethod
    def find_owner_shelf_ids_by_copy_ids(
        self, copy_ids: list[int]
    ) -> dict[int, int]:
        """copy_id → owner Shelf.pk (borrowed_from is null)."""
