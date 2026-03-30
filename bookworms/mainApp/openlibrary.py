"""
Завантаження метаданих книги з Open Library за ISBN.

Чому urllib, а не requests: достатньо стандартної бібліотеки Python; не треба додаткових пакетів.
Формат запиту описаний тут: https://openlibrary.org/dev/docs/api/books (jscmd=data, format=json).
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

BOOKS_API = "https://openlibrary.org/api/books"
# Багато публічних API просять осмислений User-Agent — так ввічливіше до сервера.
USER_AGENT = "BookWorms/1.0 (ISBN library; contact: local)"


def normalize_isbn(raw: str) -> str | None:
    """Return ISBN-10 or ISBN-13 as digits (+ trailing X for ISBN-10), or None."""
    if not raw:
        return None
    s = re.sub(r"[^0-9Xx]", "", raw.strip()).upper()
    if len(s) == 10 and s[:-1].isdigit() and (s[-1].isdigit() or s[-1] == "X"):
        return s
    if len(s) == 13 and s.isdigit():
        return s
    return None


def _authors_line(data: dict[str, Any]) -> str:
    """З JSON Open Library робимо один рядок «Ім'я1, Ім'я2» для збереження в моделі Book."""
    authors = data.get("authors") or []
    names = []
    for a in authors:
        if isinstance(a, dict) and a.get("name"):
            names.append(a["name"])
    return ", ".join(names)


def _first_publisher(data: dict[str, Any]) -> str:
    """Беремо першого видавця зі списку — для картки книги цього зазвичай достатньо."""
    pubs = data.get("publishers") or []
    if pubs and isinstance(pubs[0], dict):
        return pubs[0].get("name") or ""
    return ""


def fetch_book_by_isbn(isbn: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    Головна функція для views: або словник полів для Book, або текст помилки українською.
    Повертає кортеж (дані, None) при успіху або (None, повідомлення) при збої.
    """
    norm = normalize_isbn(isbn)
    if not norm:
        return None, "Невірний ISBN: потрібно 10 символів (останній може бути X) або 13 цифр."

    # bibkeys — формат, який очікує Books API; jscmd=data повертає назву, авторів, обкладинку тощо.
    bibkey = f"ISBN:{norm}"
    url = f"{BOOKS_API}?bibkeys={quote(bibkey)}&jscmd=data&format=json"
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
    except HTTPError as e:
        return None, f"Помилка Open Library: HTTP {e.code}"
    except URLError as e:
        return None, f"Мережа недоступна: {e.reason!s}"

    try:
        doc = json.loads(body)
    except json.JSONDecodeError:
        return None, "Некоректна відповідь Open Library."

    entry = doc.get(bibkey)
    if not entry or not isinstance(entry, dict):
        return None, "Книгу з таким ISBN не знайдено в Open Library."

    title = (entry.get("title") or "").strip()
    if not title:
        return None, "У записі Open Library немає назви."

    cover = entry.get("cover") or {}
    cover_url = cover.get("medium") or cover.get("small") or cover.get("large") or ""

    return {
        "title": title,
        "authors": _authors_line(entry),
        "publisher": _first_publisher(entry),
        "publish_date": (entry.get("publish_date") or "").strip(),
        "cover_url": cover_url,
        "info_url": (entry.get("url") or "").strip(),
        "isbn": norm,
    }, None
