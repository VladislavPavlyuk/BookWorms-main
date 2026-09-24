"""Composition root for exchange ports + services (DIP).

Outbound: ``IExchangeNotifier`` / ``ICopyQueue``
Application: ``IRequestService`` / ``IHandoffService`` / …
"""
from __future__ import annotations

from .adapters import MessageServiceNotifier, QueueServiceAdapter
from .ports import ICopyQueue, IExchangeNotifier
from .service_ports import (
    ICatalogService,
    ICopyService,
    IHandoffService,
    IRequestService,
    IReturnService,
    IShelfQueryService,
)
from .services import (
    CatalogService,
    CopyService,
    HandoffService,
    RequestService,
    ReturnService,
    ShelfQueryService,
)

_notifier: IExchangeNotifier = MessageServiceNotifier()
_queue: ICopyQueue = QueueServiceAdapter()

_requests: IRequestService = RequestService()
_handoff: IHandoffService = HandoffService()
_returns: IReturnService = ReturnService()
_catalog: ICatalogService = CatalogService()
_copies: ICopyService = CopyService()
_shelves: IShelfQueryService = ShelfQueryService()


def get_notifier() -> IExchangeNotifier:
    return _notifier


def get_queue() -> ICopyQueue:
    return _queue


def set_notifier(notifier: IExchangeNotifier) -> None:
    global _notifier
    _notifier = notifier


def set_queue(queue: ICopyQueue) -> None:
    global _queue
    _queue = queue


def get_request_service() -> IRequestService:
    return _requests


def get_handoff_service() -> IHandoffService:
    return _handoff


def get_return_service() -> IReturnService:
    return _returns


def get_catalog_service() -> ICatalogService:
    return _catalog


def get_copy_service() -> ICopyService:
    return _copies


def get_shelf_query_service() -> IShelfQueryService:
    return _shelves


def set_request_service(svc: IRequestService) -> None:
    global _requests
    _requests = svc


def set_handoff_service(svc: IHandoffService) -> None:
    global _handoff
    _handoff = svc


def set_return_service(svc: IReturnService) -> None:
    global _returns
    _returns = svc


def set_catalog_service(svc: ICatalogService) -> None:
    global _catalog
    _catalog = svc


def set_copy_service(svc: ICopyService) -> None:
    global _copies
    _copies = svc


def set_shelf_query_service(svc: IShelfQueryService) -> None:
    global _shelves
    _shelves = svc


def reset_defaults() -> None:
    set_notifier(MessageServiceNotifier())
    set_queue(QueueServiceAdapter())
    set_request_service(RequestService())
    set_handoff_service(HandoffService())
    set_return_service(ReturnService())
    set_catalog_service(CatalogService())
    set_copy_service(CopyService())
    set_shelf_query_service(ShelfQueryService())
