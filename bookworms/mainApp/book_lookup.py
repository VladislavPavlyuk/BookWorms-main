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

import os
from typing import Any

from . import googlebooks as gb
from . import isbndb as idb
from . import librarything as lt
from . import openlibrary as ol

# реекспорт для зручності
normalize_isbn = ol.normalize_isbn
isbn_candidates = ol.isbn_candidates


def _providers() -> list[str]:
    raw = (
        os.environ.get("BOOK_METADATA_PROVIDERS")
        or "openlibrary,isbndb,googlebooks,librarything"
    ).strip()
    out: list[str] = []
    for part in raw.split(","):
        name = part.strip().lower()
        if name and name not in out:
            out.append(name)
    return out or ["openlibrary"]


def fetch_book_by_isbn(isbn: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    Перебирає провайдерів по порядку.
    Повертає перший успішний payload або зібрану помилку.
    """
    errors: list[str] = []
    for name in _providers():
        if name == "openlibrary":
            data, err = ol.fetch_book_by_isbn(isbn)
        elif name in ("isbndb", "isbn_db", "idb"):
            if not idb.configured():
                errors.append("ISBNdb: немає ISBNDB_API_KEY")
                continue
            data, err = idb.fetch_book_by_isbn(isbn)
        elif name in ("googlebooks", "google", "gb"):
            data, err = gb.fetch_book_by_isbn(isbn)
        elif name in ("librarything", "lt"):
            if not lt.configured():
                errors.append("LibraryThing: немає LIBRARYTHING_API_KEY")
                continue
            data, err = lt.fetch_book_by_isbn(isbn)
        else:
            errors.append(f"невідомий провайдер «{name}»")
            continue

        if data:
            data.setdefault("source", name)
            # якщо провайдер дав книгу без обкладинки — підставити LT cover URL
            if (
                not (data.get("cover_url") or "").strip()
                and lt.configured()
                and data.get("isbn")
            ):
                data["cover_url"] = lt.cover_url_for_isbn(data["isbn"], "medium")
            return data, None
        if err:
            errors.append(err)

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
    if catalog_miss and infra:
        return None, (
            "Книгу з таким ISBN не знайдено в доступних каталогах. "
            "Задайте ISBNDB_API_KEY / GOOGLE_BOOKS_API_KEY або додайте книгу вручну."
        )
    return None, " | ".join(uniq)


def metadata_providers_ping() -> dict[str, Any]:
    """Агрегат для deep health."""
    payload: dict[str, Any] = {
        "book_metadata_providers": _providers(),
    }
    payload.update(ol.openlibrary_ping())
    payload.update(idb.isbndb_ping())
    payload.update(gb.googlebooks_ping())
    payload.update(lt.librarything_ping())
    return payload
