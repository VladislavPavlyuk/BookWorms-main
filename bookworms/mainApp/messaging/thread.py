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
    pending_in: list[BookExchangeRequest]
    pending_out: QuerySet[BookExchangeRequest]
    library_invites_in: list
    library_invites_out: list
    library_actions_in: list
    library_actions_out: list

    def as_web_dict(self) -> dict:
        """Template context for messages.html."""
        return {
            "partners": self.partners,
            "partner": self.partner,
            "timeline": self.timeline,
            "handoffs": self.handoffs,
            "pending_returns": self.pending_returns,
            "pending_in": self.pending_in,
            "pending_out": self.pending_out,
            "library_invites_in": self.library_invites_in,
            "library_invites_out": self.library_invites_out,
            "library_actions_in": self.library_actions_in,
            "library_actions_out": self.library_actions_out,
        }


def load_timeline(user: CustomUser, partner_id: int, *, limit: int = 250) -> list[PrivateMessage]:
    recent = (
        PrivateMessage.objects.filter(
            Q(recipient=user, sender_id=partner_id)
            | Q(sender=user, recipient_id=partner_id)
        )
        .select_related(
            "sender",
            "recipient",
            "exchange_request",
            "exchange_request__requester",
            "exchange_request__shelf_owner",
            "exchange_request__target_shelf__book",
            "library_invite",
            "library_invite__library",
            "library_invite__from_user",
            "library_invite__to_user",
            "library_action",
            "library_action__library",
            "library_action__initiator",
        )
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


def library_invites_with_partner(user: CustomUser, partner_id: int) -> tuple[list, list]:
    from ..library_service import ensure_personal_library, merge_overlap_preview
    from ..models import LibraryInvite

    pending = LibraryInvite.Status.PENDING
    awaiting = LibraryInvite.Status.AWAITING_ISBN
    incoming = list(
        LibraryInvite.objects.filter(
            status=pending, to_user=user, from_user_id=partner_id
        ).select_related("library", "from_user")
    )
    # Pending replies + admin still needs to confirm ISBN counts after invitee accepted.
    outgoing = list(
        LibraryInvite.objects.filter(
            status__in=(pending, awaiting),
            from_user=user,
            to_user_id=partner_id,
        ).select_related("library", "to_user")
    )
    in_payload = []
    for inv in incoming:
        in_payload.append(
            {
                "id": inv.id,
                "library_name": inv.library.display_name,
                "from_username": inv.from_user.username,
                "message": inv.message,
                "status": inv.status,
                "overlap": merge_overlap_preview(
                    inv.library, ensure_personal_library(user)
                ),
            }
        )
    out_payload = []
    for inv in outgoing:
        overlap = []
        if inv.status == awaiting:
            try:
                overlap = merge_overlap_preview(
                    inv.library, ensure_personal_library(inv.to_user)
                )
            except Exception:
                overlap = []
        out_payload.append(
            {
                "id": inv.id,
                "library_name": inv.library.display_name,
                "to_username": inv.to_user.username,
                "message": inv.message,
                "status": inv.status,
                "overlap": overlap,
            }
        )
    return in_payload, out_payload


def library_actions_with_partner(user: CustomUser, partner_id: int) -> tuple[list, list]:
    """Pending library actions between user and partner (admin ↔ initiator)."""
    from ..library_repo import get_library_repository
    from ..models import LibraryAction

    repo = get_library_repository()
    incoming = repo.find_pending_actions_for_admin_from(user.id, partner_id)
    outgoing = repo.find_pending_actions_by_initiator_to_admin(user.id, partner_id)

    def _row(a: LibraryAction) -> dict:
        p = a.payload or {}
        return {
            "id": a.id,
            "action_type": a.action_type,
            "action_type_label": a.get_action_type_display(),
            "title": p.get("title") or "",
            "isbn": p.get("isbn") or "",
            "existing_count": p.get("existing_count") or 0,
            "count": p.get("count") or 1,
            "initiator_username": a.initiator.username,
            "library_name": a.library.display_name,
        }

    return [_row(a) for a in incoming], [_row(a) for a in outgoing]


def build_thread_context(
    user: CustomUser,
    partner: CustomUser,
    partners: QuerySet[CustomUser],
) -> ThreadContext:
    from ..exchange.requests import offerable_shelves_from_requester

    partner_id = partner.pk
    pending_in_qs, pending_out = pending_requests_with_partner(user, partner_id)
    pending_in: list[BookExchangeRequest] = []
    for r in pending_in_qs:
        if r.offer_open and not r.offer_shelf_id:
            r.offerable_shelves = offerable_shelves_from_requester(r)
        else:
            r.offerable_shelves = []
        pending_in.append(r)
    lib_in, lib_out = library_invites_with_partner(user, partner_id)
    act_in, act_out = library_actions_with_partner(user, partner_id)
    return ThreadContext(
        user=user,
        partner=partner,
        partners=partners,
        timeline=load_timeline(user, partner_id),
        handoffs=handoffs_involving(user.id, partner_id),
        pending_returns=pending_returns_from_partner(user, partner_id),
        pending_in=pending_in,
        pending_out=pending_out,
        library_invites_in=lib_in,
        library_invites_out=lib_out,
        library_actions_in=act_in,
        library_actions_out=act_out,
    )
