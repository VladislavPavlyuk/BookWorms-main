"""
Сервіс обміну та позик книг (чиста логіка без HTTP).

Навіщо окремий файл: щоб правила "хто кому що може" були в одному місці,
а views лише викликали ці функції й показували повідомлення користувачу.
"""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef, QuerySet
from django.utils import timezone

from . import message_service
from .models import Book, BookCopy, BookExchangeRequest, CustomUser, Shelf


def _loan_due_date():
    days = int(getattr(settings, "DEFAULT_LOAN_DAYS", 14))
    return timezone.now().date() + timedelta(days=days)


def add_owned_copy(user: CustomUser, book: Book) -> Shelf:
    """
    Новий фізичний примірник на полиці власника.
    Той самий ISBN можна додавати багато разів (окремі BookCopy).
    """
    copy = BookCopy.objects.create(book=book, owner=user)
    return Shelf.objects.create(user=user, book=book, copy=copy)


def remove_owned_shelf(shelf: Shelf) -> None:
    """Прибрати власний рядок; якщо примірник більше ніде не лежить — видалити BookCopy."""
    copy = shelf.copy
    shelf.delete()
    if copy is not None and not Shelf.objects.filter(copy_id=copy.pk).exists():
        BookCopy.objects.filter(pk=copy.pk).delete()


def ensure_shelf_copy(shelf: Shelf) -> Shelf:
    """Якщо рядок полиці без BookCopy (старі дані) — створити примірник і прив’язати."""
    if shelf.copy_id:
        return shelf
    owner_id = shelf.borrowed_from_id or shelf.user_id
    copy = BookCopy.objects.create(book_id=shelf.book_id, owner_id=owner_id)
    Shelf.objects.filter(pk=shelf.pk).update(copy_id=copy.pk)
    shelf.copy_id = copy.pk
    shelf.copy = copy
    return shelf


def ensure_shelves_have_copies(shelves: list[Shelf]) -> list[Shelf]:
    return [ensure_shelf_copy(s) for s in shelves]


def is_copy_lent_out(copy_id: int | None) -> bool:
    """Чи є активна позика цього примірника."""
    if not copy_id:
        return False
    return Shelf.objects.filter(
        copy_id=copy_id,
        borrowed_from__isnull=False,
    ).exists()


def is_book_lent_out(owner_id: int, book_id: int) -> bool:
    """
    Legacy: чи є активна позика будь-якого примірника цієї ISBN від власника.
    Для UI «книга у від'їзді» на рівні ISBN; для блокування дій — краще is_copy_lent_out.
    """
    return Shelf.objects.filter(
        borrowed_from_id=owner_id,
        book_id=book_id,
    ).exists()


def available_owned_shelves_qs(exclude_user_id: int | None = None) -> QuerySet[Shelf]:
    """
    Полиці, доступні для запиту: власні (не borrowed), і цей примірник зараз не в позиці.
    """
    active_loan = Shelf.objects.filter(
        copy_id=OuterRef("copy_id"),
        borrowed_from__isnull=False,
    ).exclude(copy_id__isnull=True)
    qs = Shelf.objects.filter(borrowed_from__isnull=True).exclude(Exists(active_loan))
    if exclude_user_id is not None:
        qs = qs.exclude(user_id=exclude_user_id)
    return qs


def group_shelves_by_book(shelves) -> list[dict]:
    """
    Один ISBN → одна картка: book + унікальні owners + усі доступні shelf-рядки (примірники).
    Порядок = перша поява книги в queryset.
    """
    groups: dict[int, dict] = {}
    order: list[int] = []
    for s in shelves:
        bid = s.book_id
        if bid not in groups:
            groups[bid] = {
                "book": s.book,
                "shelves": [],
                "owners": [],
                "_owner_ids": set(),
            }
            order.append(bid)
        g = groups[bid]
        g["shelves"].append(s)
        if s.user_id not in g["_owner_ids"]:
            g["_owner_ids"].add(s.user_id)
            g["owners"].append(s.user)
    out = []
    for bid in order:
        g = groups[bid]
        out.append(
            {
                "book": g["book"],
                "shelves": g["shelves"],
                "owners": g["owners"],
            }
        )
    return out


def get_or_create_book_from_payload(payload: dict) -> tuple[Book, bool]:
    """
    Створює запис Book у БД з відповіді Open Library (або повертає вже існуючий за ISBN).
    Друге значення в кортежі - чи саме зараз створили новий рядок (для дебагу/логів).
    """
    book, created = Book.objects.get_or_create(
        isbn=payload["isbn"],
        defaults={
            "title": payload["title"],
            "authors": payload["authors"],
            "publisher": payload["publisher"],
            "publish_date": payload["publish_date"],
            "cover_url": payload["cover_url"],
            "info_url": payload["info_url"],
        },
    )
    return book, created


