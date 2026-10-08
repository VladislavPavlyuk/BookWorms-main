"""European languages for Advanced Search (English first, then A–Z by English name)."""
from __future__ import annotations

from django.db.models import Q

# (iso639-2/B, iso639-1, English name) — codes match typical ISBNdb / OL values.
EUROPEAN_LANGUAGES: tuple[tuple[str, str, str], ...] = (
    ("eng", "en", "English"),
    ("alb", "sq", "Albanian"),
    ("baq", "eu", "Basque"),
    ("bel", "be", "Belarusian"),
    ("bos", "bs", "Bosnian"),
    ("bre", "br", "Breton"),
    ("bul", "bg", "Bulgarian"),
    ("cat", "ca", "Catalan"),
    ("cor", "kw", "Cornish"),
    ("cos", "co", "Corsican"),
    ("cze", "cs", "Czech"),
    ("dan", "da", "Danish"),
    ("dut", "nl", "Dutch"),
    ("est", "et", "Estonian"),
    ("fao", "fo", "Faroese"),
    ("fin", "fi", "Finnish"),
    ("fre", "fr", "French"),
    ("fry", "fy", "Frisian"),
    ("glg", "gl", "Galician"),
    ("geo", "ka", "Georgian"),
    ("ger", "de", "German"),
    ("gre", "el", "Greek"),
    ("hun", "hu", "Hungarian"),
    ("ice", "is", "Icelandic"),
    ("gle", "ga", "Irish"),
    ("ita", "it", "Italian"),
    ("lav", "lv", "Latvian"),
    ("lit", "lt", "Lithuanian"),
    ("ltz", "lb", "Luxembourgish"),
    ("mac", "mk", "Macedonian"),
    ("mlt", "mt", "Maltese"),
    ("nor", "no", "Norwegian"),
    ("oci", "oc", "Occitan"),
    ("pol", "pl", "Polish"),
    ("por", "pt", "Portuguese"),
    ("rum", "ro", "Romanian"),
    ("roh", "rm", "Romansh"),
    ("rus", "ru", "Russian"),
    ("gla", "gd", "Scottish Gaelic"),
    ("srp", "sr", "Serbian"),
    ("slo", "sk", "Slovak"),
    ("slv", "sl", "Slovenian"),
    ("spa", "es", "Spanish"),
    ("swe", "sv", "Swedish"),
    ("ukr", "uk", "Ukrainian"),
    ("wel", "cy", "Welsh"),
)

# Also accept ISO 639-2/T variants that catalogs sometimes store.
_CODE_ALIASES: dict[str, tuple[str, ...]] = {
    "alb": ("sqi",),
    "baq": ("eus",),
    "cze": ("ces",),
    "dut": ("nld",),
    "fre": ("fra",),
    "geo": ("kat",),
    "ger": ("deu",),
    "gre": ("ell",),
    "ice": ("isl",),
    "rum": ("ron",),
    "slo": ("slk",),
    "spa": ("esl",),
    "wel": ("cym",),
}


def european_language_choices() -> list[tuple[str, str]]:
    """Select options: value=iso639-2/B code, label=English name."""
    return [(code3, name) for code3, _code2, name in EUROPEAN_LANGUAGES]


def language_search_q(code: str) -> Q | None:
    """
    Match Book.language against dropdown code (exact codes / English name).
    Avoids bare icontains('en') matching French/German/….
    """
    raw = (code or "").strip().lower()
    if not raw:
        return None
    for code3, code2, name in EUROPEAN_LANGUAGES:
        if raw in {code3, code2, name.lower()}:
            alts = _CODE_ALIASES.get(code3, ())
            q = Q(language__iexact=code3) | Q(language__iexact=code2) | Q(language__iexact=name)
            for a in alts:
                q |= Q(language__iexact=a)
            return q
    # Unknown free-text fallback (legacy bookmarks)
    return Q(language__icontains=raw)
