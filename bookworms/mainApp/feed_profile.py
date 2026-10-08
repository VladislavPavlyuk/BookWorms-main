"""Filter the main feed by user profile + subprofiles (themes / age)."""
from __future__ import annotations

from django.db.models import Q, QuerySet

from .models import READER_AGE_MAX, Post, UserSubProfile


def _norm_subjects(raw) -> list[str]:
    if not isinstance(raw, (list, tuple)):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        label = (item if isinstance(item, str) else str(item or "")).strip()
        if not label:
            continue
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(label)
    return out


def _clamp_reader_age(age: int) -> int:
    return max(0, min(int(age), READER_AGE_MAX))


def persona_match_q(*, age: int | None, subjects) -> Q | None:
    """
    Q for posts whose book fits this persona.
    None = unconstrained (ignore this persona for filtering).
    Age: user age (capped at 18 for 18+ books) within book.min/max_readers_age.
    Themes: book.subjects contains at least one preferred subject.
    Both set → AND; either alone → that constraint only.
    """
    themes = _norm_subjects(subjects)
    age_q: Q | None = None
    if age is not None:
        try:
            a = int(age)
        except (TypeError, ValueError):
            a = None
        if a is not None:
            eff = _clamp_reader_age(a)
            age_q = Q(
                book__min_readers_age__lte=eff,
                book__max_readers_age__gte=eff,
            )

    theme_q: Q | None = None
    if themes:
        from .book_subjects import subjects_contain_q

        tq = Q()
        for theme in themes:
            tq |= subjects_contain_q(theme, field="book__subjects")
        theme_q = tq

    if age_q is None and theme_q is None:
        return None
    if age_q is not None and theme_q is not None:
        return age_q & theme_q
    return age_q if age_q is not None else theme_q


def collect_persona_qs(user) -> list[Q]:
    parts: list[Q] = []
    main = persona_match_q(
        age=getattr(user, "age", None),
        subjects=getattr(user, "preferred_subjects", None) or [],
    )
    if main is not None:
        parts.append(main)

    subs = getattr(user, "subprofiles", None)
    if subs is None:
        return parts
    qs = subs.all() if hasattr(subs, "all") else UserSubProfile.objects.filter(user=user)
    for sp in qs:
        pq = persona_match_q(age=sp.age, subjects=sp.preferred_subjects or [])
        if pq is not None:
            parts.append(pq)
    return parts


def apply_profile_feed_filter(qs: QuerySet[Post], user) -> QuerySet[Post]:
    """
    Limit posts to books matching main profile OR any subprofile.
    Posts without a book always pass. No age/theme prefs → no extra filter.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return qs
    parts = collect_persona_qs(user)
    if not parts:
        return qs
    match = parts[0]
    for p in parts[1:]:
        match |= p
    return qs.filter(Q(book__isnull=True) | match)
