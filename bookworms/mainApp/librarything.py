"""
Метадані книги з LibraryThing за ISBN.

Документація (wiki / developer hub):
  https://wiki.librarything.com/index.php/LibraryThing_APIs
  https://www.librarything.com/developer
  Ключ: https://www.librarything.com/services/keys.php

Ендпоінти:
  - REST Common Knowledge getwork:
      GET /services/rest/1.1/?method=librarything.ck.getwork&isbn=…&apikey=…
  - Обкладинки (потрібен той самий ключ):
      https://covers.librarything.com/devkey/{key}/{small|medium|large}/isbn/{isbn}

Увага: LT офіційно пише, що не продає повну бібліографію (Bowker);
getwork усе ще дає title/author/CK для багатьох ISBN. Cloudflare може
блокувати датацентри — тоді лишається Open Library.
"""
from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .openlibrary import isbn_candidates, normalize_isbn, _preferred_isbn

LT_HOST = "https://www.librarything.com"
LT_COVERS = "https://covers.librarything.com"
CLIENT_REV = "lt-getwork-v1"

_CONTACT = os.environ.get("OPENLIBRARY_CONTACT_EMAIL", "admin@datedueslip.com").strip()
USER_AGENT = (
    os.environ.get("LIBRARYTHING_USER_AGENT", "").strip()
    or os.environ.get("OPENLIBRARY_USER_AGENT", "").strip()
    or f"DateDueSlip/1.0 (mailto:{_CONTACT}; LibraryThing ISBN client)"
)


# compose/env часто сетить LIBRARYTHING_API_KEY="" — порожній рядок ≠ відсутній ключ
_DEFAULT_API_KEY = "58aefacea1f37e153791c1cd58475558"


def api_key() -> str:
    return (os.environ.get("LIBRARYTHING_API_KEY") or _DEFAULT_API_KEY).strip()


def configured() -> bool:
    return bool(api_key())


def cover_url_for_isbn(isbn: str, size: str = "medium") -> str:
    """size: small | medium | large"""
    key = api_key()
    sz = size if size in ("small", "medium", "large") else "medium"
    return f"{LT_COVERS}/devkey/{quote(key)}/{sz}/isbn/{quote(isbn)}"


def _http_get_text(
    url: str, retries: int = 2, timeout: float = 20
) -> tuple[str | None, str | None]:
    last_err: str | None = None
    for attempt in range(retries + 1):
        req = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/xml, text/xml, */*",
            },
        )
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            if not raw:
                return None, None
            # Cloudflare challenge HTML
            if "Just a moment" in raw[:500] or "Attention Required" in raw[:500]:
                return None, "Cloudflare блокує запит до LibraryThing"
            return raw, None
        except HTTPError as e:
            if e.code == 404:
                return None, None
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:800]
            except Exception:
                body = ""
            if e.code in (403, 503) and (
                "Just a moment" in body
                or "Attention Required" in body
                or "cf-mitigated" in body.lower()
                or "cloudflare" in body.lower()
            ):
                return None, "Cloudflare блокує запит до LibraryThing (типово з NAS/DC IP)"
            last_err = f"HTTP {e.code}"
            if e.code == 403:
                # без body теж часто CF; не ретраїмо
                return None, "HTTP 403 (ймовірно Cloudflare)"
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
    return None, last_err


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return "".join(el.itertext()).strip()


def _parse_getwork_xml(xml_text: str, isbn: str) -> dict[str, Any] | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    # <response stat="fail">…
    if _local(root.tag) == "response":
        stat = (root.attrib.get("stat") or root.attrib.get("status") or "").lower()
        if stat and stat not in ("ok", "success"):
            return None

    item = None
    for el in root.iter():
        if _local(el.tag) == "item" and (el.attrib.get("type") or "work") in (
            "work",
            "",
        ):
            item = el
            break
    if item is None:
        # іноді item без type
        for el in root.iter():
            if _local(el.tag) == "item":
                item = el
                break
    if item is None:
        return None

    title = ""
    authors: list[str] = []
    work_id = item.attrib.get("id") or ""
    publish_date = ""
    publisher = ""

    for child in list(item):
        name = _local(child.tag).lower()
        if name == "title" and not title:
            title = _text(child)
        elif name == "author":
            a = _text(child)
            if a:
                authors.append(a)

    # Common Knowledge fieldList
    for field in item.iter():
        if _local(field.tag) != "field":
            continue
        fname = (field.attrib.get("name") or "").lower()
        fact_texts = [
            _text(f)
            for f in field.iter()
            if _local(f.tag) == "fact" and _text(f)
        ]
        blob = "; ".join(fact_texts) if fact_texts else _text(field)
        if not blob:
            continue
        if fname in ("originaltitle", "canonicaltitle") and not title:
            title = blob
        elif fname in ("originalpublicationdate", "publicationdate", "firstpublished"):
            # беремо рік якщо є
            m = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", blob)
            publish_date = m.group(1) if m else blob[:32]
        elif fname in ("publisher", "publishers") and not publisher:
            publisher = blob[:200]

    title = title.strip()
    if not title:
        return None

    info_url = (
        f"{LT_HOST}/work/{work_id}"
        if work_id
        else f"{LT_HOST}/isbn/{quote(isbn)}"
    )
    return {
        "title": title,
        "authors": ", ".join(authors),
        "publisher": publisher,
        "publish_date": publish_date,
        "cover_url": cover_url_for_isbn(isbn, "medium") if api_key() else "",
        "info_url": info_url,
        "isbn": isbn,
        "source": "librarything",
    }


def fetch_book_by_isbn(isbn: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    Повертає той самий dict-контракт, що Open Library:
    title, authors, publisher, publish_date, cover_url, info_url, isbn.
    """
    key = api_key()
    if not key:
        return None, "LIBRARYTHING_API_KEY не задано"

    norm = normalize_isbn(isbn)
    if not norm:
        return None, "Невірний ISBN: потрібно 10 символів (останній може бути X) або 13 цифр."

    soft_err: str | None = None
    for candidate in isbn_candidates(norm):
        qs = urlencode(
            {
                "method": "librarything.ck.getwork",
                "isbn": candidate,
                "apikey": key,
            }
        )
        url = f"{LT_HOST}/services/rest/1.1/?{qs}"
        raw, err = _http_get_text(url)
        if err:
            soft_err = err
            continue
        if not raw:
            continue
        parsed = _parse_getwork_xml(raw, candidate)
        if parsed:
            parsed["isbn"] = _preferred_isbn(norm, candidate)
            # обкладинка завжди на нормалізований/обраний ISBN
            if key:
                parsed["cover_url"] = cover_url_for_isbn(parsed["isbn"], "medium")
            return parsed, None

    if soft_err:
        return None, f"LibraryThing недоступна ({soft_err})."
    return None, "Книгу з таким ISBN не знайдено в LibraryThing."


def librarything_ping() -> dict[str, Any]:
    """Для /api/health/?deep=1."""
    key = api_key()
    if not key:
        return {
            "librarything_client": CLIENT_REV,
            "librarything_configured": False,
            "librarything_ok": False,
            "librarything_error": "no LIBRARYTHING_API_KEY",
        }
    # короткий lookup відомого ISBN
    data, err = fetch_book_by_isbn("9780140328721")
    # fetch_book_by_isbn already retries; for ping we accept result
    ok = isinstance(data, dict) and bool(data.get("title"))
    return {
        "librarything_client": CLIENT_REV,
        "librarything_configured": True,
        "librarything_ok": ok,
        "librarything_error": err,
        "librarything_sample_title": (data or {}).get("title") if data else None,
    }
