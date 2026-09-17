"""
Метадані книги з Open Library за ISBN.

Legacy `/api/books` зараз 404 — не використовуємо.
Робочі ендпоінти (див. https://openlibrary.org/developers/api ):
  - GET /isbn/{isbn}.json
  - GET /search.json?isbn=
  - GET /authors/{id}.json
  - covers.openlibrary.org/b/id/{id}-M.jpg

User-Agent обов’язково з email → rate limit 3 rps замість 1.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

OL_HOST = "https://openlibrary.org"
COVERS_HOST = "https://covers.openlibrary.org"
CLIENT_REV = "ol-isbn-json-v2"

_CONTACT = os.environ.get("OPENLIBRARY_CONTACT_EMAIL", "admin@datedueslip.com").strip()
USER_AGENT = (
    os.environ.get("OPENLIBRARY_USER_AGENT", "").strip()
    or f"DateDueSlip/1.0 (mailto:{_CONTACT})"
)


def normalize_isbn(raw: str) -> str | None:
    if not raw:
        return None
    s = re.sub(r"[^0-9Xx]", "", raw.strip()).upper()
    if len(s) == 10 and s[:-1].isdigit() and (s[-1].isdigit() or s[-1] == "X"):
        return s
    if len(s) == 13 and s.isdigit():
        return s
    return None


def isbn10_to_isbn13(isbn10: str) -> str:
    core = "978" + isbn10[:-1]
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(core))
    check = (10 - (total % 10)) % 10
    return core + str(check)


def isbn13_to_isbn10(isbn13: str) -> str | None:
    if not isbn13.startswith("978") or len(isbn13) != 13:
        return None
    core = isbn13[3:12]
    total = sum((10 - i) * int(d) for i, d in enumerate(core))
    check = (11 - (total % 11)) % 11
    return core + ("X" if check == 10 else str(check))


def isbn_candidates(norm: str) -> list[str]:
    out = [norm]
    if len(norm) == 10:
        out.append(isbn10_to_isbn13(norm))
    else:
        alt = isbn13_to_isbn10(norm)
        if alt:
            out.append(alt)
    seen: set[str] = set()
    uniq: list[str] = []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def _preferred_isbn(norm: str, found: str) -> str:
    if len(norm) == 13:
        return norm
    if len(found) == 13:
        return found
    if len(found) == 10:
        return isbn10_to_isbn13(found)
    return norm


def _http_get_json(url: str, retries: int = 2) -> tuple[Any | None, str | None]:
    """
    Повертає (data, None) | (None, None) якщо 404/порожньо |
    (None, err) при мережевій/серверній помилці.
    Ніколи не кидає — щоб ISBN-lookup не падав на одному 404.
    """
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
            with urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8")
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


def _cover_url_from_edition(edition: dict[str, Any], isbn: str) -> str:
    covers = edition.get("covers") or []
    for cid in covers:
        if isinstance(cid, int) and cid > 0:
            return f"{COVERS_HOST}/b/id/{cid}-M.jpg"
    return f"{COVERS_HOST}/b/isbn/{quote(isbn)}-M.jpg"


def _publisher_line(edition: dict[str, Any]) -> str:
    pubs = edition.get("publishers") or []
    if not pubs:
        return ""
    if isinstance(pubs[0], dict):
        return (pubs[0].get("name") or "").strip()
    return str(pubs[0]).strip()


def _resolve_authors(edition: dict[str, Any]) -> str:
    authors = edition.get("authors") or []
    names: list[str] = []
    for a in authors:
        if not isinstance(a, dict):
            continue
        if a.get("name"):
            names.append(a["name"])
            continue
        key = a.get("key") or ""
        if not key.startswith("/authors/"):
            continue
        adoc, _ = _http_get_json(f"{OL_HOST}{key}.json")
        if isinstance(adoc, dict) and adoc.get("name"):
            names.append(adoc["name"])
    return ", ".join(names)


def _from_edition(edition: dict[str, Any], isbn: str) -> dict[str, Any] | None:
    title = (edition.get("title") or "").strip()
    if not title:
        return None
    info = edition.get("key") or ""
    info_url = f"{OL_HOST}{info}" if info.startswith("/") else ""
    return {
        "title": title,
        "authors": _resolve_authors(edition),
        "publisher": _publisher_line(edition),
        "publish_date": (edition.get("publish_date") or "").strip(),
        "cover_url": _cover_url_from_edition(edition, isbn),
        "info_url": info_url,
        "isbn": isbn,
    }


def _from_search_doc(doc: dict[str, Any], isbn: str) -> dict[str, Any] | None:
    title = (doc.get("title") or "").strip()
    if not title:
        return None
    authors = doc.get("author_name") or []
    cover_id = doc.get("cover_i")
    cover_url = (
        f"{COVERS_HOST}/b/id/{cover_id}-M.jpg"
        if cover_id
        else f"{COVERS_HOST}/b/isbn/{quote(isbn)}-M.jpg"
    )
    olid = doc.get("edition_key") or doc.get("key") or ""
    if isinstance(olid, list) and olid:
        info_url = f"{OL_HOST}/books/{olid[0]}"
    elif isinstance(olid, str) and olid.startswith("/"):
        info_url = f"{OL_HOST}{olid}"
    else:
        info_url = f"{OL_HOST}/isbn/{isbn}"
    pubs = doc.get("publisher") or []
    return {
        "title": title,
        "authors": ", ".join(authors) if isinstance(authors, list) else str(authors),
        "publisher": pubs[0] if pubs else "",
        "publish_date": str(doc.get("first_publish_year") or ""),
        "cover_url": cover_url,
        "info_url": info_url,
        "isbn": isbn,
    }


def fetch_book_by_isbn(isbn: str) -> tuple[dict[str, Any] | None, str | None]:
    norm = normalize_isbn(isbn)
    if not norm:
        return None, "Невірний ISBN: потрібно 10 символів (останній може бути X) або 13 цифр."

    soft_err: str | None = None

    for candidate in isbn_candidates(norm):
        edition, err = _http_get_json(f"{OL_HOST}/isbn/{quote(candidate)}.json")
        if err:
            soft_err = err
            continue
        if isinstance(edition, dict):
            parsed = _from_edition(edition, candidate)
            if parsed:
                parsed["isbn"] = _preferred_isbn(norm, candidate)
                return parsed, None

    for candidate in isbn_candidates(norm):
        search, err = _http_get_json(
            f"{OL_HOST}/search.json?isbn={quote(candidate)}&limit=1"
        )
        if err:
            soft_err = err
            continue
        if not isinstance(search, dict):
            continue
        docs = search.get("docs") or []
        if docs and isinstance(docs[0], dict):
            parsed = _from_search_doc(docs[0], candidate)
            if parsed:
                parsed["isbn"] = _preferred_isbn(norm, candidate)
                return parsed, None

    if soft_err:
        # не «HTTP 404» — це майже завжди «немає edition»; лишаємо мережеві коди
        if soft_err.startswith("HTTP 404"):
            return None, "Книгу з таким ISBN не знайдено в Open Library."
        return None, f"Open Library недоступна ({soft_err}). Перевір outbound HTTPS з контейнера api."
    return None, "Книгу з таким ISBN не знайдено в Open Library."


def openlibrary_ping() -> dict[str, Any]:
    """Для /api/health/ — чи контейнер взагалі дістає OL."""
    data, err = _http_get_json(f"{OL_HOST}/isbn/9780140328721.json", retries=1)
    ok = isinstance(data, dict) and bool(data.get("title"))
    return {
        "openlibrary_client": CLIENT_REV,
        "openlibrary_ok": ok,
        "openlibrary_error": err,
        "openlibrary_sample_title": (data or {}).get("title") if isinstance(data, dict) else None,
        "openlibrary_user_agent": USER_AGENT,
    }
