"""Журнал подій примірника (BookCopy)."""
from __future__ import annotations

from .models import BookCopy, BookExchangeRequest, CopyEvent, CustomUser


def log_copy_event(
    copy: BookCopy | int | None,
    code: str,
    *,
    actor: CustomUser | None = None,
    holder: CustomUser | None = None,
    legal_owner: CustomUser | None = None,
    previous_holder: CustomUser | None = None,
    previous_owner: CustomUser | None = None,
    counterparty: CustomUser | None = None,
    exchange_request: BookExchangeRequest | None = None,
) -> CopyEvent | None:
    if copy is None:
        return None
    copy_id = copy.pk if isinstance(copy, BookCopy) else int(copy)
    if not copy_id:
        return None
    return CopyEvent.objects.create(
        copy_id=copy_id,
        code=code,
        actor=actor,
        holder=holder,
        legal_owner=legal_owner,
        previous_holder=previous_holder,
        previous_owner=previous_owner,
        counterparty=counterparty,
        exchange_request=exchange_request,
    )
