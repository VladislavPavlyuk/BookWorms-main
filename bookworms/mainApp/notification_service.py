"""
Сповіщення = вхідні PrivateMessage.

Системні (notify_*, is_system=True) не знімаються з unread при відкритті чату
(див. mark_thread_read) — лише по одному id або «прочитати все».
"""
from __future__ import annotations

from django.db.models import QuerySet

from .models import CustomUser, PrivateMessage, Shelf


def _inbox_qs(user: CustomUser) -> QuerySet[PrivateMessage]:
    # Не фільтруємо строго по is_system: інакше після міграції/бекфілу
    # бейдж і список стають порожніми, хоча листи в БД є.
    return PrivateMessage.objects.filter(recipient=user)


def unread_count(user: CustomUser) -> int:
    if not user or not user.is_authenticated:
        return 0
    return _inbox_qs(user).filter(read_at__isnull=True).count()


def notifications_qs(user: CustomUser) -> QuerySet[PrivateMessage]:
    return (
        _inbox_qs(user)
        .select_related(
            "sender",
            "recipient",
            "exchange_request",
            "exchange_request__target_shelf__book",
            "related_shelf",
            "related_shelf__book",
        )
        .order_by("read_at", "-created_at")
    )


def list_notifications(user: CustomUser, limit: int = 50) -> list[PrivateMessage]:
    """Непрочитані зверху, потім прочитані (новіші першими)."""
    base = _inbox_qs(user).select_related(
        "sender",
        "exchange_request",
        "exchange_request__target_shelf__book",
        "related_shelf",
        "related_shelf__book",
    )
    unread = list(base.filter(read_at__isnull=True).order_by("-created_at")[:limit])
    remain = max(0, limit - len(unread))
    read: list[PrivateMessage] = []
    if remain:
        read = list(base.filter(read_at__isnull=False).order_by("-created_at")[:remain])
    return unread + read


def _is_return_request_notification(msg: PrivateMessage) -> bool:
    """Лише сповіщення «позичальник ініціював повернення» (не обмін/чат/інше)."""
    if getattr(msg, "related_shelf_id", None):
        return True
    body = (msg.body or "").lower()
    return "ініціював повернення" in body or "инициировал возврат" in body


def _resolve_confirm_return_shelf_id(msg: PrivateMessage) -> int | None:
    """
    Id рядка позичальника для кнопки «Підтвердити».
    Тільки для сповіщень про повернення цієї конкретної книги — не для всіх листів від юзера.
    """
    if not _is_return_request_notification(msg):
        return None

    shelf = getattr(msg, "related_shelf", None)
    if (
        shelf is not None
        and shelf.return_pending
        and shelf.borrowed_from_id == msg.recipient_id
        and shelf.user_id == msg.sender_id
    ):
        return shelf.pk

    # Старі листи без related_shelf: шукаємо pending лише якщо текст про повернення,
    # і по можливості співставляємо з назвою книги в body.
    loans = list(
        Shelf.objects.filter(
            user_id=msg.sender_id,
            borrowed_from_id=msg.recipient_id,
            return_pending=True,
        )
        .select_related("book")
        .order_by("-added_at")
    )
    if not loans:
        return None
    body = msg.body or ""
    for loan in loans:
        title = loan.book.title if loan.book_id else ""
        if title and title in body:
            return loan.pk
    # Один pending від цього позичальника — однозначно ця книга
    if len(loans) == 1:
        return loans[0].pk
    return None


def notification_payload(msg: PrivateMessage) -> dict:
    kind = "message"
    if msg.exchange_request_id:
        kind = "exchange"
    is_return = _is_return_request_notification(msg)
    confirm_id = _resolve_confirm_return_shelf_id(msg) if is_return else None
    if is_return:
        kind = "return"
    elif getattr(msg, "is_system", False) and kind == "message":
        kind = "system"
    return {
        "id": msg.id,
        "kind": kind,
        "body": msg.body,
        "created_at": msg.created_at,
        "read_at": msg.read_at,
        "is_unread": msg.read_at is None,
        "chat_partner_id": msg.sender_id,
        "chat_partner_username": msg.sender.username,
        "exchange_request_id": msg.exchange_request_id,
        # Кнопка лише коли є активне повернення саме цього сповіщення
        "confirm_return_shelf_id": confirm_id,
    }
