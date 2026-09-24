"""Boundary exception handling — DRF handler + domain_guard + web helper."""
from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_handler

from . import ops_log
from .exceptions import ExchangeError

F = TypeVar("F", bound=Callable[..., Any])


def domain_guard(event: str) -> Callable[[F], F]:
    """
    Wrap a public domain entrypoint.
    ExchangeError passes through; anything else is logged once and re-raised
    as ExchangeError(code=unexpected, http_status=500).
    """

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            try:
                return fn(*args, **kwargs)
            except ExchangeError:
                raise
            except Exception as exc:
                cid = ops_log.exception(event, exc)
                raise ExchangeError(
                    f"Внутрішня помилка (cid={cid}).",
                    code="unexpected",
                    http_status=500,
                    cid=cid,
                ) from exc

        return wrapper  # type: ignore[return-value]

    return decorator


def drf_exception_handler(exc, context):
    if isinstance(exc, ExchangeError):
        body: dict[str, Any] = {
            "detail": exc.message,
            "code": exc.code,
        }
        if exc.cid:
            body["cid"] = exc.cid
        return Response(body, status=exc.http_status)
    return drf_default_handler(exc, context)


def web_exchange(
    request,
    fn: Callable[..., Any],
    *args: Any,
    success: str | None = None,
    **kwargs: Any,
) -> tuple[bool, Any]:
    """
    Run an exchange use-case from a Django view.
    Returns (True, result) on success; on ExchangeError sets messages.error
    and returns (False, None).
    """
    from django.contrib import messages

    try:
        result = fn(*args, **kwargs)
    except ExchangeError as exc:
        msg = exc.message
        if exc.cid and exc.http_status >= 500:
            msg = f"{msg}"
        messages.error(request, msg)
        return False, None
    if success:
        messages.success(request, success)
    return True, result
