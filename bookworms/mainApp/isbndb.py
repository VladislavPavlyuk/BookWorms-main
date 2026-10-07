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


_PLACEHOLDER_KEYS = frozenset(
    {
        "",
        "your_rest_key",
        "your-rest-key",
        "changeme",
        "change-me",
        "xxx",
        "TODO",
        "todo",
    }
)


def api_key() -> str:
    raw = (
        os.environ.get("ISBNDB_API_KEY")
        or os.environ.get("ISBNDB_REST_KEY")
        or ""
    ).strip()
    # strip inline comments from .env style "key  # comment"
    if "#" in raw:
        raw = raw.split("#", 1)[0].strip()
    if raw.lower() in {p.lower() for p in _PLACEHOLDER_KEYS}:
        return ""
    return raw


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


def _https(url: str) -> str:
    u = (url or "").strip()
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    return u


def _as_str_list(raw: Any) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return [str(raw).strip()] if str(raw).strip() else []


def _other_isbns(raw: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        isbn = str(item.get("isbn") or "").strip()
        if not isbn:
            continue
        out.append(
            {
                "isbn": isbn[:32],
                "binding": str(item.get("binding") or "").strip()[:64],
            }
        )
    return out


def _from_book(book: dict[str, Any], fallback_isbn: str) -> dict[str, Any] | None:
    """Map ISBNdb Book schema → internal catalog payload."""
    title = (book.get("title") or book.get("title_long") or "").strip()
    if not title:
        return None

    isbn13 = (book.get("isbn13") or "").strip()
    isbn_field = (book.get("isbn") or "").strip()
    isbn10_raw = (book.get("isbn10") or "").strip()
    # Schema: isbn is deprecated and often ISBN-13; prefer isbn13 then isbn10.
    picked = (
        normalize_isbn(isbn13)
        or normalize_isbn(isbn_field if len(isbn_field) == 13 else "")
        or normalize_isbn(isbn10_raw)
        or normalize_isbn(isbn_field)
        or normalize_isbn(fallback_isbn)
    )
    if not picked:
        picked = fallback_isbn

    isbn10 = ""
    if isbn10_raw and len(normalize_isbn(isbn10_raw) or "") == 10:
        isbn10 = normalize_isbn(isbn10_raw) or ""
    elif len(picked) == 13:
        from .openlibrary import isbn13_to_isbn10

        isbn10 = isbn13_to_isbn10(picked) or ""

    # image (≤500px) is stable; image_original expires ~2h
    cover = _https(book.get("image") or "")
    cover_orig = _https(book.get("image_original") or "")

    date = book.get("date_published")
    if date is None:
        date_s = ""
    else:
        date_s = str(date).strip()
        if "T" in date_s:
            date_s = date_s.split("T", 1)[0]

    pages = book.get("pages")
    try:
        pages_i = int(pages) if pages is not None and str(pages).strip() != "" else None
    except (TypeError, ValueError):
        pages_i = None

    msrp = book.get("msrp")
    try:
        msrp_f = float(msrp) if msrp is not None and str(msrp).strip() != "" else None
    except (TypeError, ValueError):
        msrp_f = None

    dims_data = book.get("dimensions_structured")
    if not isinstance(dims_data, (dict, list)):
        dims_data = {}

    publisher = (book.get("publisher") or "").strip()
    info_url = f"https://isbndb.com/book/{quote(picked)}"

    return {
        "title": title[:500],
        "title_long": (book.get("title_long") or title)[:500],
        "authors": _authors_line(book.get("authors"))[:500],
        "publisher": publisher[:300],
        "publish_date": date_s[:64],
        "binding": (book.get("binding") or "").strip()[:64],
        "language": (book.get("language") or "").strip()[:32],
        "edition": (book.get("edition") or "").strip()[:64],
        "pages": pages_i,
        "dimensions": (book.get("dimensions") or "").strip()[:200],
        "dimensions_data": dims_data if isinstance(dims_data, dict) else {"_list": dims_data},
        "dewey_decimal": _as_str_list(book.get("dewey_decimal")),
        "overview": (book.get("overview") or "").strip(),
        "synopsis": (book.get("synopsis") or "").strip(),
        "excerpt": (book.get("excerpt") or "").strip(),
        "msrp": msrp_f,
        "subjects": _as_str_list(book.get("subjects")),
        "other_isbns": _other_isbns(book.get("other_isbns")),
        "cover_url": cover[:500],
        "cover_url_original": cover_orig[:500],
        "info_url": info_url[:500],
        "isbn": picked,
        "isbn10": isbn10[:10],
        "source": "isbndb",
        "catalog_source": "isbndb",
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
        raw = (os.environ.get("ISBNDB_API_KEY") or os.environ.get("ISBNDB_REST_KEY") or "").strip()
        hint = "no ISBNDB_API_KEY"
        if raw and not api_key():
            hint = "ISBNDB_API_KEY is placeholder/invalid (check /.env mount)"
        elif not raw:
            hint = "no ISBNDB_API_KEY in process env (recreate api after editing .env)"
        return {
            "isbndb_client": CLIENT_REV,
            "isbndb_configured": False,
            "isbndb_ok": False,
            "isbndb_error": hint,
            "isbndb_key_len": len(raw),
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
