"""Exchange ports — INTERFACES (contracts only).

Hierarchy (DIP):
  I* interface  →  Abstract*  →  concrete adapters (adapters.py)
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import BookCopy, BookExchangeRequest, CustomUser, LoanHandoff, Shelf


class IExchangeNotifier(ABC):
    """Outbound notifications for exchange / loan / handoff / return."""

    @abstractmethod
    def notify_exchange_request_created(self, req: BookExchangeRequest) -> object: ...

    @abstractmethod
    def notify_transmission_request_created(self, req: BookExchangeRequest) -> object: ...

    @abstractmethod
    def notify_exchange_request_accepted(self, req: BookExchangeRequest) -> object: ...

    @abstractmethod
    def notify_exchange_request_rejected(self, req: BookExchangeRequest) -> object: ...

    @abstractmethod
    def notify_exchange_request_cancelled(self, req: BookExchangeRequest) -> object: ...

    @abstractmethod
    def notify_handoff_approved(self, handoff: LoanHandoff) -> None: ...

    @abstractmethod
    def notify_handoff_given(self, handoff: LoanHandoff) -> None: ...

    @abstractmethod
    def notify_handoff_cancelled(self, handoff: LoanHandoff) -> None: ...

    @abstractmethod
    def notify_loan_transmitted(
        self,
        owner: CustomUser,
        previous_holder: CustomUser,
        new_holder: CustomUser,
        book_title: str,
        exchange_request: BookExchangeRequest | None = None,
    ) -> None: ...

    @abstractmethod
    def notify_borrow_return_requested(self, shelf: Shelf) -> object: ...

    @abstractmethod
    def notify_borrow_return_confirmed(
        self, lender: CustomUser, borrower: CustomUser, book_title: str
    ) -> object: ...

    @abstractmethod
    def mark_return_notifications_read(
        self, lender: CustomUser, *, shelf_id: int, borrower_id: int, book_title: str
    ) -> int: ...


class ICopyQueue(ABC):
    """FIFO waiting list for a physical BookCopy."""

    @abstractmethod
    def join_queue(
        self, user: CustomUser, copy: BookCopy, *, notify: bool = True, exchange_request=None
    ): ...

    @abstractmethod
    def leave_queue(self, user: CustomUser, copy_id: int): ...

    @abstractmethod
    def after_copy_loaned_or_transmitted(
        self, copy_id: int, new_holder_id: int
    ) -> None: ...

    @abstractmethod
    def offer_next_after_return(
        self, copy_id: int, owner: CustomUser
    ) -> BookExchangeRequest | None: ...


# Back-compat aliases (old Protocol names)
ExchangeNotifier = IExchangeNotifier
CopyQueuePort = ICopyQueue
