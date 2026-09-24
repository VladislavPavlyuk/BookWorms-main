"""Third-party physical transfer / handoff (SRP)."""
from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .deps import get_notifier, get_queue
from .. import ops_log
from ..copy_events import log_copy_event
from ..error_handling import domain_guard
from ..exceptions import ExchangeForbidden, ExchangeInvalidState, ExchangeNotFound
from ..models import BookExchangeRequest, CopyEvent, CustomUser, LoanHandoff, Shelf
from .due import loan_due_date

_ACTIVE_HANDOFF = (
    LoanHandoff.Status.AWAITING_GIVE,
    LoanHandoff.Status.AWAITING_RECEIVE,
)


def active_handoff_for_copy(copy_id: int | None) -> LoanHandoff | None:
    if not copy_id:
        return None
    try:
        return (
            LoanHandoff.objects.filter(copy_id=copy_id, status__in=_ACTIVE_HANDOFF)
            .select_related("owner", "from_user", "to_user", "copy__book", "exchange_request")
            .first()
        )
    except Exception:
        # Таблиця ще не заmigрена / тимчасова помилка БД — не валимо confirm/accept.
        return None


def handoffs_involving(*user_ids: int) -> list[LoanHandoff]:
    """
    Активні handoff для панелі в чаті.
    Якщо передано ≥2 id — лише ті, де *всі* ці юзери серед owner/from/to.
    """
    ids = [i for i in user_ids if i]
    if not ids:
        return []
    try:
        rows = list(
            LoanHandoff.objects.filter(status__in=_ACTIVE_HANDOFF)
            .filter(Q(owner_id__in=ids) | Q(from_user_id__in=ids) | Q(to_user_id__in=ids))
            .select_related(
                "owner",
                "from_user",
                "to_user",
                "copy__book",
                "exchange_request",
                "from_shelf",
            )
            .order_by("-created_at")
        )
    except Exception:
        return []
    if len(ids) >= 2:
        need = set(ids)
        rows = [
            h
            for h in rows
            if need.issubset({h.owner_id, h.from_user_id, h.to_user_id})
        ]
    return rows


def _lock_handoff(handoff_id: int) -> LoanHandoff:
    return (
        LoanHandoff.objects.select_for_update(of=("self",))
        .select_related("owner", "from_user", "to_user", "copy__book", "exchange_request")
        .get(pk=handoff_id)
    )


def _borrower_shelf_for_copy(copy_id: int, *, user_id: int | None = None) -> Shelf | None:
    qs = Shelf.objects.select_for_update(of=("self",)).filter(
        copy_id=copy_id, borrowed_from__isnull=False
    )
    if user_id is not None:
        qs = qs.filter(user_id=user_id)
    return qs.select_related("user", "book").first()


def _create_handoff_record(
    *,
    copy_id: int,
    owner: CustomUser,
    from_user: CustomUser,
    to_user: CustomUser,
    req: BookExchangeRequest,
    from_shelf: Shelf,
) -> LoanHandoff:
    return LoanHandoff.objects.create(
        copy_id=copy_id,
        owner_id=owner.id,
        from_user_id=from_user.id,
        to_user_id=to_user.id,
        exchange_request=req,
        from_shelf=from_shelf,
        status=LoanHandoff.Status.AWAITING_GIVE,
    )


def _validate_borrower_for_handoff(
    borrower_shelf: Shelf | None,
    requester: CustomUser,
    *,
    cid: str,
    copy_id: int | None,
) -> CustomUser:
    if not borrower_shelf:
        ops_log.warning("handoff.approve.no_loan", cid=cid, copy_id=copy_id)
        raise ExchangeNotFound("Активну позику не знайдено — спробуйте ще раз.")
    previous_holder = borrower_shelf.user
    if previous_holder.id == requester.id:
        raise ExchangeInvalidState("Цей користувач уже тримає примірник.")
    if borrower_shelf.return_pending:
        raise ExchangeInvalidState(
            "Спочатку завершіть повернення від поточного позичальника."
        )
    return previous_holder


@domain_guard("handoff.approve")
def approve_loan_handoff(
    req: BookExchangeRequest,
    owner: CustomUser,
    owner_shelf: Shelf,
    requester: CustomUser,
) -> LoanHandoff:
    """Схвалення ≠ фізичний перенос; полиця переїде після give + receive."""
    cid = ops_log.new_cid()
    ops_log.info(
        "handoff.approve.start",
        cid=cid,
        req_id=req.pk,
        owner_id=owner.id,
        requester_id=requester.id,
        owner_shelf_id=owner_shelf.pk,
        copy_id=owner_shelf.copy_id,
    )
    borrower_shelf = _borrower_shelf_for_copy(owner_shelf.copy_id)
    previous_holder = _validate_borrower_for_handoff(
        borrower_shelf, requester, cid=cid, copy_id=owner_shelf.copy_id
    )
    handoff = _create_handoff_record(
        copy_id=owner_shelf.copy_id,
        owner=owner,
        from_user=previous_holder,
        to_user=requester,
        req=req,
        from_shelf=borrower_shelf,  # type: ignore[arg-type]
    )
    log_copy_event(
        owner_shelf.copy_id,
        CopyEvent.Code.HANDOFF_APPROVED,
        actor=owner,
        holder=previous_holder,
        legal_owner=owner,
        previous_holder=previous_holder,
        counterparty=requester,
        exchange_request=req,
    )
    get_notifier().notify_handoff_approved(handoff)
    ops_log.info("handoff.approve.ok", cid=cid, **ops_log.handoff_snapshot(handoff))
    return handoff


