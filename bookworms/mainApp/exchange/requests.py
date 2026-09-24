"""Exchange request create / accept / reject / cancel (SRP)."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .. import message_service
from ..copy_events import log_copy_event
from ..error_handling import domain_guard
from ..exceptions import (
    ExchangeConflict,
    ExchangeError,
    ExchangeForbidden,
    ExchangeInvalidState,
    ExchangeNotFound,
)
from ..models import BookCopy, BookExchangeRequest, CopyEvent, CustomUser, Shelf
from .copies import is_copy_lent_out
from .due import loan_due_date
from .handoff import active_handoff_for_copy, approve_loan_handoff


@domain_guard("exchange.create_request")
def create_exchange_request(
    requester: CustomUser,
    target_shelf: Shelf,
    offer_shelf: Shelf | None = None,
    *,
    from_queue: bool = False,
    join_queue_if_busy: bool = True,
) -> BookExchangeRequest:
    """
    Створює запит. Помилка — ExchangeError.
    Без offer_shelf: після прийняття - позика (borrowed_from = власник).
    З offer_shelf: обмін двома примірниками (повна передача, без позики).

    Якщо примірник уже в позиці і це запит на позику — створюємо запит на
    *передачу третій особі* (власник може прийняти) і ставимо в чергу.
    """
    from .. import queue_service

    if target_shelf.user_id == requester.id:
        raise ExchangeInvalidState("Не можна запитувати власну книгу.")

    if target_shelf.borrowed_from_id:
        raise ExchangeInvalidState(
            "Неможливо запитувати позичену в іншого користувача книгу."
        )

    lent = is_copy_lent_out(target_shelf.copy_id)

    if lent and offer_shelf is not None:
        raise ExchangeInvalidState("Неможливо обміняти примірник, який зараз у позиці.")

    if lent and active_handoff_for_copy(target_shelf.copy_id):
        raise ExchangeConflict(
            "Для цього примірника вже схвалено передачу — дочекайтесь фізичної передачі."
        )

    if offer_shelf is not None:
        if offer_shelf.user_id != requester.id:
            raise ExchangeForbidden("Запропонована книга має бути з вашої полиці.")
        if offer_shelf.borrowed_from_id:
            raise ExchangeInvalidState(
                "Неможна віддавати в обмін позичену книгу - спочатку поверніть її власнику."
            )
        if is_copy_lent_out(offer_shelf.copy_id):
            raise ExchangeInvalidState(
                "Неможна віддавати в обмін книгу, яка зараз у когось у позиці."
            )
        if offer_shelf.copy_id == target_shelf.copy_id:
            raise ExchangeInvalidState("Немає сенсу обмінювати той самий примірник.")

    pending = BookExchangeRequest.Status.PENDING
    if BookExchangeRequest.objects.filter(
        target_shelf=target_shelf,
        requester=requester,
        status=pending,
    ).exists():
        raise ExchangeConflict("Ви вже маєте активний запит щодо цієї книги.")

    if Shelf.objects.filter(user=requester, copy_id=target_shelf.copy_id).exists():
        raise ExchangeConflict("Цей примірник вже є у вас на полиці.")

    req = BookExchangeRequest.objects.create(
        target_shelf=target_shelf,
        shelf_owner=target_shelf.user,
        requester=requester,
        offer_shelf=offer_shelf,
        status=pending,
    )

    if not from_queue:
        if lent and offer_shelf is None:
            message_service.notify_transmission_request_created(req)
        else:
            message_service.notify_exchange_request_created(req)

    if lent and offer_shelf is None:
        if join_queue_if_busy and target_shelf.copy_id:
            queue_service.join_queue(
                requester,
                target_shelf.copy,
                notify=not from_queue,
                exchange_request=req,
            )
    elif (
        join_queue_if_busy
        and offer_shelf is None
        and target_shelf.copy_id
        and not from_queue
    ):
        other_pending = (
            BookExchangeRequest.objects.filter(
                target_shelf__copy_id=target_shelf.copy_id,
                status=pending,
                offer_shelf__isnull=True,
            )
            .exclude(pk=req.pk)
            .exists()
        )
        if other_pending:
            queue_service.join_queue(
                requester, target_shelf.copy, notify=True, exchange_request=req
            )

    return req


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
                errs.append(
                    f'"{label}": цю свою книгу вже обрано для іншого рядка в цьому пакеті.'
                )
                continue
            seen_offer_ids.add(oid)
        filtered.append((target_shelf, offer_shelf))

    for target_shelf, offer_shelf in filtered:
        label = short_title(target_shelf)
        try:
            create_exchange_request(requester, target_shelf, offer_shelf)
            ok += 1
        except ExchangeError as exc:
            errs.append(f"'{label}': {exc.message}")
    return ok, errs


@domain_guard("exchange.accept")
@transaction.atomic
def accept_exchange_request(request_id: int, acting_user: CustomUser) -> None:
    """
    Власник погоджується.
    Позика: власник ЗБЕРІГАЄ свій рядок Shelf; позичальнику створюється окремий рядок
    з borrowed_from на той самий BookCopy.
    Обмін: обидва рядки міняють user_id і owner на BookCopy (повна передача).

    Якщо примірник уже в позиці — *передача третій особі*: схвалення створює handoff.
    """
    from .. import queue_service

    try:
        req = BookExchangeRequest.objects.select_for_update().get(
            pk=request_id,
            status=BookExchangeRequest.Status.PENDING,
        )
    except BookExchangeRequest.DoesNotExist as exc:
        raise ExchangeNotFound("Запит не знайдено або вже оброблено.") from exc

    if req.shelf_owner_id != acting_user.id:
        raise ExchangeForbidden("Ви не власник цієї книги.")

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
        raise ExchangeNotFound("Книги вже немає на вашій полиці.")
    if target.borrowed_from_id:
        raise ExchangeInvalidState("Не можна віддати позичену книгу.")

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
            raise ExchangeNotFound("Запропонована книга більше не на полиці відправника.")
        if offer.borrowed_from_id or is_copy_lent_out(offer.copy_id):
            raise ExchangeInvalidState(
                "Запропонована книга недоступна для обміну (позика)."
            )

    if Shelf.objects.filter(user=requester, copy_id=target.copy_id).exists():
        raise ExchangeConflict(
            "У користувача вже є цей примірник - неможливо завершити обмін."
        )

    if is_copy_lent_out(target.copy_id):
        if offer is not None:
            raise ExchangeInvalidState("Неможливо обміняти примірник, який зараз у позиці.")
        if active_handoff_for_copy(target.copy_id):
            raise ExchangeConflict(
                "Для цього примірника вже є активна фізична передача."
            )
        approve_loan_handoff(req, acting_user, target, requester)
        req.status = BookExchangeRequest.Status.ACCEPTED
        req.resolved_at = timezone.now()
        req.save(update_fields=["status", "resolved_at"])
        return

    if offer:
        if (
            Shelf.objects.filter(user=acting_user, copy_id=offer.copy_id)
            .exclude(pk=offer.pk)
            .exists()
        ):
            raise ExchangeConflict("У вас уже є запропонований до обміну примірник.")
        prev_target_owner = acting_user
        prev_offer_owner = requester
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
        log_copy_event(
            target.copy_id,
            CopyEvent.Code.EXCHANGED,
            actor=acting_user,
            holder=requester,
            legal_owner=requester,
            previous_holder=prev_target_owner,
            previous_owner=prev_target_owner,
            counterparty=requester,
            exchange_request=req,
        )
        log_copy_event(
            offer.copy_id,
            CopyEvent.Code.EXCHANGED,
            actor=acting_user,
            holder=acting_user,
            legal_owner=acting_user,
            previous_holder=prev_offer_owner,
            previous_owner=prev_offer_owner,
            counterparty=acting_user,
            exchange_request=req,
        )
    else:
        Shelf.objects.create(
            user_id=requester.id,
            book_id=target.book_id,
            copy_id=target.copy_id,
            borrowed_from_id=acting_user.id,
            due_date=loan_due_date(),
            return_pending=False,
        )
        log_copy_event(
            target.copy_id,
            CopyEvent.Code.LOANED,
            actor=acting_user,
            holder=requester,
            legal_owner=acting_user,
            previous_holder=acting_user,
            counterparty=requester,
            exchange_request=req,
        )
        queue_service.after_copy_loaned_or_transmitted(target.copy_id, requester.id)

    req.status = BookExchangeRequest.Status.ACCEPTED
    req.resolved_at = timezone.now()
    req.save(update_fields=["status", "resolved_at"])
    message_service.notify_exchange_request_accepted(req)


@domain_guard("exchange.reject")
def reject_exchange_request(request_id: int, acting_user: CustomUser) -> None:
    try:
        req = BookExchangeRequest.objects.get(
            pk=request_id,
            status=BookExchangeRequest.Status.PENDING,
        )
    except BookExchangeRequest.DoesNotExist as exc:
        raise ExchangeNotFound("Запит не знайдено.") from exc

    if req.shelf_owner_id != acting_user.id:
        raise ExchangeForbidden("Ви не власник цієї книги.")

    req.status = BookExchangeRequest.Status.REJECTED
    req.resolved_at = timezone.now()
    req.save(update_fields=["status", "resolved_at"])
    message_service.notify_exchange_request_rejected(req)


@domain_guard("exchange.cancel")
def cancel_exchange_request(request_id: int, acting_user: CustomUser) -> None:
    """Той, хто надсилав запит, передумав - скасування до відповіді власника."""
    from .. import queue_service

    try:
        req = BookExchangeRequest.objects.get(
            pk=request_id,
            status=BookExchangeRequest.Status.PENDING,
        )
    except BookExchangeRequest.DoesNotExist as exc:
        raise ExchangeNotFound("Запит не знайдено.") from exc

    if req.requester_id != acting_user.id:
        raise ExchangeForbidden("Скасувати може лише той, хто надіслав запит.")

    copy_id = req.target_shelf.copy_id
    req.status = BookExchangeRequest.Status.CANCELLED
    req.resolved_at = timezone.now()
    req.save(update_fields=["status", "resolved_at"])
    message_service.notify_exchange_request_cancelled(req)
    if copy_id:
        queue_service.leave_queue(acting_user, copy_id)
