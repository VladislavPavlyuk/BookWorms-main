"""
Сервіс обміну та позик книг (чиста логіка без HTTP).

Навіщо окремий файл: щоб правила "хто кому що може" були в одному місці,
а views лише викликали ці функції й показували повідомлення користувачу.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from . import message_service
from .models import Book, BookExchangeRequest, CustomUser, Shelf


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
    З offer_shelf: обмін двома книгами (повна передача, без позики).
    """
    if target_shelf.user_id == requester.id:
        return None, "Не можна запитувати власну книгу."

    # Не пропонуємо "віджати" книгу, яку хтось тримає як позичену (вона не його власність для обміну).
    if target_shelf.borrowed_from_id:
        return None, "Неможливо запитувати позичену в іншого користувача книгу."

    if offer_shelf is not None:
        if offer_shelf.user_id != requester.id:
            return None, "Запропонована книга має бути з вашої полиці."
        if offer_shelf.borrowed_from_id:
            return None, "Неможна віддавати в обмін позичену книгу - спочатку поверніть її власнику."
        if offer_shelf.book_id == target_shelf.book_id:
            return None, "Немає сенсу обмінювати книгу на ту саму."

    pending = BookExchangeRequest.Status.PENDING
    # Один активний запит від того самого користувача на той самий рядок полиці - щоб не спамити.
    if BookExchangeRequest.objects.filter(
        target_shelf=target_shelf,
        requester=requester,
        status=pending,
    ).exists():
        return None, "Ви вже маєте активний запит щодо цієї книги."

    if Shelf.objects.filter(user=requester, book=target_shelf.book).exists():
        return None, "Ця книга вже є у вас на полиці."

    req = BookExchangeRequest.objects.create(
        target_shelf=target_shelf,
        shelf_owner=target_shelf.user,
        requester=requester,
        offer_shelf=offer_shelf,
        status=pending,
    )
    # Сповіщення власнику книги в скриньку "Повідомлення" (сервіс обміну повідомленнями).
    message_service.notify_exchange_request_created(req)
    return req, None


@transaction.atomic
def accept_exchange_request(request_id: int, acting_user: CustomUser) -> tuple[bool, str | None]:
    """
    Власник погоджується: оновлюємо рядки Shelf (не видаляємо їх - щоб не ламати посилання в запиті).
    atomic + select_for_update: два одночасні "Прийняти" не зіпсують дані.
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

    target = Shelf.objects.select_for_update().filter(
        pk=req.target_shelf_id,
        user_id=req.shelf_owner_id,
    ).select_related("book").first()
    if not target:
        return False, "Книги вже немає на вашій полиці."

    requester = CustomUser.objects.select_for_update().get(pk=req.requester_id)
    book_to_transfer = target.book

    offer = None
    if req.offer_shelf_id:
        offer = (
            Shelf.objects.select_for_update()
            .filter(pk=req.offer_shelf_id, user=requester)
            .select_related("book")
            .first()
        )
        if not offer:
            return False, "Запропонована книга більше не на полиці відправника."

    if Shelf.objects.filter(user=requester, book=book_to_transfer).exclude(pk=target.pk).exists():
        return False, "У користувача вже є ця книга - неможливо завершити обмін."

    if offer:
        # Обмін: обидві книги переходять у власність без статусу позики
        Shelf.objects.filter(pk=target.pk).update(
            user_id=requester.id,
            borrowed_from_id=None,
        )
        offer_book = offer.book
        if Shelf.objects.filter(user=acting_user, book=offer_book).exclude(pk=offer.pk).exists():
            return False, "У вас уже є запропонована до обміну книга."
        Shelf.objects.filter(pk=offer.pk).update(
            user_id=acting_user.id,
            borrowed_from_id=None,
        )
    else:
        # Позика: позичальник тримає книгу, власник зберігається в borrowed_from
        Shelf.objects.filter(pk=target.pk).update(
            user_id=requester.id,
            borrowed_from_id=acting_user.id,
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
def return_borrowed_book(shelf_id: int, borrower: CustomUser) -> tuple[bool, str | None]:
    """
    Позичальник натискає "Повернути власнику": той самий рядок Shelf залишається,
    але user стає власником, borrowed_from очищується (книга знову "повністю його").
    """
    shelf = (
        Shelf.objects.select_for_update()
        .filter(pk=shelf_id, user=borrower)
        .select_related("borrowed_from")
        .first()
    )
    if not shelf:
        return False, "Запис на полиці не знайдено."
    if not shelf.borrowed_from_id:
        return False, "Ця книга не позичена - її можна просто прибрати з полиці."

    owner_id = shelf.borrowed_from_id
    book_id = shelf.book_id

    # Захист від порушення унікальності (user, book), якщо власник якимось чином вже має дубль.
    if Shelf.objects.filter(user_id=owner_id, book_id=book_id).exclude(pk=shelf.pk).exists():
        return False, "У власника вже є ця книга на полиці - зверніться до адміністратора."

    # Один UPDATE замість delete+create - історія та id запису зберігаються.
    Shelf.objects.filter(pk=shelf.pk).update(user_id=owner_id, borrowed_from_id=None)
    return True, None
