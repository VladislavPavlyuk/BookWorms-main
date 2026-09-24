"""Owned copies & lent-out checks (SRP)."""
from __future__ import annotations

from ..copy_events import log_copy_event
from ..models import Book, BookCopy, CopyEvent, CustomUser, Shelf


def add_owned_copy(user: CustomUser, book: Book) -> Shelf:
    """Новий фізичний примірник на полиці власника."""
    copy = BookCopy.objects.create(book=book, owner=user)
    shelf = Shelf.objects.create(user=user, book=book, copy=copy)
    log_copy_event(
        copy,
        CopyEvent.Code.ADDED,
        actor=user,
        holder=user,
        legal_owner=user,
    )
    return shelf


def remove_owned_shelf(shelf: Shelf) -> None:
    """Прибрати власний рядок. BookCopy лишається — історія подій примірника."""
    copy = shelf.copy
    user = shelf.user
    log_copy_event(
        copy,
        CopyEvent.Code.REMOVED,
        actor=user,
        holder=user,
        legal_owner=copy.owner if copy else user,
        previous_holder=user,
    )
    shelf.delete()


def ensure_shelf_copy(shelf: Shelf) -> Shelf:
    """Якщо рядок полиці без BookCopy (старі дані) — створити примірник і прив’язати."""
    if shelf.copy_id:
        return shelf
    owner_id = shelf.borrowed_from_id or shelf.user_id
    copy = BookCopy.objects.create(book_id=shelf.book_id, owner_id=owner_id)
    Shelf.objects.filter(pk=shelf.pk).update(copy_id=copy.pk)
    shelf.copy_id = copy.pk
    shelf.copy = copy
    return shelf


def ensure_shelves_have_copies(shelves: list[Shelf]) -> list[Shelf]:
    return [ensure_shelf_copy(s) for s in shelves]


def is_copy_lent_out(copy_id: int | None) -> bool:
    """Чи є активна позика цього примірника."""
    if not copy_id:
        return False
    return Shelf.objects.filter(
        copy_id=copy_id,
        borrowed_from__isnull=False,
    ).exists()


def is_book_lent_out(owner_id: int, book_id: int) -> bool:
    """Legacy ISBN-level «у від'їзді»; для блокувань краще is_copy_lent_out."""
    return Shelf.objects.filter(
        borrowed_from_id=owner_id,
        book_id=book_id,
    ).exists()
