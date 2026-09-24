"""
Live-DB fixtures for FastAPI repository tests.

Uses Postgres from docker-compose.test.yml (or any POSTGRES_* / DATABASE_URL).
Creates thin mainApp_* tables from Core metadata (not Django migrations) so
repo queries can run without the Django app installed.
"""
from __future__ import annotations

import os
from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from fastapi_app import tables as t

# Tables the shelf repo needs (FK order for create / reverse for drop).
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

    # Own the thin schema for this test DB (do not point at production).
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


@pytest.fixture
def shelf_seed(conn: Connection) -> dict:
    """Owner shelf for one free copy. Returns ids used by tests."""
    now = datetime.now(timezone.utc)
    owner_id, borrower_id = 1, 2
    book_id, copy_id, owner_shelf_id = 10, 20, 30

    conn.execute(
        t.users.insert(),
        [
            {"id": owner_id, "username": "owner"},
            {"id": borrower_id, "username": "borrower"},
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
    return {
        "owner_id": owner_id,
        "borrower_id": borrower_id,
        "book_id": book_id,
        "copy_id": copy_id,
        "owner_shelf_id": owner_shelf_id,
        "now": now,
    }
