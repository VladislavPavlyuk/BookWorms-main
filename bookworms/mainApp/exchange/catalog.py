"""Book catalog resolve/sync from ISBN providers (SRP)."""
from __future__ import annotations

from ..error_handling import domain_guard
from ..exceptions import ExchangeInvalidState, ExchangeNotFound
from ..models import Book


def sync_book_from_payload(
    book: Book,
    payload: dict,
    *,
    overwrite: bool = False,
) -> Book:
    """
    Apply catalog payload onto Book.
    Default: fill empty fields only.
    overwrite=True: replace with non-empty catalog values (ISBN re-resolve / refresh).
    """
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
        if old and not overwrite:
            continue
        if new != old:
            setattr(book, field, new)
            changed_fields.append(field)
    cover_text = (payload.get("cover_text") or "").strip()
    if cover_text and (
        overwrite or not (book.cover_text or "").strip()
    ):
        if cover_text != (book.cover_text or "").strip():
            book.cover_text = cover_text
            changed_fields.append("cover_text")
    # Prefer ISBN-13 when catalog returns a different candidate for the same work.
    new_isbn = (payload.get("isbn") or "").strip()
    if (
        overwrite
        and new_isbn
        and new_isbn != (book.isbn or "").strip()
        and not Book.objects.filter(isbn=new_isbn).exclude(pk=book.pk).exists()
    ):
        book.isbn = new_isbn[:13]
        changed_fields.append("isbn")
    if changed_fields:
        book.save(update_fields=changed_fields)
    return book


def get_or_create_book_from_payload(
    payload: dict, *, overwrite: bool = False
) -> tuple[Book, bool]:
    isbn = (payload.get("isbn") or "").strip()
    defaults = {
        "title": (payload.get("title") or "").strip()[:500],
        "authors": (payload.get("authors") or "").strip()[:500],
        "publisher": (payload.get("publisher") or "").strip()[:300],
        "publish_date": (payload.get("publish_date") or "").strip()[:64],
        "cover_url": (payload.get("cover_url") or "").strip()[:500],
        "info_url": (payload.get("info_url") or "").strip()[:500],
        "cover_text": (payload.get("cover_text") or "").strip(),
    }
    book, created = Book.objects.get_or_create(isbn=isbn, defaults=defaults)
    if not created:
        sync_book_from_payload(book, payload, overwrite=overwrite)
    return book, created


@domain_guard("exchange.resolve_isbn")
def resolve_and_sync_book_by_isbn(
    raw_isbn: str,
    *,
    search_log: list | None = None,
    overwrite: bool = True,
) -> Book:
    """
    Lookup ISBN in external catalogs and upsert Book.
    overwrite=True (default): refresh bibliographic fields from the hit provider
    so re-resolving an already-known ISBN updates stale local metadata.
    """
    from ..book_lookup import fetch_book_by_isbn, isbn_candidates, normalize_isbn

    norm = normalize_isbn(raw_isbn)
    if not norm:
        raise ExchangeInvalidState(
            "Невірний ISBN: потрібно 10 символів (останній може бути X) або 13 цифр."
        )

    candidates = isbn_candidates(norm)
    existing = Book.objects.filter(isbn__in=candidates).first()

    payload, err = fetch_book_by_isbn(norm, search_log=search_log)

    if payload:
        if existing:
            sync_book_from_payload(existing, payload, overwrite=overwrite)
            return existing
        book, _ = get_or_create_book_from_payload(payload, overwrite=overwrite)
        return book

    if existing:
        if search_log is not None:
            search_log.append(
                {
                    "provider": "local",
                    "label": "Локальна база",
                    "status": "hit",
                    "detail": existing.title[:80] if existing.title else "вже в каталозі",
                }
            )
        return existing

    raise ExchangeNotFound(err or "Книгу з таким ISBN не знайдено.")


@domain_guard("exchange.refresh_isbn")
def refresh_book_metadata_from_catalog(
    book: Book,
    *,
    search_log: list | None = None,
) -> Book:
    """Force re-fetch metadata from ALL catalogs and overwrite local fields."""
    from ..book_lookup import fetch_book_by_isbn, normalize_isbn
    from ..book_photos import is_local_isbn

    raw = (book.isbn or "").strip()
    if not raw or is_local_isbn(raw):
        raise ExchangeInvalidState(
            "Локальний ISBN — немає запису в зовнішніх каталогах."
        )
    norm = normalize_isbn(raw)
    if not norm:
        raise ExchangeInvalidState("Невірний ISBN на картці книги.")

    # merge=True → keep asking Open Library / Google / LT after ISBNdb hit
    # so sparse first-provider data gets enriched from other catalogs.
    payload, err = fetch_book_by_isbn(norm, search_log=search_log, merge=True)
    if not payload:
        raise ExchangeNotFound(err or "Книгу з таким ISBN не знайдено в каталогах.")
    return sync_book_from_payload(book, payload, overwrite=True)