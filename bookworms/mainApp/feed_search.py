"""Пошук книг у довіднику Book (не постів)."""
from __future__ import annotations

from django.db.models import QuerySet

from .models import Book

BOOK_SEARCH_KEYS = (
    "q",
    "title",
    "isbn",
    "authors",
    "publisher",
    "publish_date",
    "age_min",
    "age_max",
)


def _int_or_none(raw) -> int | None:
    try:
        if raw is None or raw == "":
            return None
        return int(raw)
    except (TypeError, ValueError):
        return None


def apply_book_search(qs: QuerySet | None = None, params=None) -> QuerySet:
    """
    q / title — назва книги.
    isbn, authors, publisher, publish_date — icontains.
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

    publish_date = (params.get("publish_date") or "").strip()
    if publish_date:
        qs = qs.filter(publish_date__icontains=publish_date)

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
