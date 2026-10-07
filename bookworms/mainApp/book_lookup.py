"""
Єдиний ISBN → метадані книги.

Провайдери (порядок через BOOK_METADATA_PROVIDERS, CSV):
  openlibrary  — повна бібліографія
  isbndb       — ISBNdb REST v2 (потрібен ISBNDB_API_KEY)
  googlebooks  — Google Books volumes (ключ опційний)
  librarything — Common Knowledge getwork (LIBRARYTHING_API_KEY;
                 часто Cloudflare 403 з датацентрів/NAS)

Приклад .env:
  ISBNDB_API_KEY=…
  LIBRARYTHING_API_KEY=…
  GOOGLE_BOOKS_API_KEY=
  BOOK_METADATA_PROVIDERS=openlibrary,isbndb,googlebooks,librarything
"""
from __future__ import annotations

import logging
import os
from typing import Any

from . import googlebooks as gb
from . import isbndb as idb
from . import librarything as lt
from . import openlibrary as ol

# реекспорт для зручності
normalize_isbn = ol.normalize_isbn
isbn_candidates = ol.isbn_candidates

logger = logging.getLogger("mainApp.book_lookup")

PROVIDER_LABELS: dict[str, str] = {
    "isbndb": "ISBNdb",
    "isbn_db": "ISBNdb",
    "idb": "ISBNdb",
    "openlibrary": "Open Library",
    "googlebooks": "Google Books",
    "google": "Google Books",
    "gb": "Google Books",
    "librarything": "LibraryThing",
    "lt": "LibraryThing",
}


def _providers() -> list[str]:
    raw = (
        os.environ.get("BOOK_METADATA_PROVIDERS")
        or "isbndb,openlibrary,googlebooks,librarything"
    ).strip()
    out: list[str] = []
    for part in raw.split(","):
        name = part.strip().lower()
        if name and name not in out:
            out.append(name)
    return out or ["openlibrary"]


def provider_labels(names: list[str] | None = None) -> list[dict[str, str]]:
    """UI-friendly provider list in lookup order."""
    return [
        {"id": n, "label": PROVIDER_LABELS.get(n, n)}
        for n in (names if names is not None else _providers())
    ]


_MERGE_FIELDS = (
    "title",
    "title_long",
    "authors",
    "publisher",
    "publish_date",
    "binding",
    "language",
    "edition",
    "dimensions",
    "overview",
    "synopsis",
    "excerpt",
    "cover_url",
    "cover_url_original",
    "info_url",
    "isbn",
    "isbn10",
    "catalog_source",
)

_MERGE_SCALAR = ("pages", "msrp")
_MERGE_JSON = ("subjects", "other_isbns", "dewey_decimal", "dimensions_data")


def _log_step(
    search_log: list[dict[str, Any]] | None,
    provider: str,
    status: str,
    detail: str = "",
) -> None:
    if search_log is None:
        return
    search_log.append(
        {
            "provider": provider,
            "label": PROVIDER_LABELS.get(provider, provider),
            "status": status,  # searching | hit | miss | skip
            "detail": (detail or "")[:300],
        }
    )


def _payload_incomplete(data: dict[str, Any]) -> bool:
    """True when first-hit metadata is sparse — worth asking other catalogs."""
    if not (data.get("title") or "").strip():
        return True
    if not (data.get("authors") or "").strip():
        return True
    if not (data.get("cover_url") or "").strip():
        return True
    return False


