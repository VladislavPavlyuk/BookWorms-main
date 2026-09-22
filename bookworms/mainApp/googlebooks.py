"""
Метадані книги з Google Books за ISBN.

  GET https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}

Опційно GOOGLE_BOOKS_API_KEY (підвищує квоту). Без ключа теж працює
для помірного трафіку. Корисний fallback коли Open Library порожня,
а LibraryThing блокує Cloudflare на датацентрових IP.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .openlibrary import isbn_candidates, normalize_isbn, _preferred_isbn

GB_HOST = "https://www.googleapis.com"
CLIENT_REV = "gb-volumes-v1"

_CONTACT = os.environ.get("OPENLIBRARY_CONTACT_EMAIL", "admin@datedueslip.com").strip()
USER_AGENT = (
    os.environ.get("GOOGLE_BOOKS_USER_AGENT", "").strip()
    or os.environ.get("OPENLIBRARY_USER_AGENT", "").strip()
    or f"DateDueSlip/1.0 (mailto:{_CONTACT}; Google Books ISBN client)"
)


def api_key() -> str:
    return (os.environ.get("GOOGLE_BOOKS_API_KEY") or "").strip()


def _http_get_json(
    url: str, retries: int = 2, timeout: float = 20
) -> tuple[Any | None, str | None]:
    last_err: str | None = None
    for attempt in range(retries + 1):
        req = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            if not raw:
                return None, None
            return json.loads(raw), None
        except HTTPError as e:
            if e.code == 404:
                return None, None
            last_err = f"HTTP {e.code}"
            if e.code in (429, 503) and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            if e.code == 429:
                return None, "HTTP 429 (квота; задайте GOOGLE_BOOKS_API_KEY)"
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


def _from_volume(item: dict[str, Any], isbn: str) -> dict[str, Any] | None:
    info = item.get("volumeInfo") or {}
    if not isinstance(info, dict):
        return None
    title = (info.get("title") or "").strip()
    if not title:
        return None
    subtitle = (info.get("subtitle") or "").strip()
    if subtitle:
        title = f"{title}: {subtitle}"

    authors = info.get("authors") or []
    if isinstance(authors, list):
        authors_s = ", ".join(str(a) for a in authors if a)
    else:
        authors_s = str(authors)

    pubs = info.get("publisher") or ""
    date = (info.get("publishedDate") or "").strip()

    cover = ""
    images = info.get("imageLinks") or {}
    if isinstance(images, dict):
        cover = (
            images.get("thumbnail")
            or images.get("smallThumbnail")
            or images.get("medium")
            or ""
        ).strip()
        # Google часто віддає http:// — браузери/мобільні люблять https
        if cover.startswith("http://"):
            cover = "https://" + cover[len("http://") :]

    # спроба взяти «канонічний» ISBN з industryIdentifiers
    for ident in info.get("industryIdentifiers") or []:
        if not isinstance(ident, dict):
            continue
        t = (ident.get("type") or "").upper()
        v = (ident.get("identifier") or "").strip()
        if t in ("ISBN_13", "ISBN_10") and v:
            # лишаємо caller'у preferred; тут лише для cover fallback
            break

    info_url = (info.get("infoLink") or info.get("canonicalVolumeLink") or "").strip()
    vid = item.get("id") or ""
    if not info_url and vid:
        info_url = f"https://books.google.com/books?id={quote(str(vid))}"

    return {
        "title": title,
        "authors": authors_s,
        "publisher": str(pubs).strip() if pubs else "",
        "publish_date": date,
        "cover_url": cover,
        "info_url": info_url,
        "isbn": isbn,
        "source": "googlebooks",
    }


def fetch_book_by_isbn(isbn: str) -> tuple[dict[str, Any] | None, str | None]:
    norm = normalize_isbn(isbn)
    if not norm:
        return None, "Невірний ISBN: потрібно 10 символів (останній може бути X) або 13 цифр."

    soft_err: str | None = None
    key = api_key()
    for candidate in isbn_candidates(norm):
        params: dict[str, str] = {"q": f"isbn:{candidate}", "maxResults": "1"}
        if key:
            params["key"] = key
        url = f"{GB_HOST}/books/v1/volumes?{urlencode(params)}"
        data, err = _http_get_json(url)
        if err:
            soft_err = err
            continue
        if not isinstance(data, dict):
            continue
        items = data.get("items") or []
        if not items or not isinstance(items[0], dict):
            continue
        parsed = _from_volume(items[0], candidate)
        if parsed:
            parsed["isbn"] = _preferred_isbn(norm, candidate)
            return parsed, None

    if soft_err:
        return None, f"Google Books недоступна ({soft_err})."
    return None, "Книгу з таким ISBN не знайдено в Google Books."


def googlebooks_ping() -> dict[str, Any]:
    data, err = fetch_book_by_isbn("9780140328721")
    ok = isinstance(data, dict) and bool(data.get("title"))
    return {
        "googlebooks_client": CLIENT_REV,
        "googlebooks_ok": ok,
        "googlebooks_error": err,
        "googlebooks_sample_title": (data or {}).get("title") if data else None,
        "googlebooks_key_set": bool(api_key()),
    }
