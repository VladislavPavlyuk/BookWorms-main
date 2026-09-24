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


def notify_transmission_request_created(req: BookExchangeRequest) -> PrivateMessage:
    """Запит на позику, коли примірник уже в когось — власник може схвалити передачу третій особі."""
    req = BookExchangeRequest.objects.select_related(
        "requester",
        "shelf_owner",
        "target_shelf__book",
        "target_shelf__copy",
    ).get(pk=req.pk)
    holder = (
        Shelf.objects.filter(copy_id=req.target_shelf.copy_id, borrowed_from__isnull=False)
        .select_related("user")
        .first()
    )
    holder_name = holder.user.username if holder else "позичальника"
    body = (
        f'Запит на передачу: {req.requester.username} просить примірник "{req.target_shelf.book.title}", '
        f"який зараз у {holder_name}. "
        f"Після вашого схвалення {holder_name} і {req.requester.username} підтвердять фізичну передачу вручну; "
        f"до підтвердження отримання книга лишається у {holder_name}."
    )
    return _create_message(
        req.requester,
        req.shelf_owner,
        body,
        exchange_request=req,
        is_system=True,
    )


def notify_handoff_approved(handoff) -> None:
    """Власник схвалив — усі троє в чаті; книга ще у from_user."""
    from .models import LoanHandoff

    handoff = LoanHandoff.objects.select_related(
        "owner", "from_user", "to_user", "copy__book", "exchange_request"
    ).get(pk=handoff.pk)
    title = handoff.copy.book.title
    req = handoff.exchange_request
    to_from = (
        f'{handoff.owner.username} схвалив передачу "{title}" користувачу {handoff.to_user.username}. '
        f"Підтвердіть у чаті, коли фізично віддасте книгу. "
        f"{handoff.to_user.username} тепер у спільному чаті з вами та власником."
    )
    to_to = (
        f'{handoff.owner.username} схвалив передачу вам "{title}" (зараз у {handoff.from_user.username}). '
        f"Дочекайтесь віддачі й підтвердіть отримання в чаті — лише тоді книга з’явиться на вашій полиці. "
        f"Ви в чаті з власником і {handoff.from_user.username}."
    )
    to_owner = (
        f'Ви схвалили передачу "{title}" від {handoff.from_user.username} до {handoff.to_user.username}. '
        f"Полиця оновиться після підтвердження віддачі та отримання. "
        f"Усі троє можуть писати в чаті, доки передача не завершиться."
    )
    _create_message(
        handoff.owner, handoff.from_user, to_from, exchange_request=req, is_system=True
    )
    _create_message(
        handoff.owner, handoff.to_user, to_to, exchange_request=req, is_system=True
    )
    # Дзеркально — щоб у треді owner↔from було видно «додано to_user»
    _create_message(
        handoff.from_user,
        handoff.owner,
        to_owner,
        exchange_request=req,
        is_system=True,
    )
    # Зв’язок from↔to: системне від власника обом через прямий канал
    bridge = (
        f'Фізична передача "{title}": {handoff.from_user.username} → {handoff.to_user.username} '
        f"(схвалив {handoff.owner.username}). Узгодьте зустріч у цьому чаті."
    )
    _create_message(
        handoff.owner, handoff.to_user, bridge, exchange_request=req, is_system=True
    )
    _create_message(
        handoff.from_user,
        handoff.to_user,
        bridge,
        exchange_request=req,
        is_system=True,
    )


def notify_handoff_given(handoff) -> None:
    from .models import LoanHandoff

    handoff = LoanHandoff.objects.select_related(
        "owner", "from_user", "to_user", "copy__book", "exchange_request"
    ).get(pk=handoff.pk)
    title = handoff.copy.book.title
    req = handoff.exchange_request
    body_to = (
        f'{handoff.from_user.username} підтвердив віддачу "{title}". '
        f"Підтвердіть отримання в чаті — тоді книга з’явиться на вашій полиці, "
        f"а {handoff.from_user.username} вийде з цього чату."
    )
    body_owner = (
        f'{handoff.from_user.username} віддав "{title}" — очікуємо підтвердження від {handoff.to_user.username}.'
    )
    _create_message(
        handoff.from_user, handoff.to_user, body_to, exchange_request=req, is_system=True
    )
    _create_message(
        handoff.from_user, handoff.owner, body_owner, exchange_request=req, is_system=True
    )