def _merge_payload(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Fill empty bibliographic fields from another provider hit."""
    out = dict(base)
    sources = list(out.get("_sources") or [])
    src = (incoming.get("source") or incoming.get("catalog_source") or "").strip()
    if src and src not in sources:
        sources.append(src)
    for key in _MERGE_FIELDS:
        raw = incoming.get(key)
        if raw is None:
            continue
        new = str(raw).strip()
        if not new:
            continue
        old = str(out.get(key) or "").strip()
        if not old:
            out[key] = incoming[key]
            continue
        # Prefer a longer, more descriptive title from a secondary catalog.
        if key == "title" and len(new) > len(old) + 8:
            out[key] = incoming[key]
        # Prefer https cover if current is missing scheme junk.
        if key == "cover_url" and new.startswith("https://") and not old.startswith("https://"):
            out[key] = incoming[key]
    for key in _MERGE_SCALAR:
        if out.get(key) in (None, "") and incoming.get(key) not in (None, ""):
            out[key] = incoming[key]
    for key in _MERGE_JSON:
        old = out.get(key)
        empty = old in (None, [], {})
        new = incoming.get(key)
        if empty and new not in (None, [], {}):
            out[key] = new
    if sources:
        out["_sources"] = sources
        out["source"] = "+".join(sources)
        out["catalog_source"] = out["source"]
    return out


def fetch_book_by_isbn(
    isbn: str,
    *,
    search_log: list[dict[str, Any]] | None = None,
    merge: bool = False,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Перебирає провайдерів по порядку.

    merge=False (default add): stop on first hit, but if that hit is incomplete
    (no authors/cover) keep asking other catalogs to fill gaps.
    merge=True (metadata refresh): always query every provider and merge fields.

    Optional ``search_log`` collects per-provider steps for UI messaging.
    """
    providers = _providers()
    errors: list[str] = []
    merged: dict[str, Any] | None = None
    logger.info(
        "isbn_lookup.start isbn=%s providers=%s isbndb_configured=%s merge=%s",
        isbn,
        providers,
        idb.configured(),
        merge,
    )
    _log_step(search_log, "lookup", "searching", f"ISBN {isbn}")
    for name in providers:
        label = PROVIDER_LABELS.get(name, name)
        _log_step(search_log, name, "searching", f"Запит до {label}…")
        if name == "openlibrary":
            data, err = ol.fetch_book_by_isbn(isbn)
        elif name in ("isbndb", "isbn_db", "idb"):
            if not idb.configured():
                errors.append("ISBNdb: немає ISBNDB_API_KEY")
                _log_step(search_log, name, "skip", "немає ISBNDB_API_KEY")
                logger.warning("isbn_lookup.skip provider=isbndb reason=no_key")
                continue
            data, err = idb.fetch_book_by_isbn(isbn)
        elif name in ("googlebooks", "google", "gb"):
            data, err = gb.fetch_book_by_isbn(isbn)
        elif name in ("librarything", "lt"):
            if not lt.configured():
                errors.append("LibraryThing: немає LIBRARYTHING_API_KEY")
                _log_step(search_log, name, "skip", "немає LIBRARYTHING_API_KEY")
                logger.warning("isbn_lookup.skip provider=librarything reason=no_key")
                continue
            data, err = lt.fetch_book_by_isbn(isbn)
        else:
            errors.append(f"невідомий провайдер «{name}»")
            _log_step(search_log, name, "skip", "невідомий провайдер")
            continue

        if data:
            data.setdefault("source", name)
            title = (data.get("title") or "")[:80]
            _log_step(search_log, name, "hit", title or "знайдено")
            logger.info(
                "isbn_lookup.hit isbn=%s provider=%s title=%s",
                isbn,
                name,
                title,
            )
            # якщо провайдер дав книгу без обкладинки — підставити LT cover URL
            if (
                not (data.get("cover_url") or "").strip()
                and lt.configured()
                and data.get("isbn")
            ):
                data["cover_url"] = lt.cover_url_for_isbn(data["isbn"], "medium")
            if merged is None:
                merged = dict(data)
                merged["_sources"] = [name]
            else:
                before_cover = (merged.get("cover_url") or "").strip()
                before_authors = (merged.get("authors") or "").strip()
                merged = _merge_payload(merged, data)
                filled = []
                if not before_cover and (merged.get("cover_url") or "").strip():
                    filled.append("cover")
                if not before_authors and (merged.get("authors") or "").strip():
                    filled.append("authors")
                if filled:
                    # amend last hit detail so UI shows enrichment
                    if search_log:
                        search_log[-1]["detail"] = (
                            f"{title or 'знайдено'} (+{', '.join(filled)})"
                        )
            # Fast path: complete first hit and not forcing full merge.
            if not merge and merged is not None and not _payload_incomplete(merged):
                merged.pop("_sources", None)
                return merged, None
            continue
        if err:
            errors.append(f"{name}: {err}" if name not in err else err)
            _log_step(search_log, name, "miss", err)
            logger.warning("isbn_lookup.miss isbn=%s provider=%s err=%s", isbn, name, err)
        else:
            _log_step(search_log, name, "miss", "не знайдено")

    if merged:
        sources = merged.pop("_sources", None) or []
        if sources:
            merged["source"] = "+".join(sources) if len(sources) > 1 else sources[0]
        logger.info(
            "isbn_lookup.merged isbn=%s sources=%s title=%s",
            isbn,
            sources,
            (merged.get("title") or "")[:80],
        )
        return merged, None

    if not errors:
        return None, "Книгу з таким ISBN не знайдено."

    uniq: list[str] = []
    for e in errors:
        if e not in uniq:
            uniq.append(e)

    catalog_miss = any("не знайдено" in e.lower() for e in uniq)
    infra = any(
        any(
            tok in e
            for tok in (
                "Cloudflare",
                "HTTP 403",
                "HTTP 429",
                "недоступна",
                "немає ISBNDB_API_KEY",
            )
        )
        for e in uniq
    )
    logger.warning(
        "isbn_lookup.fail isbn=%s providers=%s errors=%s",
        isbn,
        providers,
        uniq,
    )
    if catalog_miss and infra:
        return None, (
            "Книгу з таким ISBN не знайдено в доступних каталогах. "
            "Перевірте ISBNDB_API_KEY / GOOGLE_BOOKS_API_KEY у кореневому .env "
            "(Docker mounts ./.env) або додайте книгу вручну. "
            f"Деталі: {' | '.join(uniq[:4])}"
        )
    return None, " | ".join(uniq)


def metadata_providers_ping() -> dict[str, Any]:
    """Агрегат для deep health."""
    payload: dict[str, Any] = {
        "book_metadata_providers": _providers(),
        "book_metadata_provider_labels": provider_labels(),
    }
    payload.update(ol.openlibrary_ping())
    payload.update(idb.isbndb_ping())
    payload.update(gb.googlebooks_ping())
    payload.update(lt.librarything_ping())
    return payload
