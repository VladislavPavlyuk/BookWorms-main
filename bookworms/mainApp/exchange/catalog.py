"""Book catalog resolve/sync from ISBN providers (SRP)."""
from __future__ import annotations

from ..error_handling import domain_guard
from ..exceptions import ExchangeInvalidState, ExchangeNotFound
from ..models import Book


def get_or_create_book_from_payload(payload: dict) -> tuple[Book, bool]:
    isbn = (payload.get("isbn") or "").strip()
    defaults = {
        "title": (payload.get("title") or "").strip()[:500],
        "authors": (payload.get("authors") or "").strip()[:500],
        "publisher": (payload.get("publisher") or "").strip()[:300],
        "publish_date": (payload.get("publish_date") or "").strip()[:64],
        "cover_url": (payload.get("cover_url") or "").strip()[:500],
        "info_url": (payload.get("info_url") or "").strip()[:500],
    }
    book, created = Book.objects.get_or_create(isbn=isbn, defaults=defaults)
    if not created:
        sync_book_from_payload(book, payload)
    return book, created


def sync_book_from_payload(book: Book, payload: dict) -> Book:
    changed_fields: list[str] = []
    mapping = (
        ("title", 500),
        ("authors", 500),
        ("publisher", 300),
        ("publish_date", 64),
        ("cover_url", 500),
        ("info_url", 500),
    )
    for field, maxlen in mapping:
        new = (payload.get(field) or "").strip()[:maxlen]
        if not new:
            continue
        old = (getattr(book, field) or "").strip()
        if not old:
            setattr(book, field, new)
            changed_fields.append(field)
    if changed_fields:
        book.save(update_fields=changed_fields)
    return book


@domain_guard("exchange.resolve_isbn")
def resolve_and_sync_book_by_isbn(raw_isbn: str) -> Book:
    from ..book_lookup import fetch_book_by_isbn, isbn_candidates, normalize_isbn

    norm = normalize_isbn(raw_isbn)
    if not norm:
        raise ExchangeInvalidState(
            "Невірний ISBN: потрібно 10 символів (останній може бути X) або 13 цифр."
        )

    candidates = isbn_candidates(norm)
    existing = Book.objects.filter(isbn__in=candidates).first()

    payload, err = fetch_book_by_isbn(norm)

    if payload:
        if existing and existing.isbn != payload.get("isbn"):
            sync_book_from_payload(existing, payload)
            return existing
        book, _ = get_or_create_book_from_payload(payload)
        return book

    if existing:
        return existing

    raise ExchangeNotFound(err or "Книгу з таким ISBN не знайдено.")
