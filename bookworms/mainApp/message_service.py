"""
Сервіс приватних повідомлень між користувачами.

Викликається з exchange_service після подій запиту на позику/обмін:
створення запиту, прийняття, відхилення, скасування - щоб сторони бачили це в "Повідомленнях".
"""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from .models import BookExchangeRequest, CustomUser, PrivateMessage, Shelf


def _create_message(
    sender: CustomUser,
    recipient: CustomUser,
    body: str,
    exchange_request: BookExchangeRequest | None = None,
    *,
    is_system: bool = False,
    related_shelf: Shelf | None = None,
) -> PrivateMessage:
    return PrivateMessage.objects.create(
        sender=sender,
        recipient=recipient,
        body=body,
        exchange_request=exchange_request,
        is_system=is_system,
        related_shelf=related_shelf,
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
    return _create_message(sender, recipient, body, exchange_request=exchange_request, is_system=False)


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
            f'Запит на обмін: {req.requester.username} пропонує "{offer_title}" '
            f'замість вашої "{book_title}". '
            f"Відкрийте чат або розділ «Обміни», щоб відповісти."
        )
    else:
        body = (
            f'Запит на позику: {req.requester.username} просить книгу "{book_title}". '
            f"Відкрийте чат або «Обміни», щоб прийняти чи відхилити."
        )
    return _create_message(
        req.requester,
        req.shelf_owner,
        body,
        exchange_request=req,
        is_system=True,
    )


def notify_exchange_request_accepted(req: BookExchangeRequest) -> PrivateMessage:
    """Власник прийняв запит - повідомляємо запитувача."""
    req = BookExchangeRequest.objects.select_related(
        "requester", "shelf_owner", "target_shelf__book", "offer_shelf__book"
    ).get(pk=req.pk)
    book_title = req.target_shelf.book.title
    if req.offer_shelf_id:
        body = (
            f'Ваш запит на обмін прийнято ({req.shelf_owner.username}). '
            f'Книга "{book_title}" тепер у вас. Можете написати в чат.'
        )
    else:
        body = (
            f'Ваш запит на позику прийнято ({req.shelf_owner.username}). '
            f'Книга "{book_title}" на вашій полиці. Можете написати в чат.'
        )
    return _create_message(
        req.shelf_owner, req.requester, body, exchange_request=req, is_system=True
    )


def notify_exchange_request_rejected(req: BookExchangeRequest) -> PrivateMessage:
    """Власник відхилив - повідомляємо запитувача."""
    req = BookExchangeRequest.objects.select_related("requester", "shelf_owner", "target_shelf__book").get(
        pk=req.pk
    )
    body = f'Запит щодо книги "{req.target_shelf.book.title}" відхилено.'
    return _create_message(
        req.shelf_owner, req.requester, body, exchange_request=req, is_system=True
    )


def notify_borrow_return_requested(shelf: Shelf) -> PrivateMessage:
    """Позичальник натиснув повернути - позикодавець отримує лист."""
    lender = shelf.borrowed_from
    if lender is None:
        raise ValueError("notify_borrow_return_requested: очікується позичена книга (borrowed_from).")
    body = (
        f'{shelf.user.username} ініціював повернення книги "{shelf.book.title}". '
        f'Натисніть «Підтвердити», коли фізично отримаєте книгу.'
    )
    return _create_message(
        shelf.user, lender, body, is_system=True, related_shelf=shelf
    )


def notify_borrow_return_confirmed(
    lender: CustomUser, borrower: CustomUser, book_title: str
) -> PrivateMessage:
    """Після підтвердження позикодавцем - повідомлення позичальнику."""
    body = (
        f'{lender.username} підтвердив отримання книги "{book_title}". '
        f'Вона знята з вашої полиці.'
    )
    return _create_message(lender, borrower, body, is_system=True)


def notify_exchange_request_cancelled(req: BookExchangeRequest) -> PrivateMessage:
    """Запитувач скасував - повідомляємо власника."""
    req = BookExchangeRequest.objects.select_related("requester", "shelf_owner", "target_shelf__book").get(
        pk=req.pk
    )
    body = (
        f"Користувач {req.requester.username} скасував запит щодо вашої книги "
        f'"{req.target_shelf.book.title}".'
    )
    return _create_message(
        req.requester, req.shelf_owner, body, exchange_request=req, is_system=True
    )


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


def mark_return_notifications_read(lender: CustomUser, *, shelf_id: int, borrower_id: int, book_title: str) -> int:
    """
    Після «Підтвердити повернення» — відповідні сповіщення у власника стають прочитаними.
    """
    now = timezone.now()
    legacy = (
        Q(sender_id=borrower_id)
        & Q(is_system=True)
        & Q(body__icontains="ініціював повернення")
        & Q(body__icontains=book_title)
    )
    qs = PrivateMessage.objects.filter(recipient=lender, read_at__isnull=True).filter(
        Q(related_shelf_id=shelf_id) | legacy
    )
    return qs.update(read_at=now)


def mark_thread_read(user: CustomUser, partner_id: int) -> int:
    """
    Прочитані лише звичайні листи в діалозі (не системні сповіщення).
    Інакше відкриття чату по одному notify з’їдає всі інші unread від того ж юзера.
    """
    now = timezone.now()
    return PrivateMessage.objects.filter(
        recipient=user,
        sender_id=partner_id,
        read_at__isnull=True,
        is_system=False,
    ).update(read_at=now)
