"""Пошук книг у довіднику Book (не постів)."""
from __future__ import annotations

from django.db.models import Q, QuerySet

from .book_languages import language_search_q
from .models import Book

BOOK_SEARCH_KEYS = (
    "q",
    "title",
    "isbn",
    "authors",
    "publisher",
    "publish_date",  # legacy single-string
    "year_from",
    "year_to",
    "language",
    "age_min",
    "age_max",
)

_YEAR_MIN = 1000
_YEAR_MAX = 2100
_YEAR_SPAN_MAX = 300


def _int_or_none(raw) -> int | None:
    try:
        if raw is None or raw == "":
            return None
        return int(raw)
    except (TypeError, ValueError):
        return None


def _clamp_year(y: int | None) -> int | None:
    if y is None:
        return None
    return max(_YEAR_MIN, min(_YEAR_MAX, y))


def _year_range_q(year_from: int | None, year_to: int | None) -> Q | None:
    """
    Match books whose publish_date text contains a 4-digit year in [from, to].
    publish_date is free-form CharField («1980», «1980-03-01», …).
    """
    y0 = _clamp_year(year_from)
    y1 = _clamp_year(year_to)
    if y0 is None and y1 is None:
        return None
    if y0 is None:
        y0 = _YEAR_MIN
    if y1 is None:
        y1 = _YEAR_MAX
    if y0 > y1:
        y0, y1 = y1, y0
    if y1 - y0 > _YEAR_SPAN_MAX:
        y1 = y0 + _YEAR_SPAN_MAX
    q = Q()
    for y in range(y0, y1 + 1):
        # Word-ish boundary so «198» does not match inside «1980» wrongly —
        # icontains of full 4-digit year is enough for catalog strings.
        q |= Q(publish_date__icontains=str(y))
    return q


def apply_book_search(qs: QuerySet | None = None, params=None) -> QuerySet:
    """
    q / title — назва книги.
    isbn, authors, publisher — icontains.
    year_from / year_to — рік видання (діапазон); legacy publish_date — icontains.
    language — exact/alias match.
    age_min / age_max — перетин з рекомендованим віком.
    """
    if qs is None:
        qs = Book.objects.all()
    if params is None:
        params = {}

    title = (params.get("q") or params.get("title") or "").strip()
    if title:
        qs = qs.filter(title__icontains=title)

    isbn = (params.get("isbn") or "").strip()
    if isbn:
        qs = qs.filter(isbn__icontains=isbn)

    authors = (params.get("authors") or "").strip()
    if authors:
        qs = qs.filter(authors__icontains=authors)

    publisher = (params.get("publisher") or "").strip()
    if publisher:
        qs = qs.filter(publisher__icontains=publisher)

    year_from = _int_or_none(params.get("year_from"))
    year_to = _int_or_none(params.get("year_to"))
    year_q = _year_range_q(year_from, year_to)
    if year_q is not None:
        qs = qs.filter(year_q)
    else:
        # Legacy single free-text publish_date (old bookmarks / clients).
        publish_date = (params.get("publish_date") or "").strip()
        if publish_date:
            qs = qs.filter(publish_date__icontains=publish_date)

    language = (params.get("language") or "").strip()
    if language:
        lang_q = language_search_q(language)
        if lang_q is not None:
            qs = qs.filter(lang_q)

    age_min = _int_or_none(params.get("age_min"))
    age_max = _int_or_none(params.get("age_max"))
    if age_min is not None:
        qs = qs.filter(max_readers_age__gte=age_min)
    if age_max is not None:
        qs = qs.filter(min_readers_age__lte=age_max)

    return qs.order_by("title")


def search_active(params) -> bool:
    return any((params.get(k) or "").strip() for k in BOOK_SEARCH_KEYS)


def advanced_active(params) -> bool:
    return any(
        (params.get(k) or "").strip()
        for k in BOOK_SEARCH_KEYS
        if k != "q"
    )
