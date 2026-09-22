"""
Метадані книги з ISBNdb (REST API v2) за ISBN.

Документація: https://isbndb.com/isbndb-api-documentation-v2
             https://isbndb.com/apidocs/v2

  GET https://api2.isbndb.com/book/{isbn}
  Header: Authorization: <REST_KEY>   (не query-param)

Ключ: ISBNDB_API_KEY (або ISBNDB_REST_KEY) у .env.
Без ключа провайдер пропускається.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .openlibrary import isbn_candidates, normalize_isbn, _preferred_isbn

ISBNDB_HOST = "https://api2.isbndb.com"
CLIENT_REV = "isbndb-book-v1"

_CONTACT = os.environ.get("OPENLIBRARY_CONTACT_EMAIL", "admin@datedueslip.com").strip()
USER_AGENT = (
    os.environ.get("ISBNDB_USER_AGENT", "").strip()
    or os.environ.get("OPENLIBRARY_USER_AGENT", "").strip()
    or f"DateDueSlip/1.0 (mailto:{_CONTACT}; ISBNdb ISBN client)"
)


def api_key() -> str:
    return (
        os.environ.get("ISBNDB_API_KEY")
        or os.environ.get("ISBNDB_REST_KEY")
        or ""
    ).strip()


def configured() -> bool:
    return bool(api_key())


def _http_get_json(
    url: str, retries: int = 2, timeout: float = 20
) -> tuple[Any | None, str | None]:
    key = api_key()
    if not key:
        return None, "ISBNDB_API_KEY не задано"

    last_err: str | None = None
    for attempt in range(retries + 1):
        req = Request(
            url,
            headers={
                "Authorization": key,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            if not raw:
                return None, None
            return json.loads(raw), None
        except HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                body = ""
            if e.code == 404:
                return None, None
            if e.code == 401:
                return None, "HTTP 401 (невірний або неактивний ISBNDB_API_KEY)"
            if e.code == 400:
                return None, "HTTP 400 (некоректний ISBN для ISBNdb)"
            last_err = f"HTTP {e.code}"
            if body and "error" in body.lower():
                last_err = f"HTTP {e.code}"
            if e.code in (429, 503) and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            if e.code == 429:
                return None, "HTTP 429 (квота ISBNdb)"
            return None, last_err
        except URLError as e:
            last_err = f"мережа: {e.reason!s}"
            if attempt < retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            return None, last_err
        except json.JSONDecodeError:
            return None, "некоректний JSON"
    return None, last_err


def _authors_line(raw: Any) -> str:
    if not raw:
        return ""
    if isinstance(raw, list):
        return ", ".join(str(a).strip() for a in raw if a)
    return str(raw).strip()


def _from_book(book: dict[str, Any], fallback_isbn: str) -> dict[str, Any] | None:
    title = (book.get("title") or book.get("title_long") or "").strip()
    if not title:
        return None

    isbn13 = (book.get("isbn13") or "").strip()
    isbn10 = (book.get("isbn") or "").strip()
    # у схемі поле isbn іноді deprecated і теж ISBN-13
    picked = normalize_isbn(isbn13) or normalize_isbn(isbn10) or normalize_isbn(fallback_isbn)
    if not picked:
        picked = fallback_isbn

    # image (до 500px) стабільніший за image_original (expires ~2h)
    cover = (book.get("image") or "").strip()
    if cover.startswith("http://"):
        cover = "https://" + cover[len("http://") :]

    date = book.get("date_published")
    if date is None:
        date_s = ""
    else:
        date_s = str(date).strip()
        # ISO datetime → YYYY-MM-DD / YYYY
        if "T" in date_s:
            date_s = date_s.split("T", 1)[0]

    publisher = (book.get("publisher") or "").strip()
    info_url = f"https://isbndb.com/book/{quote(picked)}"

    return {
        "title": title[:500],
        "authors": _authors_line(book.get("authors"))[:500],
        "publisher": publisher[:300],
        "publish_date": date_s[:64],
        "cover_url": cover[:500],
        "info_url": info_url[:500],
        "isbn": picked,
        "source": "isbndb",
    }


def fetch_book_by_isbn(isbn: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    GET /book/{isbn} — той самий dict-контракт, що OL/GB/LT.
    """
    if not configured():
        return None, "ISBNDB_API_KEY не задано"

    norm = normalize_isbn(isbn)
    if not norm:
        return None, "Невірний ISBN: потрібно 10 символів (останній може бути X) або 13 цифр."

    soft_err: str | None = None
    for candidate in isbn_candidates(norm):
        url = f"{ISBNDB_HOST}/book/{quote(candidate)}"
        data, err = _http_get_json(url)
        if err:
            soft_err = err
            # 401 — ключ зламаний, не крутимо кандидати
            if "401" in err:
                return None, f"ISBNdb недоступна ({err})."
            continue
        if not isinstance(data, dict):
            continue
        book = data.get("book")
        if not isinstance(book, dict):
            continue
        parsed = _from_book(book, candidate)
        if parsed:
            parsed["isbn"] = _preferred_isbn(norm, parsed["isbn"])
            return parsed, None

    if soft_err:
        return None, f"ISBNdb недоступна ({soft_err})."
    return None, "Книгу з таким ISBN не знайдено в ISBNdb."


def isbndb_ping() -> dict[str, Any]:
    """Для /api/health/?deep=1."""
    if not configured():
        return {
            "isbndb_client": CLIENT_REV,
            "isbndb_configured": False,
            "isbndb_ok": False,
            "isbndb_error": "no ISBNDB_API_KEY",
        }
    # /key — перевірка ключа (легше за book lookup)
    data, err = _http_get_json(f"{ISBNDB_HOST}/key", retries=0, timeout=8)
    if isinstance(data, dict) and not err:
        return {
            "isbndb_client": CLIENT_REV,
            "isbndb_configured": True,
            "isbndb_ok": True,
            "isbndb_error": None,
            "isbndb_key_info": {
                k: data.get(k)
                for k in ("key", "plan", "queries", "callsRemaining", "calls")
                if k in data
            }
            or None,
        }
    # fallback: sample ISBN
    book, berr = fetch_book_by_isbn("9780140328721")
    ok = isinstance(book, dict) and bool(book.get("title"))
    return {
        "isbndb_client": CLIENT_REV,
        "isbndb_configured": True,
        "isbndb_ok": ok,
        "isbndb_error": err or berr,
        "isbndb_sample_title": (book or {}).get("title") if book else None,
    }