def _move_loan_shelf(
    *,
    borrower_shelf: Shelf,
    to_user: CustomUser,
    owner: CustomUser,
    copy_id: int,
) -> str:
    """Delete borrower row, create loan for to_user. Returns book title."""
    book_title = borrower_shelf.book.title
    book_id = borrower_shelf.book_id
    borrower_shelf.delete()
    Shelf.objects.create(
        user_id=to_user.id,
        book_id=book_id,
        copy_id=copy_id,
        borrowed_from_id=owner.id,
        due_date=loan_due_date(),
        return_pending=False,
    )
    return book_title


def _finalize_completed_handoff(
    handoff: LoanHandoff,
    *,
    owner: CustomUser,
    requester: CustomUser,
    previous_holder: CustomUser,
    book_title: str,
    cid: str,
) -> None:
    copy_id = handoff.copy_id
    req = handoff.exchange_request
    handoff.status = LoanHandoff.Status.COMPLETED
    handoff.resolved_at = timezone.now()
    handoff.from_shelf = None
    handoff.save(update_fields=["status", "resolved_at", "from_shelf"])
    log_copy_event(
        copy_id,
        CopyEvent.Code.TRANSMITTED,
        actor=owner,
        holder=requester,
        legal_owner=owner,
        previous_holder=previous_holder,
        counterparty=requester,
        exchange_request=req,
    )
    get_notifier().notify_loan_transmitted(
        owner, previous_holder, requester, book_title, exchange_request=req
    )
    try:
        get_queue().after_copy_loaned_or_transmitted(copy_id, requester.id)
    except Exception as exc:
        ops_log.exception("handoff.complete.queue_fail", exc, cid=cid, copy_id=copy_id)
    ops_log.info("handoff.complete.ok", cid=cid, **ops_log.handoff_snapshot(handoff))


def complete_loan_handoff_transfer(handoff: LoanHandoff) -> None:
    """Зняти позику з from_user і видати to_user (після обох підтверджень)."""
    cid = ops_log.new_cid()
    ops_log.info("handoff.complete.start", cid=cid, **ops_log.handoff_snapshot(handoff))

    owner = handoff.owner
    requester = handoff.to_user
    previous_holder = handoff.from_user
    copy_id = handoff.copy_id

    borrower_shelf = _borrower_shelf_for_copy(copy_id, user_id=previous_holder.id)
    if not borrower_shelf:
        ops_log.warning(
            "handoff.complete.no_shelf",
            cid=cid,
            copy_id=copy_id,
            from_user_id=previous_holder.id,
        )
        raise ExchangeInvalidState("Позику вже знято — передачу не завершено.")

    book_title = _move_loan_shelf(
        borrower_shelf=borrower_shelf,
        to_user=requester,
        owner=owner,
        copy_id=copy_id,
    )
    _finalize_completed_handoff(
        handoff,
        owner=owner,
        requester=requester,
        previous_holder=previous_holder,
        book_title=book_title,
        cid=cid,
    )


def _assert_can_give(handoff: LoanHandoff, acting_user: CustomUser, cid: str) -> None:
    if handoff.status != LoanHandoff.Status.AWAITING_GIVE:
        ops_log.warning(
            "handoff.give.bad_status",
            cid=cid,
            status=handoff.status,
            actor_id=acting_user.id,
        )
        raise ExchangeInvalidState("Зараз не чекається підтвердження віддачі.")
    if acting_user.id != handoff.from_user_id:
        ops_log.warning(
            "handoff.give.forbidden",
            cid=cid,
            actor_id=acting_user.id,
            from_user_id=handoff.from_user_id,
        )
        raise ExchangeForbidden(
            "Підтвердити віддачу може лише поточний тримач книги."
        )


