"""
Live-DB fixtures for FastAPI repository / auth tests.

Uses Postgres from docker-compose.test.yml (or any POSTGRES_* / DATABASE_URL).
Creates thin mainApp_* tables from Core metadata (not Django migrations).
"""
from __future__ import annotations

import os
from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from fastapi_app import tables as t
from fastapi_app.auth.passwords import hash_password

# Tables the shelf/auth repos need (FK order for create / reverse for drop).
_SHELF_TABLES = (t.users, t.books, t.book_copies, t.shelves)


def _sqlalchemy_url() -> str:
    if url := os.environ.get("DATABASE_URL"):
        return url
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    port = os.environ.get("POSTGRES_PORT", "5433")
    db = os.environ.get("POSTGRES_DB", "bookworms_test")
    user = os.environ.get("POSTGRES_USER", "bookworms")
    password = os.environ.get("POSTGRES_PASSWORD", "bookworms")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    eng = create_engine(_sqlalchemy_url(), pool_pre_ping=True)
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"live DB unreachable ({_sqlalchemy_url()}): {exc}")

    for table in reversed(_SHELF_TABLES):
        table.drop(eng, checkfirst=True)
    t.metadata.create_all(eng, tables=list(_SHELF_TABLES))
    yield eng
    eng.dispose()


@pytest.fixture
def conn(engine: Engine) -> Generator[Connection, None, None]:
    with engine.begin() as connection:
        for table in reversed(_SHELF_TABLES):
            connection.execute(table.delete())
        yield connection


def _user_row(
    *,
    user_id: int,
    username: str,
    password: str = "x",
    is_active: bool = True,
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": user_id,
        "password": hash_password(password),
        "last_login": None,
        "is_superuser": False,
        "username": username,
        "first_name": "",
        "last_name": "",
        "email": f"{username}@example.com",
        "is_staff": False,
        "is_active": is_active,
        "date_joined": now,
        "biography": "",
        "email_confirmed": is_active,
    }


@pytest.fixture
def shelf_seed(conn: Connection) -> dict:
    """Owner shelf for one free copy. Returns ids used by tests."""
    now = datetime.now(timezone.utc)
    owner_id, borrower_id = 1, 2
    book_id, copy_id, owner_shelf_id = 10, 20, 30

    conn.execute(
        t.users.insert(),
        [
            _user_row(user_id=owner_id, username="owner", password="owner-pass"),
            _user_row(user_id=borrower_id, username="borrower", password="borrower-pass"),
        ],
    )
    conn.execute(
        t.books.insert(),
        {
            "id": book_id,
            "isbn": "9780000000001",
            "title": "Test Book",
            "authors": "",
            "cover_url": "",
        },
    )
    conn.execute(
        t.book_copies.insert(),
        {
            "id": copy_id,
            "book_id": book_id,
            "owner_id": owner_id,
            "created_at": now,
        },
    )
    conn.execute(
        t.shelves.insert(),
        {
            "id": owner_shelf_id,
            "user_id": owner_id,
            "book_id": book_id,
            "copy_id": copy_id,
            "borrowed_from_id": None,
            "return_pending": False,
            "due_date": None,
            "added_at": now,
        },
    )
    # Explicit PKs leave SERIAL/IDENTITY behind → register() UniqueViolation on id.
    _sync_pk_sequences(conn)
    return {
        "owner_id": owner_id,
        "borrower_id": borrower_id,
        "book_id": book_id,
        "copy_id": copy_id,
        "owner_shelf_id": owner_shelf_id,
        "now": now,
        "owner_password": "owner-pass",
    }


def _sync_pk_sequences(conn: Connection) -> None:
    """Best-effort: advance IDENTITY/SERIAL past MAX(id). create_user also uses MAX+1."""
    for table_name in (
        "mainApp_customuser",
        "mainApp_book",
        "mainApp_bookcopy",
        "mainApp_shelf",
    ):
        conn.execute(
            text(
                f"""
                SELECT CASE
                  WHEN pg_get_serial_sequence('"{table_name}"', 'id') IS NULL THEN NULL
                  ELSE setval(
                    pg_get_serial_sequence('"{table_name}"', 'id'),
                    (SELECT COALESCE(MAX(id), 1) FROM "{table_name}"),
                    true
                  )
                END
                """
            )
        )
