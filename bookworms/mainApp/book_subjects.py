"""Distinct Theme/Genre values from Book.subjects (internal catalog only)."""
from __future__ import annotations

from django.core.cache import cache

from .models import Book

_CACHE_KEY = "catalog_subjects:v1"
_CACHE_TTL = 30  # seconds — dropdown picks up new themes quickly


def _normalize_subject(raw) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    return str(raw).strip()


def catalog_subjects(*, use_cache: bool = True) -> list[str]:
    """
    Unique non-empty subjects from Book.subjects JSON lists, sorted case-insensitively.
    Refreshes from DB at least every _CACHE_TTL so new catalog themes appear in the dropdown.
    """
    if use_cache:
        cached = cache.get(_CACHE_KEY)
        if cached is not None:
            return list(cached)

    seen: dict[str, str] = {}  # casefold -> display
    for raw in Book.objects.values_list("subjects", flat=True).iterator(chunk_size=500):
        if not isinstance(raw, (list, tuple)) or not raw:
            continue
        for item in raw:
            label = _normalize_subject(item)
            if not label:
                continue
            key = label.casefold()
            if key not in seen:
                seen[key] = label

    result = sorted(seen.values(), key=lambda s: s.casefold())
    if use_cache:
        cache.set(_CACHE_KEY, result, _CACHE_TTL)
    return result


def invalidate_catalog_subjects_cache() -> None:
    cache.delete(_CACHE_KEY)
