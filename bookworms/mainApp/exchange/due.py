"""Loan due-date policy (SRP)."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from django.conf import settings
from django.utils import timezone


def default_loan_days() -> int:
    return int(getattr(settings, "DEFAULT_LOAN_DAYS", 14))


def loan_due_date():
    return timezone.now().date() + timedelta(days=default_loan_days())


def parse_due_date(raw) -> date | None:
    """Parse YYYY-MM-DD / date / datetime → date, or None if empty."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    s = str(raw).strip()
    if not s:
        return None
    return date.fromisoformat(s[:10])


def validate_proposed_due_date(d: date) -> date:
    """Ensure due date is today..today+365. Raises ValueError."""
    today = timezone.now().date()
    if d < today:
        raise ValueError("Дата повернення не може бути в минулому.")
    if d > today + timedelta(days=365):
        raise ValueError("Термін позики — максимум 365 днів від сьогодні.")
    return d


def resolve_loan_due_date(
    *,
    proposed: date | None = None,
    override: date | None = None,
) -> date:
    """Owner override > requester proposal > default loan window.

    Stale proposals (past) fall back to the default window so accept still works.
    """
    if override is not None:
        return validate_proposed_due_date(override)
    if proposed is not None:
        today = timezone.now().date()
        if proposed < today:
            return loan_due_date()
        if proposed > today + timedelta(days=365):
            return today + timedelta(days=365)
        return proposed
    return loan_due_date()


# Back-compat alias used inside domain
_loan_due_date = loan_due_date