def create_exchange_request(
    requester: CustomUser,
    target_shelf: Shelf,
    offer_shelf: Shelf | None = None,
) -> tuple[BookExchangeRequest | None, str | None]:
    """
    Створює запит. Помилка - (None, текст).
    Без offer_shelf: після прийняття - позика (borrowed_from = власник).
    З offer_shelf: обмін двома примірниками (повна передача, без позики).
    """
    if target_shelf.user_id == requester.id:
        return None, "Не можна запитувати власну книгу."

    if target_shelf.borrowed_from_id:
        return None, "Неможливо запитувати позичену в іншого користувача книгу."

    if is_copy_lent_out(target_shelf.copy_id):
        return None, "Цей примірник зараз у когось у позиці - запит недоступний."

    if offer_shelf is not None:
        if offer_shelf.user_id != requester.id:
            return None, "Запропонована книга має бути з вашої полиці."
        if offer_shelf.borrowed_from_id:
            return None, "Неможна віддавати в обмін позичену книгу - спочатку поверніть її власнику."
        if is_copy_lent_out(offer_shelf.copy_id):
            return None, "Неможна віддавати в обмін книгу, яка зараз у когось у позиці."
        if offer_shelf.copy_id == target_shelf.copy_id:
            return None, "Немає сенсу обмінювати той самий примірник."

    pending = BookExchangeRequest.Status.PENDING
    if BookExchangeRequest.objects.filter(
        target_shelf=target_shelf,
        requester=requester,
        status=pending,
    ).exists():
        return None, "Ви вже маєте активний запит щодо цієї книги."

    # Той самий примірник уже на полиці (не блокуємо інший ISBN-клон).
    if Shelf.objects.filter(user=requester, copy_id=target_shelf.copy_id).exists():
        return None, "Цей примірник вже є у вас на полиці."

    req = BookExchangeRequest.objects.create(
        target_shelf=target_shelf,
        shelf_owner=target_shelf.user,
        requester=requester,
        offer_shelf=offer_shelf,
        status=pending,
    )
    message_service.notify_exchange_request_created(req)
    return req, None


def create_many_exchange_requests(
    requester: CustomUser,
    lines: list[tuple[Shelf, Shelf | None]],
) -> tuple[int, list[str]]:
    """
    Кілька запитів за одну дію (позика або обмін на рядок).
    Та сама пропозиція (offer_shelf) не може зустрічатись двічі в одному пакеті.
    """
    ok = 0
    errs: list[str] = []

    def short_title(s: Shelf) -> str:
        t = s.book.title
        return (t[:52] + "…") if len(t) > 55 else t

    seen_offer_ids: set[int] = set()
    filtered: list[tuple[Shelf, Shelf | None]] = []
    for target_shelf, offer_shelf in lines:
        label = short_title(target_shelf)
        if offer_shelf is not None:
            oid = offer_shelf.pk
            if oid in seen_offer_ids:
                errs.append(f'"{label}": цю свою книгу вже обрано для іншого рядка в цьому пакеті.')
                continue
            seen_offer_ids.add(oid)
        filtered.append((target_shelf, offer_shelf))

    for target_shelf, offer_shelf in filtered:
        label = short_title(target_shelf)
        req, err = create_exchange_request(requester, target_shelf, offer_shelf)
        if err:
            errs.append(f"'{label}': {err}")
        else:
            ok += 1
    return ok, errs


@transaction.atomic
def accept_exchange_request(request_id: int, acting_user: CustomUser) -> tuple[bool, str | None]:
    """
    Власник погоджується.
    Позика: власник ЗБЕРІГАЄ свій рядок Shelf; позичальнику створюється окремий рядок
    з borrowed_from на той самий BookCopy.
    Обмін: обидва рядки міняють user_id і owner на BookCopy (повна передача).
    """
    try:
        req = BookExchangeRequest.objects.select_for_update().get(
            pk=request_id,
            status=BookExchangeRequest.Status.PENDING,
        )
    except BookExchangeRequest.DoesNotExist:
        return False, "Запит не знайдено або вже оброблено."

    if req.shelf_owner_id != acting_user.id:
        return False, "Ви не власник цієї книги."

    target = (
        Shelf.objects.select_for_update(of=("self",))
        .filter(
            pk=req.target_shelf_id,
            user_id=req.shelf_owner_id,
        )
        .select_related("book", "copy")
        .first()
    )
    if not target:
        return False, "Книги вже немає на вашій полиці."
    if target.borrowed_from_id:
        return False, "Не можна віддати позичену книгу."
    if is_copy_lent_out(target.copy_id):
        return False, "Примірник вже виданий в позику."

    requester = CustomUser.objects.select_for_update().get(pk=req.requester_id)

    offer = None
    if req.offer_shelf_id:
        offer = (
            Shelf.objects.select_for_update(of=("self",))
            .filter(pk=req.offer_shelf_id, user=requester)
            .select_related("book", "copy")
            .first()
        )
        if not offer:
            return False, "Запропонована книга більше не на полиці відправника."
        if offer.borrowed_from_id or is_copy_lent_out(offer.copy_id):
            return False, "Запропонована книга недоступна для обміну (позика)."

    if Shelf.objects.filter(user=requester, copy_id=target.copy_id).exists():
        return False, "У користувача вже є цей примірник - неможливо завершити обмін."

    if offer:
        if (
            Shelf.objects.filter(user=acting_user, copy_id=offer.copy_id)
            .exclude(pk=offer.pk)
            .exists()
        ):
            return False, "У вас уже є запропонований до обміну примірник."
        Shelf.objects.filter(pk=target.pk).update(
            user_id=requester.id,
            borrowed_from_id=None,
            due_date=None,
            return_pending=False,
        )
        Shelf.objects.filter(pk=offer.pk).update(
            user_id=acting_user.id,
            borrowed_from_id=None,
            due_date=None,
            return_pending=False,
        )
        BookCopy.objects.filter(pk=target.copy_id).update(owner_id=requester.id)
        BookCopy.objects.filter(pk=offer.copy_id).update(owner_id=acting_user.id)
    else:
        Shelf.objects.create(
            user_id=requester.id,
            book_id=target.book_id,
            copy_id=target.copy_id,
            borrowed_from_id=acting_user.id,
            due_date=_loan_due_date(),
            return_pending=False,
        )

    req.status = BookExchangeRequest.Status.ACCEPTED
    req.resolved_at = timezone.now()
    req.save(update_fields=["status", "resolved_at"])
    message_service.notify_exchange_request_accepted(req)
    return True, None


