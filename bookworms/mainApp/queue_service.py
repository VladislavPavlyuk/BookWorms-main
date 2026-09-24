"""
Черга інтересу до примірника (BookCopy).

FIFO: хто раніше — той вище. Після повернення наступний отримує
автозапит на позику + сповіщення. При передачі третій особі
(accept під час активної позики) позиція оновлюється у всіх.
"""
from __future__ import annotations

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from . import message_service
from .models import BookCopy, BookExchangeRequest, CopyQueueEntry, CustomUser, Shelf


ACTIVE = (CopyQueueEntry.Status.WAITING, CopyQueueEntry.Status.OFFERED)


def active_queue_qs(copy_id: int) -> QuerySet[CopyQueueEntry]:
    return (
        CopyQueueEntry.objects.filter(copy_id=copy_id, status__in=ACTIVE)
        .select_related("user", "copy", "copy__book", "copy__owner")
        .order_by("created_at")
    )


def queue_position(entry: CopyQueueEntry) -> int:
    """1-based position among active entries."""
    return (
        active_queue_qs(entry.copy_id)
        .filter(created_at__lte=entry.created_at)
        .count()
    )


def serialize_queue(copy_id: int) -> list[dict]:
    out = []
    for i, e in enumerate(active_queue_qs(copy_id), start=1):
        out.append(
            {
                "id": e.pk,
                "user_id": e.user_id,
                "username": e.user.username,
                "status": e.status,
                "position": i,
                "exchange_request_id": e.exchange_request_id,
                "created_at": e.created_at,
            }
        )
    return out


@transaction.atomic
def join_queue(
    user: CustomUser,
    copy: BookCopy,
    *,
    notify: bool = True,
    exchange_request: BookExchangeRequest | None = None,
) -> tuple[CopyQueueEntry | None, str | None]:
    """Стати в чергу на примірник. Власник / поточний тримач — ні."""
    if copy.owner_id == user.id:
        return None, "Власник не стає в чергу на свій примірник."

    if Shelf.objects.filter(user=user, copy_id=copy.pk).exists():
        return None, "Цей примірник уже на вашій полиці."

    existing = (
        CopyQueueEntry.objects.select_for_update()
        .filter(copy_id=copy.pk, user=user, status__in=ACTIVE)
        .first()
    )
    if existing:
        return existing, None

    entry = CopyQueueEntry.objects.create(
        copy=copy,
        user=user,
        status=CopyQueueEntry.Status.WAITING,
        exchange_request=exchange_request,
    )
    if notify:
        pos = queue_position(entry)
        message_service.notify_queue_joined(entry, pos)
        _notify_owner_queue_interest(entry, pos)
    return entry, None


def leave_queue(user: CustomUser, copy_id: int) -> tuple[bool, str | None]:
    entry = (
        CopyQueueEntry.objects.filter(copy_id=copy_id, user=user, status__in=ACTIVE)
        .first()
    )
    if not entry:
        return False, "Ви не в черзі на цей примірник."
    _cancel_entry(entry)
    _renumber_notify(copy_id)
    return True, None


def fulfill_queue_user(copy_id: int, user_id: int) -> None:
    """Позначити запис користувача як виконаний після позики/передачі."""
    now = timezone.now()
    CopyQueueEntry.objects.filter(
        copy_id=copy_id, user_id=user_id, status__in=ACTIVE
    ).update(status=CopyQueueEntry.Status.FULFILLED, resolved_at=now)


def _cancel_entry(entry: CopyQueueEntry) -> None:
    entry.status = CopyQueueEntry.Status.CANCELLED
    entry.resolved_at = timezone.now()
    entry.save(update_fields=["status", "resolved_at"])


def _renumber_notify(copy_id: int) -> None:
    for i, e in enumerate(active_queue_qs(copy_id), start=1):
        message_service.notify_queue_position(e, i)


def _notify_owner_queue_interest(entry: CopyQueueEntry, position: int) -> None:
    message_service.notify_owner_queue_joined(entry, position)


@transaction.atomic
def after_copy_loaned_or_transmitted(copy_id: int, new_holder_id: int) -> None:
    """
    Після успішної позики / передачі третій особі:
    - виконати запис нового тримача в черзі;
    - решті активних — оновити позиції сповіщеннями.
    """
    fulfill_queue_user(copy_id, new_holder_id)
    _renumber_notify(copy_id)


@transaction.atomic
def offer_next_after_return(copy_id: int, owner: CustomUser) -> BookExchangeRequest | None:
    """
    Після підтвердження повернення: першому в черзі створити запит на позику
    і надіслати «ваша черга».
    """
    from .exchange_service import create_exchange_request
    from .exceptions import ExchangeError

    entry = (
        CopyQueueEntry.objects.select_for_update()
        .filter(copy_id=copy_id, status=CopyQueueEntry.Status.WAITING)
        .order_by("created_at")
        .first()
    )
    if not entry:
        return None

    owner_shelf = (
        Shelf.objects.filter(
            user=owner,
            copy_id=copy_id,
            borrowed_from__isnull=True,
        )
        .select_related("book", "copy")
        .first()
    )
    if not owner_shelf:
        return None

    existing = BookExchangeRequest.objects.filter(
        requester=entry.user,
        target_shelf=owner_shelf,
        status=BookExchangeRequest.Status.PENDING,
    ).first()
    if existing:
        req = existing
    else:
        try:
            req = create_exchange_request(
                entry.user,
                owner_shelf,
                None,
                from_queue=True,
                join_queue_if_busy=False,
            )
        except ExchangeError:
            message_service.notify_queue_available(entry)
            return None

    entry.status = CopyQueueEntry.Status.OFFERED
    entry.exchange_request = req
    entry.resolved_at = None
    entry.save(update_fields=["status", "exchange_request", "resolved_at"])
    message_service.notify_queue_your_turn(entry, req)
    return req
