"""
Сервіс приватних повідомлень між користувачами.

Викликається з exchange_service після подій запиту на позику/обмін:
створення запиту, прийняття, відхилення, скасування - щоб сторони бачили це в "Повідомленнях".
"""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from .models import BookExchangeRequest, CustomUser, PrivateMessage


def _create_message(
    sender: CustomUser,
    recipient: CustomUser,
    body: str,
    exchange_request: BookExchangeRequest | None = None,
) -> PrivateMessage:
    return PrivateMessage.objects.create(
        sender=sender,
        recipient=recipient,
        body=body,
        exchange_request=exchange_request,
    )


def send_user_message(
    sender: CustomUser,
    recipient: CustomUser,
    body: str,
    exchange_request: BookExchangeRequest | None = None,
) -> PrivateMessage | None:
    """Ручне повідомлення (наприклад з форми "Написати"). Порожній текст або сам собі - ігнор."""
    body = (body or "").strip()
    if not body or sender.pk == recipient.pk:
        return None
    return _create_message(sender, recipient, body, exchange_request=exchange_request)


def notify_exchange_request_created(req: BookExchangeRequest) -> PrivateMessage:
    """
    Після успішного create_exchange_request: власник книги отримує сповіщення від запитувача.
    """
    req = BookExchangeRequest.objects.select_related(
        "requester",
        "shelf_owner",
        "target_shelf__book",
        "offer_shelf__book",
    ).get(pk=req.pk)
    book_title = req.target_shelf.book.title
    if req.offer_shelf_id:
        offer_title = req.offer_shelf.book.title
        body = (
            f'Запит на обмін: я пропоную вам "{offer_title}" замість вашої "{book_title}". '
            f'Перегляньте запити в розділі "Обміни".'
        )
    else:
        body = (
            f'Запит на позику книги "{book_title}". '
            f"Якщо погодитесь, після прийняття я зможу тримати її на полиці та повернути вам. "
            f'Деталі - у розділі "Обміни".'
        )
    return _create_message(
        req.requester,
        req.shelf_owner,
        body,
        exchange_request=req,
    )


def notify_exchange_request_accepted(req: BookExchangeRequest) -> PrivateMessage:
    """Власник прийняв запит - повідомляємо запитувача."""
    req = BookExchangeRequest.objects.select_related(
        "requester", "shelf_owner", "target_shelf__book", "offer_shelf__book"
    ).get(pk=req.pk)
    book_title = req.target_shelf.book.title
    if req.offer_shelf_id:
        body = (
            f'Ваш запит на обмін прийнято. Книга "{book_title}" тепер у вас на полиці, '
            f'а "{req.offer_shelf.book.title}" - у власника.'
        )
    else:
        body = (
            f'Ваш запит на позику прийнято. Книга "{book_title}" на вашій полиці як позичена; '
            f'повернути її можна лише власнику через "Повернути власнику".'
        )
    return _create_message(req.shelf_owner, req.requester, body, exchange_request=req)


def notify_exchange_request_rejected(req: BookExchangeRequest) -> PrivateMessage:
    """Власник відхилив - повідомляємо запитувача."""
    req = BookExchangeRequest.objects.select_related("requester", "shelf_owner", "target_shelf__book").get(
        pk=req.pk
    )
    body = f'Запит щодо книги "{req.target_shelf.book.title}" відхилено.'
    return _create_message(req.shelf_owner, req.requester, body, exchange_request=req)


def notify_exchange_request_cancelled(req: BookExchangeRequest) -> PrivateMessage:
    """Запитувач скасував - повідомляємо власника."""
    req = BookExchangeRequest.objects.select_related("requester", "shelf_owner", "target_shelf__book").get(
        pk=req.pk
    )
    body = (
        f"Користувач {req.requester.username} скасував запит щодо вашої книги "
        f'"{req.target_shelf.book.title}".'
    )
    return _create_message(req.requester, req.shelf_owner, body, exchange_request=req)


def get_exchange_message_partners(user: CustomUser):
    """
    Співрозмовники лише з пар BookExchangeRequest (позика або обмін).
    Без спільного запиту доступу до чату немає.
    """
    ids: set[int] = set()
    for er in BookExchangeRequest.objects.filter(
        Q(requester=user) | Q(shelf_owner=user)
    ).only("requester_id", "shelf_owner_id"):
        ids.add(er.requester_id)
        ids.add(er.shelf_owner_id)
    ids.discard(user.pk)
    return CustomUser.objects.filter(pk__in=ids).order_by("username").distinct()


def mark_messages_read_for_user(user: CustomUser, message_ids: list[int] | None = None) -> int:
    """Позначає вхідні як прочитані (для скриньки). Повертає кількість оновлених."""
    qs = PrivateMessage.objects.filter(recipient=user, read_at__isnull=True)
    if message_ids is not None:
        qs = qs.filter(pk__in=message_ids)
    now = timezone.now()
    return qs.update(read_at=now)


def mark_thread_read(user: CustomUser, partner_id: int) -> int:
    """Прочитані лише листи в цьому діалозі (від partner до user)."""
    now = timezone.now()
    return PrivateMessage.objects.filter(
        recipient=user,
        sender_id=partner_id,
        read_at__isnull=True,
    ).update(read_at=now)
