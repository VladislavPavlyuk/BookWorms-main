"""
Сповіщення про запити на книги / події позики-обміну.

Фактично це непрочитані (і останні) PrivateMessage з chat-доступом:
кожен notify_* у message_service створює лист → з’являється в inbox
і веде в чат зі співрозмовником.
"""
from __future__ import annotations

from django.db.models import QuerySet

from .models import CustomUser, PrivateMessage


def unread_count(user: CustomUser) -> int:
    if not user or not user.is_authenticated:
        return 0
    return PrivateMessage.objects.filter(recipient=user, read_at__isnull=True).count()


def notifications_qs(user: CustomUser) -> QuerySet[PrivateMessage]:
    """Вхідні сповіщення: спочатку непрочитані, потім свіжіші прочитані."""
    return (
        PrivateMessage.objects.filter(recipient=user)
        .select_related("sender", "recipient", "exchange_request", "exchange_request__target_shelf__book")
        .order_by("read_at", "-created_at")  # NULL read_at first in Postgres? 
    )


def list_notifications(user: CustomUser, limit: int = 50) -> list[PrivateMessage]:
    """
    Стабільний порядок: усі непрочитані (нові зверху), потім прочитані (нові зверху).
    """
    unread = list(
        PrivateMessage.objects.filter(recipient=user, read_at__isnull=True)
        .select_related("sender", "exchange_request", "exchange_request__target_shelf__book")
        .order_by("-created_at")[:limit]
    )
    remain = max(0, limit - len(unread))
    read: list[PrivateMessage] = []
    if remain:
        read = list(
            PrivateMessage.objects.filter(recipient=user, read_at__isnull=False)
            .select_related("sender", "exchange_request", "exchange_request__target_shelf__book")
            .order_by("-created_at")[:remain]
        )
    return unread + read


def notification_payload(msg: PrivateMessage) -> dict:
    """Структура для API / шаблонів: chat_partner_id для переходу в чат."""
    kind = "message"
    if msg.exchange_request_id:
        kind = "exchange"
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
