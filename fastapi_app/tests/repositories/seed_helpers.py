"""Arrange helpers for live-DB shelf repository tests."""
from __future__ import annotations

from sqlalchemy.engine import Connection

from fastapi_app import tables as t


def lend_copy(conn: Connection, seed: dict, *, loan_shelf_id: int = 31) -> int:
    conn.execute(
        t.shelves.insert(),
        {
            "id": loan_shelf_id,
            "user_id": seed["borrower_id"],
            "book_id": seed["book_id"],
            "copy_id": seed["copy_id"],
            "borrowed_from_id": seed["owner_id"],
            "return_pending": False,
            "due_date": None,
            "added_at": seed["now"],
        },
    )
    return loan_shelf_id
