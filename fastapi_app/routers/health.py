from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from ..db import get_engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    db_ok = False
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "runtime": "fastapi",
    }
