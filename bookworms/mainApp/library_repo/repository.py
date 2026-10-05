"""Django ORM LibraryRepository (live DB)."""
from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Count

from ..models import (
    BookCopy,
    CustomUser,
    Library,
    LibraryAction,
    LibraryMembership,
    Shelf,
)
from .ports import ILibraryRepository


class LibraryRepository(ILibraryRepository):
    def find_membership_for_user(self, user_id: int) -> LibraryMembership | None:
        return (
            LibraryMembership.objects.select_related("library", "library__admin")
            .filter(user_id=user_id)
            .first()
        )

    def create_personal_library(self, user: CustomUser) -> Library:
        with transaction.atomic():
            lib = Library.objects.create(
                name=f"Бібліотека {user.username}",
                admin=user,
            )
            LibraryMembership.objects.create(
                library=lib,
                user=user,
                role=LibraryMembership.Role.ADMIN,
            )
            BookCopy.objects.filter(owner=user, library__isnull=True).update(
                library=lib,
                added_by=user,
            )
            return lib

    def count_memberships(self, library_id: int) -> int:
        return LibraryMembership.objects.filter(library_id=library_id).count()

    def count_isbn(self, library_id: int, book_id: int) -> int:
        return BookCopy.objects.filter(library_id=library_id, book_id=book_id).count()

    def find_isbn_count_rows(self, library_id: int) -> list[dict[str, Any]]:
        return list(
            BookCopy.objects.filter(library_id=library_id)
            .values("book_id", "book__isbn", "book__title")
            .annotate(n=Count("id"))
            .order_by("book__title")
        )

    def find_owned_shelf_by_id(self, shelf_id: int) -> Shelf | None:
        return (
            Shelf.objects.select_related(
                "copy",
                "copy__book",
                "copy__owner",
                "copy__added_by",
                "book",
                "user",
            )
            .filter(pk=shelf_id, borrowed_from__isnull=True)
            .first()
        )

    def find_shelf_for_removal(self, shelf_id: int) -> Shelf | None:
        return (
            Shelf.objects.select_related(
                "copy",
                "copy__book",
                "copy__owner",
                "copy__added_by",
                "copy__library",
                "book",
                "user",
            )
            .filter(pk=shelf_id)
            .first()
        )

    def find_owned_shelves_for_copy(self, copy_id: int) -> list[Shelf]:
        return list(
            Shelf.objects.filter(copy_id=copy_id, borrowed_from__isnull=True).select_related(
                "user", "copy"
            )
        )

    def detach_copy_from_library(self, copy_id: int) -> int:
        return BookCopy.objects.filter(pk=copy_id).update(library=None)

    def create_action(
        self,
        *,
        library: Library,
        initiator: CustomUser,
        action_type: str,
        payload: dict[str, Any],
    ) -> LibraryAction:
        return LibraryAction.objects.create(
            library=library,
            initiator=initiator,
            action_type=action_type,
            payload=payload,
        )

    def find_pending_action_by_id(self, action_id: int) -> LibraryAction | None:
        return (
            LibraryAction.objects.select_related("library", "initiator", "library__admin")
            .filter(pk=action_id, status=LibraryAction.Status.PENDING)
            .first()
        )

    def find_pending_actions_for_admin_from(
        self, admin_id: int, initiator_id: int
    ) -> list[LibraryAction]:
        return list(
            LibraryAction.objects.filter(
                status=LibraryAction.Status.PENDING,
                library__admin_id=admin_id,
                initiator_id=initiator_id,
            ).select_related("initiator", "library")
        )

    def find_pending_actions_by_initiator_to_admin(
        self, initiator_id: int, admin_id: int
    ) -> list[LibraryAction]:
        return list(
            LibraryAction.objects.filter(
                status=LibraryAction.Status.PENDING,
                initiator_id=initiator_id,
                library__admin_id=admin_id,
            ).select_related("initiator", "library")
        )

    def find_active_loans_by_copy(self, library_id: int) -> dict[int, Shelf]:
        out: dict[int, Shelf] = {}
        for row in Shelf.objects.filter(
            borrowed_from__isnull=False,
            copy__library_id=library_id,
        ).select_related("user", "book", "copy", "borrowed_from"):
            if row.copy_id:
                out[row.copy_id] = row
        return out
