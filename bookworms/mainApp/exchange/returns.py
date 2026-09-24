"""Borrow return request / confirm (SRP)."""
from __future__ import annotations

from django.db import transaction

from .deps import get_notifier, get_queue
from .. import ops_log
from ..copy_events import log_copy_event
from ..error_handling import domain_guard
from ..exceptions import ExchangeConflict, ExchangeInvalidState, ExchangeNotFound
from ..models import BookCopy, CopyEvent, CustomUser, Shelf
from .handoff import active_handoff_for_copy


def _lock_borrower_return_shelf(shelf_id: int, borrower: CustomUser) -> Shelf:
    shelf = (
        Shelf.objects.select_for_update(of=("self",))
        .select_related("borrowed_from", "book", "copy")
        .filter(pk=shelf_id, user=borrower)
        .first()
    )
    if not shelf:
        raise ExchangeNotFound("Запис на полиці не знайдено.")
    if not shelf.borrowed_from_id:
        raise ExchangeInvalidState(
            "Ця книга не позичена - її можна просто прибрати з полиці."
        )
    if shelf.return_pending:
        raise ExchangeConflict("Повернення вже очікує підтвердження позикодавця.")
    if active_handoff_for_copy(shelf.copy_id):
        ops_log.warning(
            "return.blocked_by_handoff",
            shelf_id=shelf_id,
            user_id=borrower.id,
            copy_id=shelf.copy_id,
        )
        raise ExchangeConflict(
            "Для цього примірника схвалено передачу наступному читачу. "
            "Не «Повернути власнику», а в чаті натисніть «Я віддав книгу»."
        )
    return shelf


def _lock_pending_return_shelf(shelf_id: int, lender: CustomUser) -> Shelf:
    shelf = (
        Shelf.objects.select_for_update(of=("self",))
        .select_related("book", "user", "copy")
        .filter(pk=shelf_id, borrowed_from=lender, return_pending=True)
        .first()
    )
    if not shelf:
        raise ExchangeNotFound(
            "Немає запису з очікуванням вашого підтвердження повернення."
        )
    if active_handoff_for_copy(shelf.copy_id):
        raise ExchangeConflict(
            "Спочатку скасуйте активну фізичну передачу цього примірника."
        )
    return shelf


def _restore_or_delete_loan_shelf(shelf: Shelf, lender: CustomUser) -> None:
    """Owner row missing → convert borrower row back to owner; else delete loan row."""
    owner_id = lender.id
    copy_id = shelf.copy_id
    owner_row = (
        Shelf.objects.select_for_update(of=("self",))
        .filter(user_id=owner_id, copy_id=copy_id, borrowed_from__isnull=True)
        .first()
    )
    if not owner_row:
        Shelf.objects.filter(pk=shelf.pk).update(
            user_id=owner_id,
            borrowed_from_id=None,
            return_pending=False,
            due_date=None,
        )
        if copy_id:
            BookCopy.objects.filter(pk=copy_id).update(owner_id=owner_id)
    else:
        shelf.delete()


def _offer_queue_after_return(copy_id: int, lender: CustomUser) -> None:
    try:
        get_queue().offer_next_after_return(copy_id, lender)
    except Exception:
        # Черга не повинна валити підтвердження повернення
        pass


@domain_guard("exchange.return_request")
@transaction.atomic
def request_borrow_return(shelf_id: int, borrower: CustomUser) -> None:
    """Позичальник повідомляє про повернення; рядок лишається до confirm."""
    shelf = _lock_borrower_return_shelf(shelf_id, borrower)
    Shelf.objects.filter(pk=shelf.pk).update(return_pending=True)
    shelf.return_pending = True
    log_copy_event(
        shelf.copy_id,
        CopyEvent.Code.RETURN_REQUESTED,
        actor=borrower,
        holder=borrower,
        legal_owner=shelf.borrowed_from,
        counterparty=shelf.borrowed_from,
    )
    get_notifier().notify_borrow_return_requested(shelf)


@domain_guard("exchange.return_confirm")
@transaction.atomic
def confirm_borrow_return(shelf_id: int, lender: CustomUser) -> None:
    """Позикодавець підтверджує отримання: знімає позику з полиці позичальника."""
    shelf = _lock_pending_return_shelf(shelf_id, lender)
    borrower = shelf.user
    book_title = shelf.book.title
    copy_id = shelf.copy_id
    shelf_pk = shelf.pk

    get_notifier().mark_return_notifications_read(
        lender,
        shelf_id=shelf_pk,
        borrower_id=borrower.id,
        book_title=book_title,
    )
    _restore_or_delete_loan_shelf(shelf, lender)
    log_copy_event(
        copy_id,
        CopyEvent.Code.RETURNED,
        actor=lender,
        holder=lender,
        legal_owner=lender,
        previous_holder=borrower,
        counterparty=borrower,
    )
    get_notifier().notify_borrow_return_confirmed(lender, borrower, book_title)
    if copy_id:
        _offer_queue_after_return(copy_id, lender)
