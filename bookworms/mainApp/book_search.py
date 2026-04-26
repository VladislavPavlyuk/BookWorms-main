"""
Пошук книг на полицях інших за полями моделі Book.
Порожні параметри ігноруються; усі задані об'єднуються через AND.
Поле `q` — швидкий пошук лише за назвою (title__icontains).
Поле `book` — id книги з довідника (точний збіг).
Поле `author` — один з авторів з довідника (розбиття рядка authors за комою/крапкою з комою тощо).
Поле `publisher` — видавець з довідника (точний збіг без урахування регістру).
"""
from __future__ import annotations

import re

from django.db.models import QuerySet

from .models import READER_AGE_MAX, READER_AGE_MIN, Book

SEARCH_GET_KEYS = (
    "q",
    "isbn",
    "publisher",
    "publish_date",
    "reader_age_min",
    "reader_age_max",
)


def _clean_term(get_dict, key: str, maxlen: int = 200) -> str:
    raw = get_dict.get(key)
    if raw is None:
        return ""
    s = str(raw).strip()
    return s[:maxlen] if s else ""


def _parse_reader_age(get_dict, key: str) -> int | None:
    raw = get_dict.get(key)
    if raw is None or str(raw).strip() == "":
        return None
    try:
        v = int(str(raw).strip())
    except ValueError:
        return None
    return max(READER_AGE_MIN, min(READER_AGE_MAX, v))


def split_authors_field(authors: str) -> list[str]:
    """Розбиває поле Book.authors на окремі імена (типові роздільники)."""
    if not authors or not str(authors).strip():
        return []
    parts = re.split(
        r"\s*[,;]\s*|\s+та\s+|\s+і\s+|\s+and\s+",
        str(authors),
        flags=re.IGNORECASE,
    )
    return [p.strip() for p in parts if p.strip()]


def unique_author_choices() -> list[str]:
    """Унікальні автори з усіх книг, алфавіт (без урахування регістру для сортування)."""
    seen: dict[str, str] = {}
    for row in Book.objects.exclude(authors="").values_list("authors", flat=True):
        for part in split_authors_field(row):
            key = part.casefold()
            if key not in seen:
                seen[key] = part
    return sorted(seen.values(), key=lambda s: s.casefold())


def unique_publisher_choices() -> list[str]:
    """Унікальні видавці з усіх книг, алфавіт (дублікати з різним регістром зливаються)."""
    seen: dict[str, str] = {}
    for row in Book.objects.exclude(publisher="").values_list("publisher", flat=True):
        p = (row or "").strip()
        if not p:
            continue
        key = p.casefold()
        if key not in seen:
            seen[key] = p
    return sorted(seen.values(), key=lambda s: s.casefold())


def _book_ids_matching_author_pick(author_pick: str) -> list[int]:
    pick_cf = author_pick.casefold()
    return [
        pk
        for pk, authors in Book.objects.exclude(authors="").values_list("id", "authors")
        if any(p.casefold() == pick_cf for p in split_authors_field(authors))
    ]


def _parse_book_id(get_dict) -> int | None:
    raw = get_dict.get("book")
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        return None


def has_active_book_search(get_dict) -> bool:
    if _parse_book_id(get_dict) is not None:
        return True
    if _clean_term(get_dict, "author", 500):
        return True
    for k in SEARCH_GET_KEYS:
        if k.startswith("reader_age"):
            if _parse_reader_age(get_dict, k) is not None:
                return True
        elif _clean_term(get_dict, k, 300 if k == "publisher" else 500):
            return True
    return False


def apply_book_search_to_shelf_queryset(qs: QuerySet, get_dict) -> QuerySet:
    """Фільтрує Shelf за пов'язаною Book (через book__)."""
    q_title = _clean_term(get_dict, "q", 500)
    author_pick = _clean_term(get_dict, "author", 500)
    isbn_raw = _clean_term(get_dict, "isbn", 32)
    publisher = _clean_term(get_dict, "publisher", 300)
    publish_date = _clean_term(get_dict, "publish_date", 64)

    if q_title:
        qs = qs.filter(book__title__icontains=q_title)
    book_id = _parse_book_id(get_dict)
    if book_id is not None:
        qs = qs.filter(book_id=book_id)
    if author_pick:
        matching = _book_ids_matching_author_pick(author_pick)
        qs = qs.filter(book_id__in=matching) if matching else qs.none()
    if isbn_raw:
        digits = "".join(c for c in isbn_raw if c.isdigit())
        needle = digits if len(digits) >= 4 else isbn_raw
        qs = qs.filter(book__isbn__icontains=needle)
    if publisher:
        qs = qs.filter(book__publisher__iexact=publisher)
    if publish_date:
        qs = qs.filter(book__publish_date__icontains=publish_date)

    age_min = _parse_reader_age(get_dict, "reader_age_min")
    age_max = _parse_reader_age(get_dict, "reader_age_max")
    # Перетин діапазонів рекомендованого віку: книга [bmin, bmax] ∩ [fmin, fmax] непорожній
    if age_min is not None:
        qs = qs.filter(book__max_readers_age__gte=age_min)
    if age_max is not None:
        qs = qs.filter(book__min_readers_age__lte=age_max)

    return qs
