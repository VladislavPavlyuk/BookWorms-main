"""Book catalog resolve/sync from ISBN providers (SRP)."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from ..catalog_media import persist_catalog_cover
from ..error_handling import domain_guard
from ..exceptions import ExchangeInvalidState, ExchangeNotFound
from ..html_sanitize import sanitize_isbn_html
from ..models import Book

_HTML_PROSE_FIELDS = frozenset({"overview", "synopsis", "excerpt"})
# cover_url is owned by persist_catalog_cover (local MEDIA) — never hot-link overwrite.
_COVER_REMOTE_FIELDS = frozenset({"cover_url", "cover_url_original"})

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

    from ..catalog_media import is_remote_http_url, to_relative_media_url

    # Prefer path-only /media/... so Safari HTTPS pages are not mixed-content blocked.
    _prev_rel = to_relative_media_url((book.cover_url or "").strip())
    prev_local_cover = _prev_rel if _prev_rel is not None else ""

    for field, maxlen in _STRING_FIELDS:
        if field in _COVER_REMOTE_FIELDS:
            # Covers: only stash remote source URLs; never replace a local
            # MEDIA cover_url with a hot-link (refresh was wiping covers).
            continue
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

    # Stash remote cover source (prefer stable image over ephemeral «original»).
    remote_orig = (payload.get("cover_url_original") or "").strip()
    remote_cover = (payload.get("cover_url") or "").strip()
    for cand in (remote_cover, remote_orig):
        if is_remote_http_url(cand):
            old_o = (book.cover_url_original or "").strip()
            if (not old_o and cand) or (overwrite and cand != old_o):
                book.cover_url_original = cand[:500]
                if "cover_url_original" not in changed_fields:
                    changed_fields.append("cover_url_original")
            break

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

    # Mirror best available cover into MEDIA. On refresh failure, keep local.
    ok = persist_catalog_cover(
        book,
        force=overwrite,
        candidates=[
            (payload.get("cover_url") or "").strip(),  # stable image first
            (payload.get("cover_url_original") or "").strip(),  # may expire (ISBNdb)
        ],
        keep_local_on_fail=prev_local_cover or None,
    )
    if overwrite and not ok and prev_local_cover:
        # Defensive: sync must not leave a broken remote cover_url.
        if (book.cover_url or "").strip() != prev_local_cover:
            book.cover_url = prev_local_cover
            book.save(update_fields=["cover_url"])
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
        if field in _HTML_PROSE_FIELDS:
            val = sanitize_isbn_html(val)
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

    # Prefer original remote cover in cover_url_original; cover_url filled after mirror.
    remote_cover = (defaults.get("cover_url") or "").strip()
    if remote_cover and not (defaults.get("cover_url_original") or "").strip():
        defaults["cover_url_original"] = remote_cover[:500]

    book, created = Book.objects.get_or_create(isbn=isbn, defaults=defaults)
    if not created:
        sync_book_from_payload(book, payload, overwrite=overwrite)
    else:
        persist_catalog_cover(
            book,
            force=True,
            candidates=[
                (payload.get("cover_url_original") or "").strip(),
                remote_cover,
            ],
        )
    return book, created


@domain_guard("exchange.resolve_isbn")
def resolve_and_sync_book_by_isbn(
    raw_isbn: str,
    *,
    search_log: list | None = None,
    overwrite: bool = False,
) -> Book:
    """
    Resolve Book for display / add-copy.

    1. If the ISBN exists locally → return that Book (covers + metadata from DB).
       No external catalog calls.
    2. If missing → fetch every provider (merge=True), enrich-merge as much as
       possible, persist fields + mirror cover into MEDIA, then return the
       new local Book.

    Later re-fetch/overwrite only via refresh_book_metadata_from_catalog
    («Оновити з каталогу»).
    """
    from ..book_lookup import fetch_book_by_isbn, isbn_candidates, normalize_isbn

    norm = normalize_isbn(raw_isbn)
    if not norm:
        raise ExchangeInvalidState(
            "Невірний ISBN: потрібно 10 символів (останній може бути X) або 13 цифр."
        )

    candidates = isbn_candidates(norm)
    isbn10s = [c for c in candidates if len(c) == 10]
    existing = Book.objects.filter(isbn__in=candidates).first()
    if existing is None and isbn10s:
        existing = Book.objects.filter(isbn10__in=isbn10s).first()

    if existing:
        if search_log is not None:
            search_log.append(
                {
                    "provider": "local",
                    "label": "Локальна база",
                    "status": "hit",
                    "detail": (existing.title or "вже в каталозі")[:80],
                }
            )
        # Legacy rows may still hot-link — one-time mirror, no external catalog call.
        persist_catalog_cover(existing, force=False)
        return existing

    # No local row: maximize abroad, then store everything locally.
    payload, err = fetch_book_by_isbn(norm, search_log=search_log, merge=True)
    if payload:
        book, _ = get_or_create_book_from_payload(payload, overwrite=overwrite)
        return book

    raise ExchangeNotFound(err or "Книгу з таким ISBN не знайдено.")


@domain_guard("exchange.refresh_isbn")
def refresh_book_metadata_from_catalog(
    book: Book,
    *,
    search_log: list | None = None,
) -> Book:
    """
    «Оновити з каталогу»: query every configured provider, merge the richest
    bibliographic payload + best cover URL, overwrite local Book fields, and
    re-mirror the cover into MEDIA.
    """
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

    # merge=True → every provider + enrich merge (longer prose, better covers,
    # union subjects / other_isbns / dewey).
    payload, err = fetch_book_by_isbn(norm, search_log=search_log, merge=True)
    if not payload:
        raise ExchangeNotFound(err or "Книгу з таким ISBN не знайдено в каталогах.")
    return sync_book_from_payload(book, payload, overwrite=True)
