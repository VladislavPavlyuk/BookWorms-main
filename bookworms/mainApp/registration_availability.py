"""Live registration checks: username/email taken + suggested unique logins."""

from __future__ import annotations

import re
import secrets

from django.contrib.auth import get_user_model

User = get_user_model()

# Django username ≤150; leave room for "_" + 4 hex (16-bit).
_BASE_MAX = 145
_HEX_BITS = 2  # token_hex(2) → 4 hex chars = 16-bit


def normalize_username(raw: str) -> str:
    return (raw or "").strip()


def normalize_email(raw: str) -> str:
    return (raw or "").strip()


def username_taken(username: str) -> bool:
    u = normalize_username(username)
    if not u:
        return False
    return User.objects.filter(username__iexact=u).exists()


def email_taken(email: str) -> bool:
    e = normalize_email(email)
    if not e:
        return False
    return User.objects.filter(email__iexact=e).exists()


def _sanitize_base(username: str) -> str:
    """Keep Django-allowed username chars; trim for suffix room."""
    base = normalize_username(username)
    base = re.sub(r"[^\w.@+-]", "", base, flags=re.UNICODE)
    if not base:
        base = "user"
    return base[:_BASE_MAX]


def suggest_usernames(base_username: str, *, count: int = 5) -> list[str]:
    """
    Propose unique logins: ``{base}_{XXXX}`` where XXXX is 16-bit hex (4 chars).
    """
    base = _sanitize_base(base_username)
    out: list[str] = []
    seen: set[str] = set()
    for _ in range(max(count * 12, 24)):
        if len(out) >= count:
            break
        cand = f"{base}_{secrets.token_hex(_HEX_BITS)}"
        key = cand.lower()
        if key in seen:
            continue
        seen.add(key)
        if not username_taken(cand):
            out.append(cand)
    return out


def check_registration_availability(
    *, username: str = "", email: str = ""
) -> dict:
    """
    Returns payload for live UI / API.

    When email is free (or empty) and username is taken → ``suggestions``.
    """
    u = normalize_username(username)
    e = normalize_email(email)

    u_taken = username_taken(u) if u else False
    e_taken = email_taken(e) if e else False
    u_ok = bool(u) and not u_taken
    e_ok = bool(e) and not e_taken

    suggestions: list[str] = []
    # Propose alternatives only when email is unique (or not filled yet) and username clashes.
    if u and u_taken and (not e or not e_taken):
        suggestions = suggest_usernames(u)

    return {
        "username": u,
        "email": e,
        "username_available": u_ok if u else None,
        "email_available": e_ok if e else None,
        "username_taken": u_taken,
        "email_taken": e_taken,
        "suggestions": suggestions,
        "message_uk": _message_uk(u, e, u_taken, e_taken, suggestions),
    }


def _message_uk(
    u: str,
    e: str,
    u_taken: bool,
    e_taken: bool,
    suggestions: list[str],
) -> str:
    parts: list[str] = []
    if e and e_taken:
        parts.append("Ця електронна адреса вже використовується.")
    if u and u_taken:
        if suggestions and (not e or not e_taken):
            parts.append(
                "Цей логін уже зайнятий. Оберіть запропонований унікальний логін нижче."
            )
        else:
            parts.append("Цей логін уже зайнятий.")
    if u and not u_taken:
        parts.append("Логін вільний.")
    if e and not e_taken:
        parts.append("Email вільний.")
    return " ".join(parts)
