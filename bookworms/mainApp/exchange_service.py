"""
Backward-compatible facade for exchange domain logic.

Prefer ``from mainApp.exchange import …`` (or ``from .exchange import …``).
This module re-exports the same public API as before the SOLID split.
"""
from .exchange import *  # noqa: F403
from .exchange import (  # noqa: F401 — explicit for star + private aliases
    _approve_loan_handoff,
    _loan_due_date,
    _transmit_loan_to_requester,
)