def reject_exchange_request(request_id: int, acting_user: CustomUser) -> tuple[bool, str | None]:
    try:
        req = BookExchangeRequest.objects.get(
            pk=request_id,
            status=BookExchangeRequest.Status.PENDING,
        )
    except BookExchangeRequest.DoesNotExist:
        return False, "Запит не знайдено."

    if req.shelf_owner_id != acting_user.id:
        return False, "Ви не власник цієї книги."

    req.status = BookExchangeRequest.Status.REJECTED
    req.resolved_at = timezone.now()
    req.save(update_fields=["status", "resolved_at"])
    message_service.notify_exchange_request_rejected(req)
    return True, None


def cancel_exchange_request(request_id: int, acting_user: CustomUser) -> tuple[bool, str | None]:
    """Той, хто надсилав запит, передумав - скасування до відповіді власника."""
    try:
        req = BookExchangeRequest.objects.get(
            pk=request_id,
            status=BookExchangeRequest.Status.PENDING,
        )
    except BookExchangeRequest.DoesNotExist:
        return False, "Запит не знайдено."

    if req.requester_id != acting_user.id:
        return False, "Скасувати може лише той, хто надіслав запит."

    req.status = BookExchangeRequest.Status.CANCELLED
    req.resolved_at = timezone.now()
    req.save(update_fields=["status", "resolved_at"])
    message_service.notify_exchange_request_cancelled(req)
    return True, None


@transaction.atomic
def request_borrow_return(shelf_id: int, borrower: CustomUser) -> tuple[bool, str | None]:
    """
    Позичальник повідомляє, що повертає книгу. Рядок лишається на його полиці до підтвердження позикодавцем.
    """
    shelf = (
        Shelf.objects.select_related("borrowed_from", "book")
        .select_for_update(of=("self",))
        .filter(pk=shelf_id, user=borrower)
        .first()
    )
    if not shelf:
        return False, "Запис на полиці не знайдено."
    if not shelf.borrowed_from_id:
        return False, "Ця книга не позичена - її можна просто прибрати з полиці."
    if shelf.return_pending:
        return False, "Повернення вже очікує підтвердження позикодавця."

    Shelf.objects.filter(pk=shelf.pk).update(return_pending=True)
    shelf.return_pending = True
    message_service.notify_borrow_return_requested(shelf)
    return True, None


@transaction.atomic
def confirm_borrow_return(shelf_id: int, lender: CustomUser) -> tuple[bool, str | None]:
    """
    Позикодавець підтверджує отримання: видаляємо рядок позичальника.
    Рядок власника вже має бути на його полиці (після фіксу позики); якщо ні — відновлюємо.
    """
    shelf = (
        Shelf.objects.select_related("book", "user", "copy")
        .select_for_update(of=("self",))
        .filter(
            pk=shelf_id,
            borrowed_from=lender,
            return_pending=True,
        )
        .first()
    )
    if not shelf:
        return False, "Немає запису з очікуванням вашого підтвердження повернення."

    owner_id = lender.id
    copy_id = shelf.copy_id
    borrower = shelf.user
    book_title = shelf.book.title
    shelf_pk = shelf.pk

    message_service.mark_return_notifications_read(
        lender,
        shelf_id=shelf_pk,
        borrower_id=borrower.id,
        book_title=book_title,
    )

    owner_row = (
        Shelf.objects.select_for_update(of=("self",))
        .filter(user_id=owner_id, copy_id=copy_id, borrowed_from__isnull=True)
        .first()
    )
    if not owner_row:
        Shelf.objects.filter(pk=shelf.pk).update(
            user_id=owner_id,
            borrowed_from_id=None,
            return_pending=False,
            due_date=None,
        )
        BookCopy.objects.filter(pk=copy_id).update(owner_id=owner_id)
    else:
        shelf.delete()

    message_service.notify_borrow_return_confirmed(lender, borrower, book_title)
    return True, None
