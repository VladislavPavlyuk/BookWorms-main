"""Thread context: timeline + handoff / return / pending-request panels."""
from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Q, QuerySet

from ..exchange.handoff import handoffs_involving
from ..models import (
    BookExchangeRequest,
    CustomUser,
    LoanHandoff,
    PrivateMessage,
    Shelf,
)

_PENDING_REQ_SELECT = (
    "requester",
    "shelf_owner",
    "target_shelf__book",
    "target_shelf__user",
    "target_shelf__copy",
    "offer_shelf__book",
    "offer_shelf__user",
    "target_shelf__borrowed_from",
    "offer_shelf__borrowed_from",
)


@dataclass
class ThreadContext:
    user: CustomUser
    partner: CustomUser
    partners: QuerySet[CustomUser]
    timeline: list[PrivateMessage]
    handoffs: list[LoanHandoff]
    pending_returns: list[Shelf]
    pending_in: QuerySet[BookExchangeRequest]
    pending_out: QuerySet[BookExchangeRequest]

    def as_web_dict(self) -> dict:
        """Template context for messages.html (no pending_in/out forms there yet)."""
        return {
            "partners": self.partners,
            "partner": self.partner,
            "timeline": self.timeline,
            "handoffs": self.handoffs,
            "pending_returns": self.pending_returns,
        }


def load_timeline(user: CustomUser, partner_id: int, *, limit: int = 250) -> list[PrivateMessage]:
    recent = (
        PrivateMessage.objects.filter(
            Q(recipient=user, sender_id=partner_id)
            | Q(sender=user, recipient_id=partner_id)
        )
        .select_related("sender", "recipient", "exchange_request")
        .order_by("-created_at")[:limit]
    )
    return list(reversed(list(recent)))


def pending_returns_from_partner(owner: CustomUser, partner_id: int) -> list[Shelf]:
    return list(
        Shelf.objects.filter(
            borrowed_from=owner,
            user_id=partner_id,
            return_pending=True,
        )
        .select_related("user", "book", "borrowed_from", "copy")
        .order_by("-added_at")
    )


def pending_requests_with_partner(
    user: CustomUser, partner_id: int
) -> tuple[QuerySet[BookExchangeRequest], QuerySet[BookExchangeRequest]]:
    pending = BookExchangeRequest.Status.PENDING
    pending_in = BookExchangeRequest.objects.filter(
        status=pending,
        shelf_owner=user,
        requester_id=partner_id,
    ).select_related(*_PENDING_REQ_SELECT)
    pending_out = BookExchangeRequest.objects.filter(
        status=pending,
        requester=user,
        shelf_owner_id=partner_id,
    ).select_related(*_PENDING_REQ_SELECT)
    return pending_in, pending_out


def build_thread_context(
    user: CustomUser,
    partner: CustomUser,
    partners: QuerySet[CustomUser],
) -> ThreadContext:
    partner_id = partner.pk
    pending_in, pending_out = pending_requests_with_partner(user, partner_id)
    return ThreadContext(
        user=user,
        partner=partner,
        partners=partners,
        timeline=load_timeline(user, partner_id),
        handoffs=handoffs_involving(user.id, partner_id),
        pending_returns=pending_returns_from_partner(user, partner_id),
        pending_in=pending_in,
        pending_out=pending_out,
    )
