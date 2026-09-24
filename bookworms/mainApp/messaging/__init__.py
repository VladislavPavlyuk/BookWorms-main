"""Messaging domain — partners + exchange/handoff chat thread."""
from __future__ import annotations

from .exceptions import MessagingForbidden, MessagingNoPartners, MessagingNotFound
from .ports import IMessagingService
from .service import MessagingService, get_messaging_service, set_messaging_service
from .thread import ThreadContext

__all__ = [
    "IMessagingService",
    "MessagingForbidden",
    "MessagingNoPartners",
    "MessagingNotFound",
    "MessagingService",
    "ThreadContext",
    "get_messaging_service",
    "set_messaging_service",
]
