"""
Сповіщення = вхідні PrivateMessage.

Системні (notify_*, is_system=True) не знімаються з unread при відкритті чату
(див. mark_thread_read) — лише по одному id або «прочитати все».
"""
from __future__ import annotations

from django.db.models import QuerySet

from .models import CustomUser, PrivateMessage


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
        .select_related("sender", "recipient", "exchange_request", "exchange_request__target_shelf__book")
        .order_by("read_at", "-created_at")
    )


def list_notifications(user: CustomUser, limit: int = 50) -> list[PrivateMessage]:
    """Непрочитані зверху, потім прочитані (новіші першими)."""
    base = _inbox_qs(user).select_related(
        "sender", "exchange_request", "exchange_request__target_shelf__book"
    )
    unread = list(base.filter(read_at__isnull=True).order_by("-created_at")[:limit])
    remain = max(0, limit - len(unread))
    read: list[PrivateMessage] = []
    if remain:
        read = list(base.filter(read_at__isnull=False).order_by("-created_at")[:remain])
    return unread + read


def notification_payload(msg: PrivateMessage) -> dict:
    kind = "message"
    if msg.exchange_request_id:
        kind = "exchange"
    if getattr(msg, "is_system", False):
        kind = "system" if kind == "message" else kind
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
    }
