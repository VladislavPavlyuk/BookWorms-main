"""Library repository interface (DIP) — DB access only."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models import CustomUser, Library, LibraryAction, LibraryMembership, Shelf


class ILibraryRepository(ABC):
    @abstractmethod
    def find_membership_for_user(self, user_id: int) -> LibraryMembership | None:
        """Membership row with library (+ admin) selected, or None."""

    @abstractmethod
    def create_personal_library(self, user: CustomUser) -> Library:
        """Create library + admin membership; attach orphan owned copies."""

    @abstractmethod
    def count_memberships(self, library_id: int) -> int:
        """Number of members in the library."""

    @abstractmethod
    def count_isbn(self, library_id: int, book_id: int) -> int:
        """How many copies of book_id belong to the library."""

    @abstractmethod
    def find_isbn_count_rows(self, library_id: int) -> list[dict[str, Any]]:
        """Raw ISBN aggregation rows for a library."""

    @abstractmethod
    def find_owned_shelf_by_id(self, shelf_id: int) -> Shelf | None:
        """Owned shelf (borrowed_from is null) with copy relations, or None."""

    @abstractmethod
    def find_shelf_for_removal(self, shelf_id: int) -> Shelf | None:
        """Shelf loaded for remove_library_copy (copy/book/owner relations)."""

    @abstractmethod
    def find_owned_shelves_for_copy(self, copy_id: int) -> list[Shelf]:
        """All owned shelf rows for a physical copy."""

    @abstractmethod
    def detach_copy_from_library(self, copy_id: int) -> int:
        """Set BookCopy.library = NULL. Returns rows updated."""

    @abstractmethod
    def create_action(
        self,
        *,
        library: Library,
        initiator: CustomUser,
        action_type: str,
        payload: dict[str, Any],
    ) -> LibraryAction:
        """Persist a pending LibraryAction."""

    @abstractmethod
    def find_pending_action_by_id(self, action_id: int) -> LibraryAction | None:
        """Pending action by pk, or None."""

    @abstractmethod
    def find_pending_actions_for_admin_from(
        self, admin_id: int, initiator_id: int
    ) -> list[LibraryAction]:
        """Pending actions where admin owns the library and initiator is partner."""

    @abstractmethod
    def find_pending_actions_by_initiator_to_admin(
        self, initiator_id: int, admin_id: int
    ) -> list[LibraryAction]:
        """Pending actions started by initiator awaiting admin."""

    @abstractmethod
    def find_active_loans_by_copy(self, library_id: int) -> dict[int, Shelf]:
        """copy_id → active loan shelf for copies in the library."""
