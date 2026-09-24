"""IMessagingService — chat partners + thread (interface)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from django.db.models import QuerySet

from ..models import CustomUser, PrivateMessage
from .thread import ThreadContext


class IMessagingService(ABC):
    @abstractmethod
    def list_partners(self, user: CustomUser) -> QuerySet[CustomUser]:
        """Active exchange / loan / handoff / queue chat partners."""

    @abstractmethod
    def can_chat(self, user: CustomUser, partner_id: int) -> bool: ...

    @abstractmethod
    def open_thread(self, user: CustomUser, partner_id: int) -> ThreadContext:
        """Load timeline + handoff/return/request panels. Raises Messaging*."""

    @abstractmethod
    def send(
        self, sender: CustomUser, partner_id: int, body: str
    ) -> PrivateMessage | None:
        """Send user message if chat allowed. None = empty body."""
