"""Exchange request create / accept / reject / cancel (SRP)."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .deps import get_notifier, get_queue
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
from .due import parse_due_date, resolve_loan_due_date, validate_proposed_due_date
from .handoff import active_handoff_for_copy, approve_loan_handoff


def _validate_create_request(
    requester: CustomUser,
    target_shelf: Shelf,
    offer_shelf: Shelf | None,
) -> bool:
    """Returns whether target copy is currently lent out."""
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
        _validate_offer_shelf(requester, target_shelf, offer_shelf)

    if BookExchangeRequest.objects.filter(
        target_shelf=target_shelf,
        requester=requester,
        status=BookExchangeRequest.Status.PENDING,
    ).exists():
        raise ExchangeConflict("Ви вже маєте активний запит щодо цієї книги.")

    if Shelf.objects.filter(user=requester, copy_id=target_shelf.copy_id).exists():
        raise ExchangeConflict("Цей примірник вже є у вас на полиці.")

    return lent


def _validate_offer_shelf(
    requester: CustomUser, target_shelf: Shelf, offer_shelf: Shelf
) -> None:
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


def _enqueue_after_create(
    requester: CustomUser,
    target_shelf: Shelf,
    offer_shelf: Shelf | None,
    req: BookExchangeRequest,
    *,
    lent: bool,
    from_queue: bool,
    join_queue_if_busy: bool,
) -> None:
    if not from_queue:
        if lent and offer_shelf is None:
            get_notifier().notify_transmission_request_created(req)
        else:
            get_notifier().notify_exchange_request_created(req)

    if lent and offer_shelf is None:
        if join_queue_if_busy and target_shelf.copy_id:
            get_queue().join_queue(
                requester,
                target_shelf.copy,
                notify=not from_queue,
                exchange_request=req,
            )
        return

    if not (
        join_queue_if_busy
        and offer_shelf is None
        and target_shelf.copy_id
        and not from_queue
    ):
        return

    other_pending = (
        BookExchangeRequest.objects.filter(
            target_shelf__copy_id=target_shelf.copy_id,
            status=BookExchangeRequest.Status.PENDING,
            offer_shelf__isnull=True,
        )
        .exclude(pk=req.pk)
        .exists()
    )
    if other_pending:
        get_queue().join_queue(
            requester, target_shelf.copy, notify=True, exchange_request=req
        )


@domain_guard("exchange.create_request")
def create_exchange_request(
    requester: CustomUser,
    target_shelf: Shelf,
    offer_shelf: Shelf | None = None,
    *,
    from_queue: bool = False,
    join_queue_if_busy: bool = True,
    proposed_due_date=None,
) -> BookExchangeRequest:
    """
    Створює запит. Помилка — ExchangeError.
    Без offer_shelf: після прийняття - позика; з offer_shelf: повний обмін.
    Lent + позика → запит на передачу третій особі + черга.
    proposed_due_date — запропонований термін повернення (лише позика / передача).
    """
    lent = _validate_create_request(requester, target_shelf, offer_shelf)
    due = None
    if not offer_shelf and proposed_due_date is not None:
        try:
            parsed = parse_due_date(proposed_due_date)
            due = validate_proposed_due_date(parsed) if parsed else None
        except ValueError as exc:
            raise ExchangeError(str(exc)) from exc
    req = BookExchangeRequest.objects.create(
        target_shelf=target_shelf,
        shelf_owner=target_shelf.user,
        requester=requester,
        offer_shelf=offer_shelf,
        status=BookExchangeRequest.Status.PENDING,
        proposed_due_date=due,
        due_date_proposer=BookExchangeRequest.DueProposer.REQUESTER,
        due_date_confirmed=False,
    )
    _enqueue_after_create(
        requester,
        target_shelf,
        offer_shelf,
        req,
        lent=lent,
        from_queue=from_queue,
        join_queue_if_busy=join_queue_if_busy,
    )
    return req


def _short_shelf_title(s: Shelf) -> str:
    t = s.book.title
    return (t[:52] + "…") if len(t) > 55 else t


def create_many_exchange_requests(
    requester: CustomUser,
    lines: list[tuple[Shelf, Shelf | None, object | None]],
) -> tuple[int, list[str]]:
    """Кілька запитів за одну дію; та сама offer_shelf — лише раз у пакеті.

    lines: (target, offer|None, proposed_due_date|None)
    """
    ok = 0
    errs: list[str] = []
    seen_offer_ids: set[int] = set()
    filtered: list[tuple[Shelf, Shelf | None, object | None]] = []

    for target_shelf, offer_shelf, proposed_due in lines:
        label = _short_shelf_title(target_shelf)
        if offer_shelf is not None:
            oid = offer_shelf.pk
            if oid in seen_offer_ids:
                errs.append(
                    f'"{label}": цю свою книгу вже обрано для іншого рядка в цьому пакеті.'
                )
                continue
            seen_offer_ids.add(oid)
        filtered.append((target_shelf, offer_shelf, proposed_due))

    for target_shelf, offer_shelf, proposed_due in filtered:
        label = _short_shelf_title(target_shelf)
        try:
            create_exchange_request(
                requester,
                target_shelf,
                offer_shelf,
                proposed_due_date=proposed_due,
            )
            ok += 1
        except ExchangeError as exc:
            errs.append(f"'{label}': {exc.message}")
    return ok, errs


def _lock_pending_request(request_id: int) -> BookExchangeRequest:
    try:
        return BookExchangeRequest.objects.select_for_update().get(
            pk=request_id,
            status=BookExchangeRequest.Status.PENDING,
        )
    except BookExchangeRequest.DoesNotExist as exc:
        raise ExchangeNotFound("Запит не знайдено або вже оброблено.") from exc


def _lock_accept_shelves(
    req: BookExchangeRequest, requester: CustomUser
) -> tuple[Shelf, Shelf | None]:
    target = (
        Shelf.objects.select_for_update(of=("self",))
        .filter(pk=req.target_shelf_id, user_id=req.shelf_owner_id)
        .select_related("book", "copy")
        .first()
    )
    if not target:
        raise ExchangeNotFound("Книги вже немає на вашій полиці.")
    if target.borrowed_from_id:
        raise ExchangeInvalidState("Не можна віддати позичену книгу.")

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
    return target, offer


def _mark_request_accepted(req: BookExchangeRequest) -> None:
    req.status = BookExchangeRequest.Status.ACCEPTED
    req.resolved_at = timezone.now()
    req.save(update_fields=["status", "resolved_at"])


def _accept_as_handoff(
    req: BookExchangeRequest,
    owner: CustomUser,
    target: Shelf,
    requester: CustomUser,
    offer: Shelf | None,
) -> None:
    if offer is not None:
        raise ExchangeInvalidState("Неможливо обміняти примірник, який зараз у позиці.")
    if active_handoff_for_copy(target.copy_id):
        raise ExchangeConflict("Для цього примірника вже є активна фізична передача.")
    approve_loan_handoff(req, owner, target, requester)
    _mark_request_accepted(req)


def _accept_as_swap(
    req: BookExchangeRequest,
    owner: CustomUser,
    target: Shelf,
    requester: CustomUser,
    offer: Shelf,
) -> None:
    if (
        Shelf.objects.filter(user=owner, copy_id=offer.copy_id)
        .exclude(pk=offer.pk)
        .exists()
    ):
        raise ExchangeConflict("У вас уже є запропонований до обміну примірник.")

    Shelf.objects.filter(pk=target.pk).update(
        user_id=requester.id,
        borrowed_from_id=None,
        due_date=None,
        return_pending=False,
    )
    Shelf.objects.filter(pk=offer.pk).update(
        user_id=owner.id,
        borrowed_from_id=None,
        due_date=None,
        return_pending=False,
    )
    BookCopy.objects.filter(pk=target.copy_id).update(owner_id=requester.id)
    BookCopy.objects.filter(pk=offer.copy_id).update(owner_id=owner.id)
    log_copy_event(
        target.copy_id,
        CopyEvent.Code.EXCHANGED,
        actor=owner,
        holder=requester,
        legal_owner=requester,
        previous_holder=owner,
        previous_owner=owner,
        counterparty=requester,
        exchange_request=req,
    )
    log_copy_event(
        offer.copy_id,
        CopyEvent.Code.EXCHANGED,
        actor=owner,
        holder=owner,
        legal_owner=owner,
        previous_holder=requester,
        previous_owner=requester,
        counterparty=owner,
        exchange_request=req,
    )


def _accept_as_loan(
    req: BookExchangeRequest,
    owner: CustomUser,
    target: Shelf,
    requester: CustomUser,
    *,
    due_date=None,
) -> None:
    try:
        due = resolve_loan_due_date(
            proposed=req.proposed_due_date,
            override=parse_due_date(due_date) if due_date is not None else None,
        )
    except ValueError as exc:
        raise ExchangeError(str(exc)) from exc
    Shelf.objects.create(
        user_id=requester.id,
        book_id=target.book_id,
        copy_id=target.copy_id,
        borrowed_from_id=owner.id,
        due_date=due,
        return_pending=False,
    )
    log_copy_event(
        target.copy_id,
        CopyEvent.Code.LOANED,
        actor=owner,
        holder=requester,
        legal_owner=owner,
        previous_holder=owner,
        counterparty=requester,
        exchange_request=req,
    )
    get_queue().after_copy_loaned_or_transmitted(target.copy_id, requester.id)


@domain_guard("exchange.accept")
@transaction.atomic
def accept_exchange_request(
    request_id: int,
    acting_user: CustomUser,
    *,
    due_date=None,
) -> None:
    """
    Власник погоджується: позика / обмін / handoff (якщо примірник уже в позиці).
    due_date — опційний override терміну (інакше proposed_due_date / дефолт).
    """
    req = _lock_pending_request(request_id)
    if req.shelf_owner_id != acting_user.id:
        raise ExchangeForbidden("Ви не власник цієї книги.")

    requester = CustomUser.objects.select_for_update().get(pk=req.requester_id)
    target, offer = _lock_accept_shelves(req, requester)

    if Shelf.objects.filter(user=requester, copy_id=target.copy_id).exists():
        raise ExchangeConflict(
            "У користувача вже є цей примірник - неможливо завершити обмін."
        )

    if is_copy_lent_out(target.copy_id):
        _accept_as_handoff(req, acting_user, target, requester, offer)
        return

    if offer:
        _accept_as_swap(req, acting_user, target, requester, offer)
    else:
        _accept_as_loan(req, acting_user, target, requester, due_date=due_date)

    _mark_request_accepted(req)
    get_notifier().notify_exchange_request_accepted(req)


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
    get_notifier().notify_exchange_request_rejected(req)


@domain_guard("exchange.cancel")
def cancel_exchange_request(request_id: int, acting_user: CustomUser) -> None:
    """Той, хто надсилав запит, передумав - скасування до відповіді власника."""
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
    get_notifier().notify_exchange_request_cancelled(req)
    if copy_id:
        get_queue().leave_queue(acting_user, copy_id)


@domain_guard("exchange.propose_due")
@transaction.atomic
def propose_exchange_due_date(
    request_id: int,
    acting_user: CustomUser,
    due_date,
) -> BookExchangeRequest:
    """
    Власник або позичальник пропонує / змінює термін повернення (лише позика/передача).
    Інша сторона має підтвердити (confirm) або відповісти новою пропозицією.
    """
    req = _lock_pending_request(request_id)
    if req.offer_shelf_id:
        raise ExchangeInvalidState("Для обміну термін повернення не потрібен.")
    is_owner = acting_user.id == req.shelf_owner_id
    is_requester = acting_user.id == req.requester_id
    if not (is_owner or is_requester):
        raise ExchangeForbidden("Немає доступу до цього запиту.")
    try:
        parsed = parse_due_date(due_date)
        if parsed is None:
            raise ExchangeError("Вкажіть дату повернення.")
        due = validate_proposed_due_date(parsed)
    except ValueError as exc:
        raise ExchangeError(str(exc)) from exc

    req.proposed_due_date = due
    req.due_date_proposer = (
        BookExchangeRequest.DueProposer.OWNER
        if is_owner
        else BookExchangeRequest.DueProposer.REQUESTER
    )
    req.due_date_confirmed = False
    req.save(
        update_fields=["proposed_due_date", "due_date_proposer", "due_date_confirmed"]
    )
    get_notifier().notify_exchange_due_proposed(req, acting_user)
    return req


@domain_guard("exchange.confirm_due")
@transaction.atomic
def confirm_exchange_due_date(
    request_id: int, acting_user: CustomUser
) -> BookExchangeRequest:
    """Погодити поточну пропозицію терміну (робить сторона, яка НЕ пропонувала останньою)."""
    req = _lock_pending_request(request_id)
    if req.offer_shelf_id:
        raise ExchangeInvalidState("Для обміну термін повернення не потрібен.")
    if not req.proposed_due_date:
        raise ExchangeInvalidState("Немає запропонованої дати для підтвердження.")

    is_owner = acting_user.id == req.shelf_owner_id
    is_requester = acting_user.id == req.requester_id
    if not (is_owner or is_requester):
        raise ExchangeForbidden("Немає доступу до цього запиту.")

    proposer = req.due_date_proposer or BookExchangeRequest.DueProposer.REQUESTER
    if proposer == BookExchangeRequest.DueProposer.OWNER and not is_requester:
        raise ExchangeForbidden("Підтвердити пропозицію власника може лише позичальник.")
    if proposer == BookExchangeRequest.DueProposer.REQUESTER and not is_owner:
        raise ExchangeForbidden("Підтвердити пропозицію позичальника може лише власник.")

    if req.due_date_confirmed:
        return req

    req.due_date_confirmed = True
    req.save(update_fields=["due_date_confirmed"])
    get_notifier().notify_exchange_due_confirmed(req, acting_user)
    return req
