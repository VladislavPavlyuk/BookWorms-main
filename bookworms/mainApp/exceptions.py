"""Central application / domain exceptions (single hub)."""
from __future__ import annotations


class AppError(Exception):
    """Base for expected, user-facing failures."""

    code: str = "app_error"
    http_status: int = 400

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        http_status: int | None = None,
        cid: str | None = None,
    ):
        super().__init__(message)
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.cid = cid

    @property
    def message(self) -> str:
        return str(self)


class ExchangeError(AppError):
    """Exchange-domain root."""

    code = "exchange_error"
    http_status = 400


class ExchangeNotFound(ExchangeError):
    code = "not_found"
    http_status = 404


class ExchangeForbidden(ExchangeError):
    code = "forbidden"
    http_status = 403


class ExchangeConflict(ExchangeError):
    code = "conflict"
    http_status = 409


class ExchangeInvalidState(ExchangeError):
    code = "invalid_state"
    http_status = 409
