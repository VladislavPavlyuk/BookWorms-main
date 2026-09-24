"""Loan due-date policy (SRP)."""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone


def loan_due_date():
    days = int(getattr(settings, "DEFAULT_LOAN_DAYS", 14))
    return timezone.now().date() + timedelta(days=days)


# Back-compat alias used inside domain
_loan_due_date = loan_due_date
