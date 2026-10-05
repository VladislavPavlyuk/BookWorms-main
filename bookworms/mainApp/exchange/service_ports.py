"""Service-layer interfaces (above implementations).

Pattern (same as repositories): ``I*Service`` + concrete ``*Service``.
Use-cases / HTTP depend on these interfaces via ``deps``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from django.db.models import QuerySet

from ..models import Book, BookExchangeRequest, CustomUser, LoanHandoff, Shelf


class IRequestService(ABC):
    @abstractmethod
    def create(
        self,
        requester: CustomUser,
        target_shelf: Shelf,
        offer_shelf: Shelf | None = None,
        *,
        from_queue: bool = False,
        join_queue_if_busy: bool = True,
        proposed_due_date=None,
    ) -> BookExchangeRequest: ...

    @abstractmethod
    def create_many(
        self,
        requester: CustomUser,
        lines: list[tuple[Shelf, Shelf | None, object | None]],
    ) -> tuple[int, list[str]]: ...

    @abstractmethod
    def accept(
        self, request_id: int, acting_user: CustomUser, *, due_date=None
    ) -> None: ...

    @abstractmethod
    def propose_due(
        self, request_id: int, acting_user: CustomUser, due_date
    ) -> BookExchangeRequest: ...

    @abstractmethod
    def confirm_due(
        self, request_id: int, acting_user: CustomUser
    ) -> BookExchangeRequest: ...

    @abstractmethod
    def reject(self, request_id: int, acting_user: CustomUser) -> None: ...

    @abstractmethod
    def cancel(self, request_id: int, acting_user: CustomUser) -> None: ...


class IHandoffService(ABC):
    @abstractmethod
    def active_for_copy(self, copy_id: int | None) -> LoanHandoff | None: ...

    @abstractmethod
    def involving(self, *user_ids: int) -> list[LoanHandoff]: ...

    @abstractmethod
    def approve(
        self,
        req: BookExchangeRequest,
        owner: CustomUser,
        owner_shelf: Shelf,
        requester: CustomUser,
    ) -> LoanHandoff: ...

    @abstractmethod
    def confirm_give(
        self,
        handoff_id: int,
        acting_user: CustomUser,
        *,
        qr_payload: str | None = None,
    ) -> None: ...

    @abstractmethod
    def confirm_receive(
        self,
        handoff_id: int,
        acting_user: CustomUser,
        *,
        qr_payload: str | None = None,
    ) -> None: ...

    @abstractmethod
    def cancel(self, handoff_id: int, acting_user: CustomUser) -> None: ...

    @abstractmethod
    def transmit(
        self,
        req: BookExchangeRequest,
        owner: CustomUser,
        owner_shelf: Shelf,
        requester: CustomUser,
    ) -> LoanHandoff: ...


class IReturnService(ABC):
    @abstractmethod
    def request_return(self, shelf_id: int, borrower: CustomUser) -> None: ...

    @abstractmethod
    def confirm_return(
        self, shelf_id: int, lender: CustomUser, *, qr_payload: str | None = None
    ) -> None: ...


class ICatalogService(ABC):
    @abstractmethod
    def get_or_create_from_payload(self, payload: dict) -> tuple[Book, bool]: ...

    @abstractmethod
    def sync_from_payload(self, book: Book, payload: dict) -> Book: ...

    @abstractmethod
    def resolve_and_sync_by_isbn(self, raw_isbn: str) -> Book: ...


class ICopyService(ABC):
    @abstractmethod
    def add_owned(self, user: CustomUser, book: Book) -> Shelf: ...

    @abstractmethod
    def remove_owned(self, shelf: Shelf) -> None: ...

    @abstractmethod
    def ensure_shelf_copy(self, shelf: Shelf) -> Shelf: ...

    @abstractmethod
    def ensure_shelves_have_copies(self, shelves: list[Shelf]) -> list[Shelf]: ...

    @abstractmethod
    def is_copy_lent_out(self, copy_id: int | None) -> bool: ...

    @abstractmethod
    def is_book_lent_out(self, owner_id: int, book_id: int) -> bool: ...


class IShelfQueryService(ABC):
    @abstractmethod
    def available_owned_qs(
        self, exclude_user_id: int | None = None
    ) -> QuerySet[Shelf]: ...

    @abstractmethod
    def physical_presence_qs(
        self, exclude_user_id: int | None = None
    ) -> QuerySet[Shelf]: ...

    @abstractmethod
    def browsable_owned_qs(
        self, exclude_user_id: int | None = None
    ) -> QuerySet[Shelf]: ...

    @abstractmethod
    def attach_loan_info(self, shelves: list[Shelf]) -> list[Shelf]: ...

    @abstractmethod
    def attach_request_targets(self, shelves: list[Shelf]) -> list[Shelf]: ...

    @abstractmethod
    def filter_physically_present(self, shelves: list[Shelf]) -> list[Shelf]: ...

    @abstractmethod
    def group_by_book(self, shelves) -> list[dict]: ...

    @abstractmethod
    def load_browse_catalog(self, viewer: CustomUser, *, ensure_copies: bool = False): ...

    @abstractmethod
    def for_user_physical_shelf(
        self,
        owner: CustomUser,
        *,
        ensure_copies: bool = False,
        viewer: CustomUser | None = None,
    ) -> list[Shelf]: ...

    @abstractmethod
    def for_book_physical_holders(
        self, book, *, ensure_copies: bool = False, viewer: CustomUser | None = None
    ) -> list[Shelf]: ...

    @abstractmethod
    def for_copy_physical_holders(
        self, copy, *, ensure_copies: bool = False
    ) -> list[Shelf]: ...

    @abstractmethod
    def get_available_owned_offer(
        self, user: CustomUser, offer_shelf_id: int
    ) -> Shelf | None: ...
