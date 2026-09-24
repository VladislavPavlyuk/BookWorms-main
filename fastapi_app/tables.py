"""
SQLAlchemy Core tables mapped to existing Django tables (no ORM models).

Django app label ``mainApp`` → table prefix ``mainApp_``.
Schema ownership: Django migrations. Do not drop/alter these via Alembic.
"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)

metadata = MetaData()

# Django CustomUser → auth-style table name for custom user model
users = Table(
    "mainApp_customuser",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("username", String(150), nullable=False),
)

books = Table(
    "mainApp_book",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("isbn", String(13), nullable=False),
    Column("title", String(500), nullable=False),
    Column("authors", String(500), nullable=False, server_default=""),
    Column("cover_url", String(500), nullable=False, server_default=""),
)

book_copies = Table(
    "mainApp_bookcopy",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("book_id", BigInteger, ForeignKey("mainApp_book.id"), nullable=False),
    Column("owner_id", BigInteger, ForeignKey("mainApp_customuser.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

shelves = Table(
    "mainApp_shelf",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("user_id", BigInteger, ForeignKey("mainApp_customuser.id"), nullable=False),
    Column("book_id", BigInteger, ForeignKey("mainApp_book.id"), nullable=False),
    Column("copy_id", BigInteger, ForeignKey("mainApp_bookcopy.id"), nullable=False),
    Column("borrowed_from_id", BigInteger, ForeignKey("mainApp_customuser.id"), nullable=True),
    Column("return_pending", Boolean, nullable=False, server_default="false"),
    Column("due_date", Date, nullable=True),
    Column("added_at", DateTime(timezone=True), nullable=False),
)

# FastAPI-owned marker (Alembic only)
fastapi_meta = Table(
    "fastapi_schema_meta",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("note", Text, nullable=False),
)
