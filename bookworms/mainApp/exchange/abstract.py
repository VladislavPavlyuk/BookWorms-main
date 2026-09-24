"""Abstract classes that sit *under* interfaces (ports) and *above* adapters."""
from __future__ import annotations

from abc import abstractmethod

from ..models import BookExchangeRequest, CustomUser, LoanHandoff, Shelf
from .ports import ICopyQueue, IExchangeNotifier


class AbstractExchangeNotifier(IExchangeNotifier):
    """
    Shared notifier skeleton.
    Handoff stages funnel through ``_emit_handoff``; other methods stay abstract
    for concrete adapters.
    """

    def notify_handoff_approved(self, handoff: LoanHandoff) -> None:
        self._emit_handoff(handoff, stage="approved")

    def notify_handoff_given(self, handoff: LoanHandoff) -> None:
        self._emit_handoff(handoff, stage="given")

    def notify_handoff_cancelled(self, handoff: LoanHandoff) -> None:
        self._emit_handoff(handoff, stage="cancelled")

    @abstractmethod
    def _emit_handoff(self, handoff: LoanHandoff, *, stage: str) -> None:
        """stage: approved | given | cancelled"""

    # Remaining IExchangeNotifier methods stay abstract (inherited).


class AbstractCopyQueue(ICopyQueue):
    """
    Shared queue skeleton.
    ``join_queue`` / ``leave_queue`` stay abstract; loan/return hooks can share
    a no-op default for adapters that only care about join/leave.
    """

    def after_copy_loaned_or_transmitted(
        self, copy_id: int, new_holder_id: int
    ) -> None:
        """Default: nothing. Override when queue must react to holder change."""

    def offer_next_after_return(
        self, copy_id: int, owner: CustomUser
    ) -> BookExchangeRequest | None:
        """Default: nobody offered. Override to create next loan request."""
        return None
