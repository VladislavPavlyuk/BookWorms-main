"""SQLAlchemy Core shelf queries (mirrors Django ShelfRepository)."""
from __future__ import annotations

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.engine import Connection

from .. import tables as t


def _active_loan_exists(copy_col):
    loan = t.shelves.alias("loan")
    return exists(
        select(1).where(
            and_(
                loan.c.copy_id == copy_col,
                loan.c.borrowed_from_id.is_not(None),
                loan.c.copy_id.is_not(None),
            )
        )
    )


def find_available_owned(
    conn: Connection,
    *,
    exclude_user_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Власні вільні примірники (не в активній позиці)."""
    s = t.shelves.alias("s")
    loaned = _active_loan_exists(s.c.copy_id)
    stmt = (
        select(
            s.c.id,
            s.c.user_id,
            s.c.book_id,
            s.c.copy_id,
            s.c.borrowed_from_id,
            s.c.return_pending,
            s.c.due_date,
            s.c.added_at,
            t.users.c.username,
            t.books.c.title.label("book_title"),
            t.books.c.isbn.label("book_isbn"),
            t.books.c.cover_url,
            t.books.c.authors,
        )
        .select_from(
            s.join(t.books, t.books.c.id == s.c.book_id).join(
                t.users, t.users.c.id == s.c.user_id
            )
        )
        .where(and_(s.c.borrowed_from_id.is_(None), ~loaned))
        .order_by(s.c.added_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if exclude_user_id is not None:
        stmt = stmt.where(s.c.user_id != exclude_user_id)
    return [dict(row._mapping) for row in conn.execute(stmt)]


def find_physical_presence(
    conn: Connection,
    *,
    exclude_user_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """
    Фізична присутність:
    - власний рядок без активної позики на copy;
    - або рядок позичальника.
    """
    s = t.shelves.alias("s")
    loaned = _active_loan_exists(s.c.copy_id)
    at_owner = and_(s.c.borrowed_from_id.is_(None), ~loaned)
    at_borrower = s.c.borrowed_from_id.is_not(None)
    stmt = (
        select(
            s.c.id,
            s.c.user_id,
            s.c.book_id,
            s.c.copy_id,
            s.c.borrowed_from_id,
            s.c.return_pending,
            s.c.due_date,
            s.c.added_at,
            t.users.c.username,
            t.books.c.title.label("book_title"),
            t.books.c.isbn.label("book_isbn"),
            t.books.c.cover_url,
            t.books.c.authors,
        )
        .select_from(
            s.join(t.books, t.books.c.id == s.c.book_id).join(
                t.users, t.users.c.id == s.c.user_id
            )
        )
        .where(or_(at_owner, at_borrower))
        .order_by(s.c.added_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if exclude_user_id is not None:
        stmt = stmt.where(s.c.user_id != exclude_user_id)
    return [dict(row._mapping) for row in conn.execute(stmt)]