def notify_handoff_cancelled(handoff) -> None:
    from .models import LoanHandoff

    handoff = LoanHandoff.objects.select_related(
        "owner", "from_user", "to_user", "copy__book", "exchange_request"
    ).get(pk=handoff.pk)
    title = handoff.copy.book.title
    req = handoff.exchange_request
    body = (
        f'{handoff.owner.username} скасував фізичну передачу "{title}" '
        f"({handoff.from_user.username} → {handoff.to_user.username}). "
        f"Книга лишається у {handoff.from_user.username}."
    )
    _create_message(
        handoff.owner, handoff.from_user, body, exchange_request=req, is_system=True
    )
    _create_message(
        handoff.owner, handoff.to_user, body, exchange_request=req, is_system=True
    )


def notify_loan_transmitted(
    owner: CustomUser,
    previous_holder: CustomUser,
    new_holder: CustomUser,
    book_title: str,
    exchange_request: BookExchangeRequest | None = None,
) -> None:
    """Після підтвердження отримання: полиця у new_holder; previous_holder виходить з чату."""
    to_prev = (
        f'{new_holder.username} підтвердив отримання "{book_title}". '
        f"Книгу знято з вашої полиці; ви більше не в чаті щодо цієї позики. "
        f"Власник {owner.username} лишається в чаті з {new_holder.username} до підтвердження повернення."
    )
    to_new = (
        f'Ви підтвердили отримання "{book_title}". Книга на вашій полиці. '
        f"{previous_holder.username} вийшов з чату. "
        f"Власник {owner.username} лишається з вами до підтвердження повернення."
    )
    to_owner = (
        f'Передачу "{book_title}" завершено: {previous_holder.username} → {new_holder.username}. '
        f"Ви в чаті з {new_holder.username} доки не підтвердите повернення."
    )
    _create_message(
        owner, previous_holder, to_prev, exchange_request=exchange_request, is_system=True
    )
    _create_message(
        owner, new_holder, to_new, exchange_request=exchange_request, is_system=True
    )
    _create_message(
        new_holder, owner, to_owner, exchange_request=exchange_request, is_system=True
    )


def notify_queue_joined(entry, position: int) -> PrivateMessage:
    from .models import CopyQueueEntry

    entry = CopyQueueEntry.objects.select_related("copy__book", "copy__owner", "user").get(pk=entry.pk)
    body = (
        f'Ви в черзі на примірник "{entry.copy.book.title}" (позиція {position}). '
        f"Отримаєте сповіщення, коли підійде ваша черга або власник схвалить передачу."
    )
    return _create_message(
        entry.copy.owner, entry.user, body, is_system=True
    )


def notify_owner_queue_joined(entry, position: int) -> PrivateMessage:
    from .models import CopyQueueEntry

    entry = CopyQueueEntry.objects.select_related("copy__book", "copy__owner", "user").get(pk=entry.pk)
    body = (
        f'{entry.user.username} став(ла) у чергу на ваш примірник "{entry.copy.book.title}" '
        f"(позиція {position})."
    )
    return _create_message(entry.user, entry.copy.owner, body, is_system=True)


def notify_queue_position(entry, position: int) -> PrivateMessage:
    from .models import CopyQueueEntry

    entry = CopyQueueEntry.objects.select_related("copy__book", "copy__owner", "user").get(pk=entry.pk)
    body = (
        f'Оновлення черги: примірник "{entry.copy.book.title}" — ваша позиція зараз {position}.'
    )
    return _create_message(entry.copy.owner, entry.user, body, is_system=True)


def notify_queue_your_turn(entry, req: BookExchangeRequest) -> PrivateMessage:
    from .models import CopyQueueEntry

    entry = CopyQueueEntry.objects.select_related("copy__book", "copy__owner", "user").get(pk=entry.pk)
    body = (
        f'Ваша черга на примірник "{entry.copy.book.title}"! '
        f"Створено запит на позику — власник {entry.copy.owner.username} може прийняти його "
        f"в чаті або в «Обміни»."
    )
    return _create_message(
        entry.copy.owner, entry.user, body, exchange_request=req, is_system=True
    )


def notify_queue_available(entry) -> PrivateMessage:
    """Примірник вільний, але автозапит не створився — м’яке сповіщення."""
    from .models import CopyQueueEntry

    entry = CopyQueueEntry.objects.select_related("copy__book", "copy__owner", "user").get(pk=entry.pk)
    body = (
        f'Примірник "{entry.copy.book.title}" знову доступний. '
        f"Надішліть запит на позику або зачекайте пропозиції від системи."
    )
    return _create_message(entry.copy.owner, entry.user, body, is_system=True)


def get_exchange_message_partners(user: CustomUser):
    """Compat shim — logic lives in ``mainApp.messaging.partners``."""
    from .messaging.partners import list_exchange_message_partners

    return list_exchange_message_partners(user)


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
