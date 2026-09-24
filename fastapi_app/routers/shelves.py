from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import Connection

from ..db import get_connection
from ..repositories import shelf as shelf_repo
from ..schemas import ShelfListResponse, ShelfRow

router = APIRouter(prefix="/shelves", tags=["shelves"])


@router.get("/available-owned", response_model=ShelfListResponse)
def available_owned(
    exclude_user_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    conn: Connection = Depends(get_connection),
):
    rows = shelf_repo.find_available_owned(
        conn,
        exclude_user_id=exclude_user_id,
        limit=limit,
        offset=offset,
    )
    items = [ShelfRow.model_validate(r) for r in rows]
    return ShelfListResponse(count=len(items), items=items)


@router.get("/physical-presence", response_model=ShelfListResponse)
def physical_presence(
    exclude_user_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    conn: Connection = Depends(get_connection),
):
    rows = shelf_repo.find_physical_presence(
        conn,
        exclude_user_id=exclude_user_id,
        limit=limit,
        offset=offset,
    )
    items = [ShelfRow.model_validate(r) for r in rows]
    return ShelfListResponse(count=len(items), items=items)
