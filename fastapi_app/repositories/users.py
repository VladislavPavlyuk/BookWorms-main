"""User lookups / inserts against mainApp_customuser (Django-owned)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from .. import tables as t


def get_by_username(conn: Connection, username: str) -> dict | None:
    stmt = select(
        t.users.c.id,
        t.users.c.username,
        t.users.c.password,
        t.users.c.email,
        t.users.c.is_active,
        t.users.c.email_confirmed,
    ).where(t.users.c.username == username)
    row = conn.execute(stmt).mappings().first()
    return dict(row) if row else None


def get_by_id(conn: Connection, user_id: int) -> dict | None:
    stmt = select(
        t.users.c.id,
        t.users.c.username,
        t.users.c.password,
        t.users.c.email,
        t.users.c.is_active,
        t.users.c.email_confirmed,
    ).where(t.users.c.id == user_id)
    row = conn.execute(stmt).mappings().first()
    return dict(row) if row else None


def username_exists(conn: Connection, username: str) -> bool:
    stmt = select(t.users.c.id).where(t.users.c.username == username).limit(1)
    return conn.execute(stmt).first() is not None


def _next_user_id(conn: Connection) -> int:
    """Avoid SERIAL lag after tests/tools insert explicit PKs."""
    return int(
        conn.execute(select(func.coalesce(func.max(t.users.c.id), 0) + 1)).scalar_one()
    )


def create_user(
    conn: Connection,
    *,
    username: str,
    email: str,
    password_hash: str,
    biography: str = "",
    is_active: bool = True,
    email_confirmed: bool = True,
) -> dict:
    now = datetime.now(timezone.utc)
    user_id = _next_user_id(conn)
    stmt = (
        t.users.insert()
        .values(
            id=user_id,
            password=password_hash,
            last_login=None,
            is_superuser=False,
            username=username,
            first_name="",
            last_name="",
            email=email,
            is_staff=False,
            is_active=is_active,
            date_joined=now,
            biography=biography or "",
            email_confirmed=email_confirmed,
        )
        .returning(
            t.users.c.id,
            t.users.c.username,
            t.users.c.email,
            t.users.c.is_active,
            t.users.c.email_confirmed,
        )
    )
    row = conn.execute(stmt).mappings().one()
    return dict(row)
