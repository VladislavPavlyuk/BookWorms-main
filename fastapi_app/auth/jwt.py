"""SimpleJWT-compatible access/refresh tokens (HS256 + DJANGO_SECRET_KEY)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt

from ..config import Settings, get_settings

TokenType = Literal["access", "refresh"]


class TokenError(Exception):
    """Invalid or expired JWT."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_token(
    user_id: int,
    token_type: TokenType,
    *,
    settings: Settings | None = None,
) -> str:
    cfg = settings or get_settings()
    lifetime = (
        cfg.access_token_timedelta_seconds
        if token_type == "access"
        else cfg.refresh_token_timedelta_seconds
    )
    now = _now()
    payload = {
        "token_type": token_type,
        "exp": now + timedelta(seconds=lifetime),
        "iat": now,
        "jti": uuid.uuid4().hex,
        "user_id": user_id,
    }
    return jwt.encode(payload, cfg.django_secret_key, algorithm="HS256")


def create_token_pair(
    user_id: int, *, settings: Settings | None = None
) -> dict[str, str]:
    return {
        "access": create_token(user_id, "access", settings=settings),
        "refresh": create_token(user_id, "refresh", settings=settings),
    }


def decode_token(
    token: str,
    *,
    expected_type: TokenType,
    settings: Settings | None = None,
) -> dict[str, Any]:
    cfg = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            cfg.django_secret_key,
            algorithms=["HS256"],
            options={"require": ["exp", "iat", "user_id", "token_type"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc

    if payload.get("token_type") != expected_type:
        raise TokenError("wrong token_type")
    if not isinstance(payload.get("user_id"), int):
        # JSON numbers may arrive as int; SimpleJWT uses int user_id
        try:
            payload["user_id"] = int(payload["user_id"])
        except (TypeError, ValueError) as exc:
            raise TokenError("invalid user_id") from exc
    return payload
