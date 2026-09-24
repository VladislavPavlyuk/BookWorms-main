"""Shelf query objects for browse / physical presence (SRP)."""
from __future__ import annotations

from django.db.models import Exists, OuterRef, QuerySet
from django.utils import timezone

from ..models import Shelf


def available_owned_shelves_qs(exclude_user_id: int | None = None) -> QuerySet[Shelf]:
    """Вільні власні примірники (для обміну / миттєвої позики)."""
    active_loan = Shelf.objects.filter(
        copy_id=OuterRef("copy_id"),
        borrowed_from__isnull=False,
    ).exclude(copy_id__isnull=True)
    qs = Shelf.objects.filter(borrowed_from__isnull=True).exclude(Exists(active_loan))
    if exclude_user_id is not None:
        qs = qs.exclude(user_id=exclude_user_id)
    return qs


def physical_presence_shelves_qs(exclude_user_id: int | None = None) -> QuerySet[Shelf]:
    """
    Де примірник фізично зараз:
    - власний рядок, якщо не в позиці;
    - рядок позичальника, якщо видано.
    """
    active_loan = Shelf.objects.filter(
        copy_id=OuterRef("copy_id"),
        borrowed_from__isnull=False,
    ).exclude(copy_id__isnull=True)
    at_owner = Shelf.objects.filter(borrowed_from__isnull=True).exclude(Exists(active_loan))
    at_borrower = Shelf.objects.filter(borrowed_from__isnull=False)
    qs = (at_owner | at_borrower).distinct()
    if exclude_user_id is not None:
        qs = qs.exclude(user_id=exclude_user_id)
    return qs


def attach_loan_info(shelves: list[Shelf]) -> list[Shelf]:
    """Проставляє is_lent_out + loan_row на власні рядки."""
    copy_ids = [s.copy_id for s in shelves if s.copy_id and not s.borrowed_from_id]
    loan_by_copy: dict[int, Shelf] = {}
    if copy_ids:
        for row in (
            Shelf.objects.filter(copy_id__in=copy_ids, borrowed_from__isnull=False)
            .select_related("user", "book", "copy", "borrowed_from")
        ):
            loan_by_copy[row.copy_id] = row
    today = timezone.now().date()
    for s in shelves:
        if s.borrowed_from_id:
            s.is_lent_out = False
            s.loan_row = None
            s.request_shelf_id = None
            if s.due_date:
                s.is_overdue = s.due_date < today
                s.days_left = (s.due_date - today).days
            else:
                s.is_overdue = False
                s.days_left = None
            continue
        loan = loan_by_copy.get(s.copy_id) if s.copy_id else None
        s.loan_row = loan
        s.is_lent_out = loan is not None
        s.request_shelf_id = s.pk
        if loan and loan.due_date:
            s._loan_due = loan.due_date
            s._loan_overdue = loan.due_date < today
            s._loan_days_left = (loan.due_date - today).days
        else:
            s._loan_due = None
            s._loan_overdue = False
            s._loan_days_left = None
    return shelves


def attach_request_targets(shelves: list[Shelf]) -> list[Shelf]:
    """Для позики — id полиці власника; для вільного — сам рядок."""
    need = [s.copy_id for s in shelves if s.borrowed_from_id and s.copy_id]
    owner_by_copy: dict[int, int] = {}
    if need:
        for row in Shelf.objects.filter(
            copy_id__in=need, borrowed_from__isnull=True
        ).only("id", "copy_id"):
            if row.copy_id:
                owner_by_copy[row.copy_id] = row.id
    for s in shelves:
        if s.borrowed_from_id:
            s.request_shelf_id = owner_by_copy.get(s.copy_id)
        else:
            s.request_shelf_id = s.pk
    return shelves


def filter_physically_present(shelves: list[Shelf]) -> list[Shelf]:
    shelves = attach_loan_info(shelves)
    return [s for s in shelves if not getattr(s, "is_lent_out", False)]


def browsable_owned_shelves_qs(exclude_user_id: int | None = None) -> QuerySet[Shelf]:
    return physical_presence_shelves_qs(exclude_user_id=exclude_user_id)


def group_shelves_by_book(shelves) -> list[dict]:
    """Один ISBN → book + owners + shelf-рядки."""
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
        legal = s.borrowed_from if s.borrowed_from_id else s.user
        if legal.id not in g["_owner_ids"]:
            g["_owner_ids"].add(legal.id)
            g["owners"].append(legal)
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
