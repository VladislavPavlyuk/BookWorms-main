"""Book catalog resolve/sync from ISBN providers (SRP)."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from ..error_handling import domain_guard
from ..exceptions import ExchangeInvalidState, ExchangeNotFound
from ..html_sanitize import sanitize_isbn_html
from ..models import Book

_HTML_PROSE_FIELDS = frozenset({"overview", "synopsis", "excerpt"})

# CharField / URLField / TextField keys → max length (None = TextField)
_STRING_FIELDS: tuple[tuple[str, int | None], ...] = (
    ("title", 500),
    ("title_long", 500),
    ("authors", 500),
    ("publisher", 300),
    ("publish_date", 64),
    ("binding", 64),
    ("language", 32),
    ("edition", 64),
    ("dimensions", 200),
    ("overview", None),
    ("synopsis", None),
    ("excerpt", None),
    ("cover_url", 500),
    ("cover_url_original", 500),
    ("info_url", 500),
    ("cover_text", None),
    ("catalog_source", 64),
    ("isbn10", 10),
)

_JSON_FIELDS = ("subjects", "other_isbns", "dewey_decimal", "dimensions_data")


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

    for field, maxlen in _STRING_FIELDS:
        if field not in payload and field == "catalog_source":
            # map legacy `source` key from providers
            raw = payload.get("source")
        else:
            raw = payload.get(field)
        if raw is None:
            continue
        new = str(raw).strip()
        if field in _HTML_PROSE_FIELDS:
            new = sanitize_isbn_html(new)
        if maxlen is not None:
            new = new[:maxlen]
        if not new:
            continue
        old = (getattr(book, field) or "").strip()
        if old and not overwrite:
            continue
        if new != old:
            setattr(book, field, new)
            changed_fields.append(field)

    # pages
    if "pages" in payload and payload.get("pages") is not None:
        try:
            pages = int(payload["pages"])
        except (TypeError, ValueError):
            pages = None
        if pages is not None and pages >= 0:
            old_p = book.pages
            if old_p is None or overwrite:
                if pages != old_p:
                    book.pages = pages
                    changed_fields.append("pages")

    # msrp
    if "msrp" in payload and payload.get("msrp") is not None:
        try:
            msrp = Decimal(str(payload["msrp"]))
        except (InvalidOperation, TypeError, ValueError):
            msrp = None
        if msrp is not None:
            old_m = book.msrp
            if old_m is None or overwrite:
                if old_m != msrp:
                    book.msrp = msrp
                    changed_fields.append("msrp")

    for field in _JSON_FIELDS:
        if field not in payload:
            continue
        new_val = payload.get(field)
        if new_val is None:
            continue
        if isinstance(new_val, list) and not new_val:
            continue
        if isinstance(new_val, dict) and not new_val:
            continue
        old_val = getattr(book, field, None)
        empty_old = old_val in (None, [], {}, "")
        if not empty_old and not overwrite:
            continue
        if new_val != old_val:
            setattr(book, field, new_val)
            changed_fields.append(field)

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
        # unique + stable order
        uniq = list(dict.fromkeys(changed_fields))
        book.save(update_fields=uniq)
    return book


def get_or_create_book_from_payload(
    payload: dict, *, overwrite: bool = False
) -> tuple[Book, bool]:
    isbn = (payload.get("isbn") or "").strip()
    defaults: dict[str, Any] = {
        "title": (payload.get("title") or "").strip()[:500] or "Книга",
    }
    for field, maxlen in _STRING_FIELDS:
        if field == "title":
            continue
        raw = payload.get(field)
        if field == "catalog_source" and raw is None:
            raw = payload.get("source")
        if raw is None:
            continue
        val = str(raw).strip()
        if maxlen is not None:
            val = val[:maxlen]
        if val:
            defaults[field] = val
    if payload.get("pages") is not None:
        try:
            defaults["pages"] = int(payload["pages"])
        except (TypeError, ValueError):
            pass
    if payload.get("msrp") is not None:
        try:
            defaults["msrp"] = Decimal(str(payload["msrp"]))
        except (InvalidOperation, TypeError, ValueError):
            pass
    for field in _JSON_FIELDS:
        if payload.get(field) not in (None, [], {}):
            defaults[field] = payload[field]

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
