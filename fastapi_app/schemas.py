from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


class BookBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    isbn: str
    title: str
    authors: str
    cover_url: str


class ShelfRow(BaseModel):
    """One physical-presence / available-owned shelf row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    book_id: int
    copy_id: int
    borrowed_from_id: int | None
    return_pending: bool
    due_date: date | None
    added_at: datetime
    username: str | None = None
    book_title: str | None = None
    book_isbn: str | None = None
    cover_url: str | None = None
    authors: str | None = None


class ShelfListResponse(BaseModel):
    count: int
    items: list[ShelfRow]
