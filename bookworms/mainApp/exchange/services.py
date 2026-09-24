"""Concrete service implementations (``I*Service`` → ``*Service``).

Procedural modules hold the logic; these classes are the injectable surface.
Imports of use-case modules are lazy to avoid circular deps with ``deps``.
"""
from __future__ import annotations

from django.db.models import QuerySet

from ..models import Book, BookExchangeRequest, CustomUser, LoanHandoff, Shelf
from .service_ports import (
    ICatalogService,
    ICopyService,
    IHandoffService,
    IRequestService,
    IReturnService,
    IShelfQueryService,
)


class RequestService(IRequestService):
    def create(
        self,
        requester: CustomUser,
        target_shelf: Shelf,
        offer_shelf: Shelf | None = None,
        *,
        from_queue: bool = False,
        join_queue_if_busy: bool = True,
    ) -> BookExchangeRequest:
        from . import requests as m

        return m.create_exchange_request(
            requester,
            target_shelf,
            offer_shelf,
            from_queue=from_queue,
            join_queue_if_busy=join_queue_if_busy,
        )

    def create_many(
        self,
        requester: CustomUser,
        lines: list[tuple[Shelf, Shelf | None]],
    ) -> tuple[int, list[str]]:
        from . import requests as m

        return m.create_many_exchange_requests(requester, lines)

    def accept(self, request_id: int, acting_user: CustomUser) -> None:
        from . import requests as m

        return m.accept_exchange_request(request_id, acting_user)

    def reject(self, request_id: int, acting_user: CustomUser) -> None:
        from . import requests as m

        return m.reject_exchange_request(request_id, acting_user)

    def cancel(self, request_id: int, acting_user: CustomUser) -> None:
        from . import requests as m

        return m.cancel_exchange_request(request_id, acting_user)


class HandoffService(IHandoffService):
    def active_for_copy(self, copy_id: int | None) -> LoanHandoff | None:
        from . import handoff as m

        return m.active_handoff_for_copy(copy_id)

    def involving(self, *user_ids: int) -> list[LoanHandoff]:
        from . import handoff as m

        return m.handoffs_involving(*user_ids)

    def approve(
        self,
        req: BookExchangeRequest,
        owner: CustomUser,
        owner_shelf: Shelf,
        requester: CustomUser,
    ) -> LoanHandoff:
        from . import handoff as m

        return m.approve_loan_handoff(req, owner, owner_shelf, requester)

    def confirm_give(self, handoff_id: int, acting_user: CustomUser) -> None:
        from . import handoff as m

        return m.confirm_handoff_give(handoff_id, acting_user)

    def confirm_receive(self, handoff_id: int, acting_user: CustomUser) -> None:
        from . import handoff as m

        return m.confirm_handoff_receive(handoff_id, acting_user)

    def cancel(self, handoff_id: int, acting_user: CustomUser) -> None:
        from . import handoff as m

        return m.cancel_loan_handoff(handoff_id, acting_user)

    def transmit(
        self,
        req: BookExchangeRequest,
        owner: CustomUser,
        owner_shelf: Shelf,
        requester: CustomUser,
    ) -> LoanHandoff:
        from . import handoff as m

        return m.transmit_loan_to_requester(req, owner, owner_shelf, requester)


class ReturnService(IReturnService):
    def request_return(self, shelf_id: int, borrower: CustomUser) -> None:
        from . import returns as m

        return m.request_borrow_return(shelf_id, borrower)

    def confirm_return(self, shelf_id: int, lender: CustomUser) -> None:
        from . import returns as m

        return m.confirm_borrow_return(shelf_id, lender)


class CatalogService(ICatalogService):
    def get_or_create_from_payload(self, payload: dict) -> tuple[Book, bool]:
        from . import catalog as m

        return m.get_or_create_book_from_payload(payload)

    def sync_from_payload(self, book: Book, payload: dict) -> Book:
        from . import catalog as m

        return m.sync_book_from_payload(book, payload)

    def resolve_and_sync_by_isbn(self, raw_isbn: str) -> Book:
        from . import catalog as m

        return m.resolve_and_sync_book_by_isbn(raw_isbn)


class CopyService(ICopyService):
    def add_owned(self, user: CustomUser, book: Book) -> Shelf:
        from . import copies as m

        return m.add_owned_copy(user, book)

    def remove_owned(self, shelf: Shelf) -> None:
        from . import copies as m

        return m.remove_owned_shelf(shelf)

    def ensure_shelf_copy(self, shelf: Shelf) -> Shelf:
        from . import copies as m

        return m.ensure_shelf_copy(shelf)

    def ensure_shelves_have_copies(self, shelves: list[Shelf]) -> list[Shelf]:
        from . import copies as m

        return m.ensure_shelves_have_copies(shelves)

    def is_copy_lent_out(self, copy_id: int | None) -> bool:
        from . import copies as m

        return m.is_copy_lent_out(copy_id)

    def is_book_lent_out(self, owner_id: int, book_id: int) -> bool:
        from . import copies as m

        return m.is_book_lent_out(owner_id, book_id)


class ShelfQueryService(IShelfQueryService):
    def available_owned_qs(
        self, exclude_user_id: int | None = None
    ) -> QuerySet[Shelf]:
        from . import shelves as m

        return m.available_owned_shelves_qs(exclude_user_id)

    def physical_presence_qs(
        self, exclude_user_id: int | None = None
    ) -> QuerySet[Shelf]:
        from . import shelves as m

        return m.physical_presence_shelves_qs(exclude_user_id)

    def browsable_owned_qs(
        self, exclude_user_id: int | None = None
    ) -> QuerySet[Shelf]:
        from . import shelves as m

        return m.browsable_owned_shelves_qs(exclude_user_id)

    def attach_loan_info(self, shelves: list[Shelf]) -> list[Shelf]:
        from . import shelves as m

        return m.attach_loan_info(shelves)

    def attach_request_targets(self, shelves: list[Shelf]) -> list[Shelf]:
        from . import shelves as m

        return m.attach_request_targets(shelves)

    def filter_physically_present(self, shelves: list[Shelf]) -> list[Shelf]:
        from . import shelves as m

        return m.filter_physically_present(shelves)

    def group_by_book(self, shelves) -> list[dict]:
        from . import shelves as m

        return m.group_shelves_by_book(shelves)

    def load_browse_catalog(self, viewer: CustomUser, *, ensure_copies: bool = False):
        from . import shelves as m

        return m.load_browse_catalog(viewer, ensure_copies=ensure_copies)

    def for_user_physical_shelf(
        self, owner: CustomUser, *, ensure_copies: bool = False
    ) -> list[Shelf]:
        from . import shelves as m

        return m.for_user_physical_shelf(owner, ensure_copies=ensure_copies)

    def for_book_physical_holders(
        self, book, *, ensure_copies: bool = False
    ) -> list[Shelf]:
        from . import shelves as m

        return m.for_book_physical_holders(book, ensure_copies=ensure_copies)

    def for_copy_physical_holders(
        self, copy, *, ensure_copies: bool = False
    ) -> list[Shelf]:
        from . import shelves as m

        return m.for_copy_physical_holders(copy, ensure_copies=ensure_copies)

    def get_available_owned_offer(
        self, user: CustomUser, offer_shelf_id: int
    ) -> Shelf | None:
        from . import shelves as m

        return m.get_available_owned_offer(user, offer_shelf_id)
