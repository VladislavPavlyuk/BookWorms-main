"""
Операційний лог для позик / handoff / повернень.

Дивись у контейнері:
  docker compose -f docker-compose.qnap.yml logs -f api | grep -E 'ops\\.|handoff|HANDOFF'

Кожен виклик має correlation id (cid) — шукай той самий cid у стеку.
"""
from __future__ import annotations

import logging
import traceback
import uuid
from typing import Any

logger = logging.getLogger("mainApp.ops")


def new_cid() -> str:
    return uuid.uuid4().hex[:10]


def _fmt(event: str, cid: str | None, **fields: Any) -> str:
    parts = [f"ops.{event}"]
    if cid:
        parts.append(f"cid={cid}")
    for k, v in fields.items():
        if v is None:
            continue
        parts.append(f"{k}={v}")
    return " ".join(parts)


def info(event: str, *, cid: str | None = None, **fields: Any) -> None:
    logger.info(_fmt(event, cid, **fields))


def warning(event: str, *, cid: str | None = None, **fields: Any) -> None:
    logger.warning(_fmt(event, cid, **fields))


def error(event: str, *, cid: str | None = None, **fields: Any) -> None:
    logger.error(_fmt(event, cid, **fields))


def exception(event: str, exc: BaseException, *, cid: str | None = None, **fields: Any) -> str:
    """
    Логує exception + traceback. Повертає cid (створює, якщо не передали).
    """
    cid = cid or new_cid()
    fields = dict(fields)
    fields["exc_type"] = type(exc).__name__
    fields["exc"] = str(exc)[:500]
    logger.error(_fmt(event, cid, **fields))
    logger.error("ops.traceback cid=%s\n%s", cid, traceback.format_exc())
    return cid


def handoff_snapshot(handoff) -> dict[str, Any]:
    if handoff is None:
        return {"handoff": None}
    return {
        "handoff_id": getattr(handoff, "pk", None),
        "status": getattr(handoff, "status", None),
        "copy_id": getattr(handoff, "copy_id", None),
        "owner_id": getattr(handoff, "owner_id", None),
        "from_user_id": getattr(handoff, "from_user_id", None),
        "to_user_id": getattr(handoff, "to_user_id", None),
        "from_shelf_id": getattr(handoff, "from_shelf_id", None),
        "exchange_request_id": getattr(handoff, "exchange_request_id", None),
    }
