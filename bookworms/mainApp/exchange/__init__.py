"""
Exchange domain — SOLID slice.

SRP modules:
  due.py      — loan due-date policy
  copies.py   — BookCopy / owned shelf mutations + lent checks
  catalog.py  — ISBN Book resolve/sync (metadata → Book)
  shelves.py  — query objects for browse / physical presence
  requests.py — create / accept / reject / cancel exchange requests
  handoff.py  — third-party physical transfer (approve → give → receive)
  returns.py  — borrow return request / confirm

DIP: HTTP (api/views, mainApp/views) depends on this package facade,
not the other way around. Notifiers/queue stay as application services
imported at call sites (Django style); Protocols in ports.py document
the boundaries.

Compat: ``mainApp.exchange_service`` re-exports this public API.
"""
from __future__ import annotations

from .catalog import (
    get_or_create_book_from_payload,
    resolve_and_sync_book_by_isbn,
    sync_book_from_payload,
)
from .copies import (
    add_owned_copy,
    ensure_shelf_copy,
    ensure_shelves_have_copies,
    is_book_lent_out,
    is_copy_lent_out,
    remove_owned_shelf,
)
from .due import loan_due_date
from .handoff import (
    active_handoff_for_copy,
    approve_loan_handoff,
    cancel_loan_handoff,
    confirm_handoff_give,
    confirm_handoff_receive,
    handoffs_involving,
    transmit_loan_to_requester,
)
from .requests import (
    accept_exchange_request,
    cancel_exchange_request,
    create_exchange_request,
    create_many_exchange_requests,
    reject_exchange_request,
)
from .returns import confirm_borrow_return, request_borrow_return
from .shelves import (
    attach_loan_info,
    attach_request_targets,
    available_owned_shelves_qs,
    browsable_owned_shelves_qs,
    filter_physically_present,
    group_shelves_by_book,
    physical_presence_shelves_qs,
)

# Legacy private names still imported by older call sites / tests
_loan_due_date = loan_due_date
_approve_loan_handoff = approve_loan_handoff
_transmit_loan_to_requester = transmit_loan_to_requester

__all__ = [
    "accept_exchange_request",
    "active_handoff_for_copy",
    "add_owned_copy",
    "approve_loan_handoff",
    "attach_loan_info",
    "attach_request_targets",
    "available_owned_shelves_qs",
    "browsable_owned_shelves_qs",
    "cancel_exchange_request",
    "cancel_loan_handoff",
    "confirm_borrow_return",
    "confirm_handoff_give",
    "confirm_handoff_receive",
    "create_exchange_request",
    "create_many_exchange_requests",
    "ensure_shelf_copy",
    "ensure_shelves_have_copies",
    "filter_physically_present",
    "get_or_create_book_from_payload",
    "group_shelves_by_book",
    "handoffs_involving",
    "is_book_lent_out",
    "is_copy_lent_out",
    "loan_due_date",
    "physical_presence_shelves_qs",
    "reject_exchange_request",
    "remove_owned_shelf",
    "request_borrow_return",
    "resolve_and_sync_book_by_isbn",
    "sync_book_from_payload",
    "transmit_loan_to_requester",
    "_loan_due_date",
    "_approve_loan_handoff",
    "_transmit_loan_to_requester",
]
