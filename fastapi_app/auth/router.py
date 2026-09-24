from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.engine import Connection

from ..config import get_settings
from ..db import get_connection
from ..repositories import users as users_repo
from .jwt import TokenError, create_token_pair, decode_token
from .passwords import hash_password, verify_password
from .schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPairResponse,
    UserBrief,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPairResponse)
def login(
    body: LoginRequest,
    conn: Connection = Depends(get_connection),
):
    username = body.username.strip()
    user = users_repo.get_by_username(conn, username)
    if user is None or not verify_password(body.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невірний логін або пароль.",
        )
    if not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Акаунт не активовано. Підтвердіть email або використайте Django /api/auth/register/.",
        )
    tokens = create_token_pair(user["id"])
    return TokenPairResponse(
        access=tokens["access"],
        refresh=tokens["refresh"],
        user=UserBrief(id=user["id"], username=user["username"]),
    )


@router.post("/refresh", response_model=TokenPairResponse)
def refresh(
    body: RefreshRequest,
    conn: Connection = Depends(get_connection),
):
    try:
        payload = decode_token(body.refresh, expected_type="refresh")
    except TokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from None

    user = users_repo.get_by_id(conn, payload["user_id"])
    if user is None or not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User inactive or not found",
        )
    tokens = create_token_pair(user["id"])
    return TokenPairResponse(
        access=tokens["access"],
        refresh=tokens["refresh"],
        user=UserBrief(id=user["id"], username=user["username"]),
    )


@router.post("/register", response_model=TokenPairResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    conn: Connection = Depends(get_connection),
):
    settings = get_settings()
    if not settings.skip_email_activation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Email activation required. Use Django POST /api/auth/register/ "
                "(Web3Forms bridge), or set SKIP_EMAIL_ACTIVATION=1."
            ),
        )

    username = body.username.strip()
    email = body.email.strip()
    if users_repo.username_exists(conn, username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with that username already exists.",
        )

    user = users_repo.create_user(
        conn,
        username=username,
        email=email,
        password_hash=hash_password(body.password),
        biography=body.biography or "",
        is_active=True,
        email_confirmed=True,
    )
    tokens = create_token_pair(user["id"])
    return TokenPairResponse(
        access=tokens["access"],
        refresh=tokens["refresh"],
        user=UserBrief(id=user["id"], username=user["username"]),
    )