def _assert_can_receive(handoff: LoanHandoff, acting_user: CustomUser, cid: str) -> None:
    if handoff.status != LoanHandoff.Status.AWAITING_RECEIVE:
        if handoff.status == LoanHandoff.Status.AWAITING_GIVE:
            ops_log.warning("handoff.receive.need_give_first", cid=cid)
            raise ExchangeInvalidState(
                "Спочатку поточний тримач має підтвердити віддачу."
            )
        ops_log.warning("handoff.receive.bad_status", cid=cid, status=handoff.status)
        raise ExchangeInvalidState("Зараз не чекається підтвердження отримання.")
    if acting_user.id != handoff.to_user_id:
        ops_log.warning(
            "handoff.receive.forbidden",
            cid=cid,
            actor_id=acting_user.id,
            to_user_id=handoff.to_user_id,
        )
        raise ExchangeForbidden(
            "Підтвердити отримання може лише наступний позичальник."
        )


@domain_guard("handoff.give")
@transaction.atomic
def confirm_handoff_give(handoff_id: int, acting_user: CustomUser) -> None:
    """Поточний позичальник підтверджує, що фізично віддав книгу наступному."""
    cid = ops_log.new_cid()
    ops_log.info(
        "handoff.give.start",
        cid=cid,
        handoff_id=handoff_id,
        actor_id=acting_user.id,
    )
    try:
        handoff = _lock_handoff(handoff_id)
    except LoanHandoff.DoesNotExist as exc:
        ops_log.warning("handoff.give.missing", cid=cid, handoff_id=handoff_id)
        raise ExchangeNotFound("Передачу не знайдено.") from exc

    ops_log.info("handoff.give.locked", cid=cid, **ops_log.handoff_snapshot(handoff))
    _assert_can_give(handoff, acting_user, cid)

    handoff.status = LoanHandoff.Status.AWAITING_RECEIVE
    handoff.giver_confirmed_at = timezone.now()
    handoff.save(update_fields=["status", "giver_confirmed_at"])
    log_copy_event(
        handoff.copy_id,
        CopyEvent.Code.HANDOFF_GIVEN,
        actor=acting_user,
        holder=acting_user,
        legal_owner=handoff.owner,
        previous_holder=acting_user,
        counterparty=handoff.to_user,
        exchange_request=handoff.exchange_request,
    )
    get_notifier().notify_handoff_given(handoff)
    ops_log.info("handoff.give.ok", cid=cid, **ops_log.handoff_snapshot(handoff))


@domain_guard("handoff.receive")
@transaction.atomic
def confirm_handoff_receive(handoff_id: int, acting_user: CustomUser) -> None:
    """Наступний позичальник підтверджує отримання — полиця переїздить."""
    cid = ops_log.new_cid()
    ops_log.info(
        "handoff.receive.start",
        cid=cid,
        handoff_id=handoff_id,
        actor_id=acting_user.id,
    )
    try:
        handoff = _lock_handoff(handoff_id)
    except LoanHandoff.DoesNotExist as exc:
        ops_log.warning("handoff.receive.missing", cid=cid, handoff_id=handoff_id)
        raise ExchangeNotFound("Передачу не знайдено.") from exc

    _assert_can_receive(handoff, acting_user, cid)
    handoff.receiver_confirmed_at = timezone.now()
    handoff.save(update_fields=["receiver_confirmed_at"])
    try:
        complete_loan_handoff_transfer(handoff)
    except ExchangeInvalidState as exc:
        ops_log.warning("handoff.receive.complete_fail", cid=cid, err=str(exc))
        raise
    ops_log.info("handoff.receive.ok", cid=cid, handoff_id=handoff_id)


@domain_guard("handoff.cancel")
@transaction.atomic
def cancel_loan_handoff(handoff_id: int, acting_user: CustomUser) -> None:
    """Власник скасовує схвалену, але ще не завершену фізичну передачу."""
    cid = ops_log.new_cid()
    try:
        handoff = _lock_handoff(handoff_id)
    except LoanHandoff.DoesNotExist as exc:
        raise ExchangeNotFound("Передачу не знайдено.") from exc

    if handoff.status not in _ACTIVE_HANDOFF:
        raise ExchangeInvalidState("Цю передачу вже завершено або скасовано.")
    if acting_user.id != handoff.owner_id:
        raise ExchangeForbidden("Скасувати може лише власник примірника.")

    handoff.status = LoanHandoff.Status.CANCELLED
    handoff.resolved_at = timezone.now()
    handoff.save(update_fields=["status", "resolved_at"])
    get_notifier().notify_handoff_cancelled(handoff)
    ops_log.info("handoff.cancel.ok", cid=cid, **ops_log.handoff_snapshot(handoff))


@domain_guard("handoff.transmit")
def transmit_loan_to_requester(
    req: BookExchangeRequest,
    owner: CustomUser,
    owner_shelf: Shelf,
    requester: CustomUser,
) -> LoanHandoff:
    """Legacy alias — тепер схвалення створює handoff, не миттєвий перенос."""
    return approve_loan_handoff(req, owner, owner_shelf, requester)


_approve_loan_handoff = approve_loan_handoff
_complete_loan_handoff_transfer = complete_loan_handoff_transfer
_transmit_loan_to_requester = transmit_loan_to_requester
