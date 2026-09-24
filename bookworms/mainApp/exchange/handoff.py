"""Third-party physical transfer / handoff (SRP)."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .. import message_service
from .. import ops_log
from ..copy_events import log_copy_event
from ..models import BookExchangeRequest, CopyEvent, CustomUser, LoanHandoff, Shelf
from .due import loan_due_date

def active_handoff_for_copy(copy_id: int | None) -> LoanHandoff | None:
    if not copy_id:
        return None
    try:
        return (
            LoanHandoff.objects.filter(
                copy_id=copy_id,
                status__in=(
                    LoanHandoff.Status.AWAITING_GIVE,
                    LoanHandoff.Status.AWAITING_RECEIVE,
                ),
            )
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
    from django.db.models import Q

    ids = [i for i in user_ids if i]
    if not ids:
        return []
    try:
        qs = (
            LoanHandoff.objects.filter(
                status__in=(
                    LoanHandoff.Status.AWAITING_GIVE,
                    LoanHandoff.Status.AWAITING_RECEIVE,
                )
            )
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
        rows = list(qs)
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



def approve_loan_handoff(
    req: BookExchangeRequest,
    owner: CustomUser,
    owner_shelf: Shelf,
    requester: CustomUser,
) -> tuple[bool, str | None]:
    """
    Власник схвалив передачу: книга лишається у поточного позичальника,
    створюється LoanHandoff. Полиця переїде лише після confirm give + receive.
    """
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
    borrower_shelf = (
        Shelf.objects.select_for_update(of=("self",))
        .filter(copy_id=owner_shelf.copy_id, borrowed_from__isnull=False)
        .select_related("user", "book")
        .first()
    )
    if not borrower_shelf:
        ops_log.warning("handoff.approve.no_loan", cid=cid, copy_id=owner_shelf.copy_id)
        return False, "Активну позику не знайдено — спробуйте ще раз."

    previous_holder = borrower_shelf.user
    if previous_holder.id == requester.id:
        return False, "Цей користувач уже тримає примірник."
    if borrower_shelf.return_pending:
        return False, "Спочатку завершіть повернення від поточного позичальника."

    copy_id = owner_shelf.copy_id
    handoff = LoanHandoff.objects.create(
        copy_id=copy_id,
        owner_id=owner.id,
        from_user_id=previous_holder.id,
        to_user_id=requester.id,
        exchange_request=req,
        from_shelf=borrower_shelf,
        status=LoanHandoff.Status.AWAITING_GIVE,
    )
    log_copy_event(
        copy_id,
        CopyEvent.Code.HANDOFF_APPROVED,
        actor=owner,
        holder=previous_holder,
        legal_owner=owner,
        previous_holder=previous_holder,
        counterparty=requester,
        exchange_request=req,
    )
    message_service.notify_handoff_approved(handoff)
    ops_log.info(
        "handoff.approve.ok",
        cid=cid,
        **ops_log.handoff_snapshot(handoff),
    )
    return True, None


def complete_loan_handoff_transfer(handoff: LoanHandoff) -> tuple[bool, str | None]:
    """Зняти позику з from_user і видати to_user (після обох підтверджень)."""
    from .. import queue_service

    cid = ops_log.new_cid()
    ops_log.info("handoff.complete.start", cid=cid, **ops_log.handoff_snapshot(handoff))

    owner = handoff.owner
    requester = handoff.to_user
    previous_holder = handoff.from_user
    copy_id = handoff.copy_id
    req = handoff.exchange_request

    borrower_shelf = (
        Shelf.objects.select_for_update(of=("self",))
        .filter(copy_id=copy_id, borrowed_from__isnull=False, user_id=previous_holder.id)
        .select_related("user", "book")
        .first()
    )
    if not borrower_shelf:
        ops_log.warning(
            "handoff.complete.no_shelf",
            cid=cid,
            copy_id=copy_id,
            from_user_id=previous_holder.id,
        )
        return False, "Позику вже знято — передачу не завершено."

    book_title = borrower_shelf.book.title
    book_id = borrower_shelf.book_id
    borrower_shelf.delete()
    Shelf.objects.create(
        user_id=requester.id,
        book_id=book_id,
        copy_id=copy_id,
        borrowed_from_id=owner.id,
        due_date=loan_due_date(),
        return_pending=False,
    )
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
    message_service.notify_loan_transmitted(
        owner, previous_holder, requester, book_title, exchange_request=req
    )
    try:
        queue_service.after_copy_loaned_or_transmitted(copy_id, requester.id)
    except Exception as exc:
        ops_log.exception("handoff.complete.queue_fail", exc, cid=cid, copy_id=copy_id)
    ops_log.info("handoff.complete.ok", cid=cid, **ops_log.handoff_snapshot(handoff))
    return True, None


@transaction.atomic
def confirm_handoff_give(
    handoff_id: int, acting_user: CustomUser
) -> tuple[bool, str | None]:
    """Поточний позичальник підтверджує, що фізично віддав книгу наступному."""
    cid = ops_log.new_cid()
    ops_log.info(
        "handoff.give.start",
        cid=cid,
        handoff_id=handoff_id,
        actor_id=acting_user.id,
    )
    try:
        # of=("self",) — Postgres: FOR UPDATE + LEFT JOIN на nullable FK інакше 500
        handoff = (
            LoanHandoff.objects.select_for_update(of=("self",))
            .select_related(
                "owner", "from_user", "to_user", "copy__book", "exchange_request"
            )
            .get(pk=handoff_id)
        )
    except LoanHandoff.DoesNotExist:
        ops_log.warning("handoff.give.missing", cid=cid, handoff_id=handoff_id)
        return False, "Передачу не знайдено."
    except Exception as exc:
        ops_log.exception(
            "handoff.give.lock_fail",
            exc,
            cid=cid,
            handoff_id=handoff_id,
            actor_id=acting_user.id,
        )
        return False, f"Помилка блокування передачі (cid={cid})."

    ops_log.info("handoff.give.locked", cid=cid, **ops_log.handoff_snapshot(handoff))

    if handoff.status != LoanHandoff.Status.AWAITING_GIVE:
        ops_log.warning(
            "handoff.give.bad_status",
            cid=cid,
            status=handoff.status,
            actor_id=acting_user.id,
        )
        return False, "Зараз не чекається підтвердження віддачі."
    if acting_user.id != handoff.from_user_id:
        ops_log.warning(
            "handoff.give.forbidden",
            cid=cid,
            actor_id=acting_user.id,
            from_user_id=handoff.from_user_id,
        )
        return False, "Підтвердити віддачу може лише поточний тримач книги."

    try:
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
        message_service.notify_handoff_given(handoff)
    except Exception as exc:
        ops_log.exception(
            "handoff.give.save_fail",
            exc,
            cid=cid,
            **ops_log.handoff_snapshot(handoff),
        )
        raise

    ops_log.info("handoff.give.ok", cid=cid, **ops_log.handoff_snapshot(handoff))
    return True, None


@transaction.atomic
def confirm_handoff_receive(
    handoff_id: int, acting_user: CustomUser
) -> tuple[bool, str | None]:
    """Наступний позичальник підтверджує отримання — полиця переїздить, попередній виходить з чату."""
    cid = ops_log.new_cid()
    ops_log.info(
        "handoff.receive.start",
        cid=cid,
        handoff_id=handoff_id,
        actor_id=acting_user.id,
    )
    try:
        handoff = (
            LoanHandoff.objects.select_for_update(of=("self",))
            .select_related(
                "owner", "from_user", "to_user", "copy__book", "exchange_request"
            )
            .get(pk=handoff_id)
        )
    except LoanHandoff.DoesNotExist:
        ops_log.warning("handoff.receive.missing", cid=cid, handoff_id=handoff_id)
        return False, "Передачу не знайдено."
    except Exception as exc:
        ops_log.exception(
            "handoff.receive.lock_fail",
            exc,
            cid=cid,
            handoff_id=handoff_id,
            actor_id=acting_user.id,
        )
        return False, f"Помилка блокування передачі (cid={cid})."

    if handoff.status != LoanHandoff.Status.AWAITING_RECEIVE:
        if handoff.status == LoanHandoff.Status.AWAITING_GIVE:
            ops_log.warning("handoff.receive.need_give_first", cid=cid)
            return False, "Спочатку поточний тримач має підтвердити віддачу."
        ops_log.warning(
            "handoff.receive.bad_status", cid=cid, status=handoff.status
        )
        return False, "Зараз не чекається підтвердження отримання."
    if acting_user.id != handoff.to_user_id:
        ops_log.warning(
            "handoff.receive.forbidden",
            cid=cid,
            actor_id=acting_user.id,
            to_user_id=handoff.to_user_id,
        )
        return False, "Підтвердити отримання може лише наступний позичальник."

    try:
        handoff.receiver_confirmed_at = timezone.now()
        handoff.save(update_fields=["receiver_confirmed_at"])
        ok, err = complete_loan_handoff_transfer(handoff)
        if not ok:
            ops_log.warning("handoff.receive.complete_fail", cid=cid, err=err)
        else:
            ops_log.info("handoff.receive.ok", cid=cid, handoff_id=handoff_id)
        return ok, err
    except Exception as exc:
        ops_log.exception(
            "handoff.receive.fail",
            exc,
            cid=cid,
            **ops_log.handoff_snapshot(handoff),
        )
        raise


@transaction.atomic
def cancel_loan_handoff(
    handoff_id: int, acting_user: CustomUser
) -> tuple[bool, str | None]:
    """Власник скасовує схвалену, але ще не завершену фізичну передачу."""
    cid = ops_log.new_cid()
    try:
        handoff = (
            LoanHandoff.objects.select_for_update(of=("self",))
            .select_related(
                "owner", "from_user", "to_user", "copy__book", "exchange_request"
            )
            .get(pk=handoff_id)
        )
    except LoanHandoff.DoesNotExist:
        return False, "Передачу не знайдено."
    except Exception as exc:
        ops_log.exception(
            "handoff.cancel.lock_fail", exc, cid=cid, handoff_id=handoff_id
        )
        return False, f"Помилка блокування передачі (cid={cid})."

    if handoff.status not in (
        LoanHandoff.Status.AWAITING_GIVE,
        LoanHandoff.Status.AWAITING_RECEIVE,
    ):
        return False, "Цю передачу вже завершено або скасовано."
    if acting_user.id != handoff.owner_id:
        return False, "Скасувати може лише власник примірника."

    handoff.status = LoanHandoff.Status.CANCELLED
    handoff.resolved_at = timezone.now()
    handoff.save(update_fields=["status", "resolved_at"])
    message_service.notify_handoff_cancelled(handoff)
    ops_log.info("handoff.cancel.ok", cid=cid, **ops_log.handoff_snapshot(handoff))
    return True, None


def transmit_loan_to_requester(
    req: BookExchangeRequest,
    owner: CustomUser,
    owner_shelf: Shelf,
    requester: CustomUser,
) -> tuple[bool, str | None]:
    """Legacy alias — тепер схвалення створює handoff, не миттєвий перенос."""
    return approve_loan_handoff(req, owner, owner_shelf, requester)



# Back-compat private names
_approve_loan_handoff = approve_loan_handoff
_complete_loan_handoff_transfer = complete_loan_handoff_transfer
_transmit_loan_to_requester = transmit_loan_to_requester
