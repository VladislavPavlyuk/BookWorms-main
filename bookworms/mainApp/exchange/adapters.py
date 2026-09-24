"""Concrete adapters — implement Abstract* (which implement I*)."""
from __future__ import annotations

from .. import message_service
from .. import queue_service
from ..models import BookCopy, BookExchangeRequest, CustomUser, LoanHandoff, Shelf
from .abstract import AbstractCopyQueue, AbstractExchangeNotifier


class MessageServiceNotifier(AbstractExchangeNotifier):
    """Django PrivateMessage / notification side-effects."""

    def notify_exchange_request_created(self, req: BookExchangeRequest):
        return message_service.notify_exchange_request_created(req)

    def notify_transmission_request_created(self, req: BookExchangeRequest):
        return message_service.notify_transmission_request_created(req)

    def notify_exchange_request_accepted(self, req: BookExchangeRequest):
        return message_service.notify_exchange_request_accepted(req)

    def notify_exchange_request_rejected(self, req: BookExchangeRequest):
        return message_service.notify_exchange_request_rejected(req)

    def notify_exchange_request_cancelled(self, req: BookExchangeRequest):
        return message_service.notify_exchange_request_cancelled(req)

    def _emit_handoff(self, handoff: LoanHandoff, *, stage: str) -> None:
        if stage == "approved":
            message_service.notify_handoff_approved(handoff)
        elif stage == "given":
            message_service.notify_handoff_given(handoff)
        elif stage == "cancelled":
            message_service.notify_handoff_cancelled(handoff)
        else:
            raise ValueError(f"unknown handoff stage: {stage}")

    def notify_loan_transmitted(
        self,
        owner: CustomUser,
        previous_holder: CustomUser,
        new_holder: CustomUser,
        book_title: str,
        exchange_request: BookExchangeRequest | None = None,
    ) -> None:
        message_service.notify_loan_transmitted(
            owner,
            previous_holder,
            new_holder,
            book_title,
            exchange_request=exchange_request,
        )

    def notify_borrow_return_requested(self, shelf: Shelf):
        return message_service.notify_borrow_return_requested(shelf)

    def notify_borrow_return_confirmed(
        self, lender: CustomUser, borrower: CustomUser, book_title: str
    ):
        return message_service.notify_borrow_return_confirmed(
            lender, borrower, book_title
        )

    def mark_return_notifications_read(
        self, lender: CustomUser, *, shelf_id: int, borrower_id: int, book_title: str
    ) -> int:
        return message_service.mark_return_notifications_read(
            lender,
            shelf_id=shelf_id,
            borrower_id=borrower_id,
            book_title=book_title,
        )


class QueueServiceAdapter(AbstractCopyQueue):
    """Django CopyQueueEntry side-effects."""

    def join_queue(
        self, user: CustomUser, copy: BookCopy, *, notify: bool = True, exchange_request=None
    ):
        return queue_service.join_queue(
            user, copy, notify=notify, exchange_request=exchange_request
        )

    def leave_queue(self, user: CustomUser, copy_id: int):
        return queue_service.leave_queue(user, copy_id)

    def after_copy_loaned_or_transmitted(
        self, copy_id: int, new_holder_id: int
    ) -> None:
        queue_service.after_copy_loaned_or_transmitted(copy_id, new_holder_id)

    def offer_next_after_return(
        self, copy_id: int, owner: CustomUser
    ) -> BookExchangeRequest | None:
        return queue_service.offer_next_after_return(copy_id, owner)
