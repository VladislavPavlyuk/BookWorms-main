"""Age derived from birthday (profile / subprofile)."""
from __future__ import annotations

from datetime import date


def age_from_birthday(
    birthday: date | None, *, today: date | None = None
) -> int | None:
    """Full years since birthday; None if missing or in the future."""
    if birthday is None:
        return None
    today = today or date.today()
    if birthday > today:
        return None
    years = today.year - birthday.year
    if (today.month, today.day) < (birthday.month, birthday.day):
        years -= 1
    return max(0, min(years, 120))


def approx_birthday_from_age(age: int, *, today: date | None = None) -> date:
    """Best-effort birthday for migrating legacy integer age → date."""
    today = today or date.today()
    age = max(0, min(int(age), 120))
    year = today.year - age
    try:
        return today.replace(year=year)
    except ValueError:
        # 29 Feb → 28 Feb in non-leap birth year
        return today.replace(year=year, day=28)
