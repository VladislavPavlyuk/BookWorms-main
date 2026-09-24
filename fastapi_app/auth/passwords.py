"""Django-compatible password hashing (pbkdf2_sha256)."""
from __future__ import annotations

from passlib.hash import django_pbkdf2_sha256


def hash_password(plain: str) -> str:
    return django_pbkdf2_sha256.hash(plain)


def verify_password(plain: str, encoded: str) -> bool:
    if not encoded:
        return False
    try:
        return django_pbkdf2_sha256.verify(plain, encoded)
    except (ValueError, TypeError):
        return False
