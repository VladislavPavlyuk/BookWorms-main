"""Who may chat with whom (active exchange / loan / handoff / queue)."""
from __future__ import annotations

from django.db.models import Q, QuerySet

from ..models import BookExchangeRequest, CustomUser, Shelf


def list_exchange_message_partners(user: CustomUser) -> QuerySet[CustomUser]:
    """
    Співрозмовники за *активним* контекстом:
    - pending запити на обмін/позику;
    - активна позика (Shelf.borrowed_from);
    - активна фізична передача (LoanHandoff) — власник + обидва позичальники;
    - черга на примірник.

    Після завершення handoff попередній позичальник відпадає; власник лишається
    з новим доки не підтвердить повернення.
    """
    from ..models import CopyQueueEntry, LoanHandoff

    ids: set[int] = set()
    pending = BookExchangeRequest.Status.PENDING
    for er in BookExchangeRequest.objects.filter(status=pending).filter(
        Q(requester=user) | Q(shelf_owner=user)
    ).only("requester_id", "shelf_owner_id"):
        ids.add(er.requester_id)
        ids.add(er.shelf_owner_id)

    for s in Shelf.objects.filter(borrowed_from=user).only("user_id"):
        ids.add(s.user_id)
    for s in Shelf.objects.filter(user=user, borrowed_from__isnull=False).only(
        "borrowed_from_id"
    ):
        ids.add(s.borrowed_from_id)

    active_h = (
        LoanHandoff.Status.AWAITING_GIVE,
        LoanHandoff.Status.AWAITING_RECEIVE,
    )
    try:
        for h in LoanHandoff.objects.filter(status__in=active_h).filter(
            Q(owner=user) | Q(from_user=user) | Q(to_user=user)
        ).only("owner_id", "from_user_id", "to_user_id"):
            ids.add(h.owner_id)
            ids.add(h.from_user_id)
            ids.add(h.to_user_id)
    except Exception:
        pass

    for e in CopyQueueEntry.objects.filter(
        status__in=("waiting", "offered"),
        copy__owner=user,
    ).only("user_id"):
        ids.add(e.user_id)
    for e in CopyQueueEntry.objects.filter(
        status__in=("waiting", "offered"),
        user=user,
    ).select_related("copy").only("copy__owner_id"):
        ids.add(e.copy.owner_id)

    ids.discard(user.pk)
    return CustomUser.objects.filter(pk__in=ids).order_by("username").distinct()
