"""Messaging errors."""
from __future__ import annotations


class MessagingError(Exception):
    def __init__(self, message: str):
        super().__init__(message)

    @property
    def message(self) -> str:
        return str(self)


class MessagingForbidden(MessagingError):
    """User is not allowed to open/send in this thread."""


class MessagingNoPartners(MessagingForbidden):
    """User has no active exchange partners at all."""


class MessagingNotFound(MessagingError):
    """Partner user does not exist."""
