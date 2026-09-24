"""
Auth + protected shelf tests — live Postgres.

Naming: test_<method>_<whenCondition>_<returnsExpected>
Assert style: actualResult / expectedResult; one assert per test.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Connection, Engine

# Force settings before app import cache
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-for-jwt")
os.environ.setdefault("SKIP_EMAIL_ACTIVATION", "1")
os.environ.setdefault("JWT_ACCESS_DAYS", "1")
os.environ.setdefault("JWT_REFRESH_DAYS", "7")

from fastapi_app.auth.jwt import create_token, decode_token
from fastapi_app.config import get_settings
from fastapi_app.db import get_connection
from fastapi_app.main import app


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client(engine: Engine, conn: Connection, shelf_seed: dict) -> TestClient:
    """HTTP client; DB deps use the same transactional connection as fixtures."""

    def _override_connection():
        yield conn

    app.dependency_overrides[get_connection] = _override_connection
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestLogin:
    def test_login_when_credentials_valid_returns_access_and_refresh(
        self, client: TestClient, shelf_seed: dict
    ):
        response = client.post(
            "/auth/login",
            json={"username": "owner", "password": shelf_seed["owner_password"]},
        )

        actualResult = sorted(response.json().keys()) if response.status_code == 200 else response.status_code
        expectedResult = ["access", "refresh", "user"]

        assert actualResult == expectedResult

    def test_login_when_password_wrong_returns_401(
        self, client: TestClient, shelf_seed: dict
    ):
        response = client.post(
            "/auth/login",
            json={"username": "owner", "password": "nope"},
        )

        actualResult = response.status_code
        expectedResult = 401

        assert actualResult == expectedResult


class TestJwtDecode:
    def test_decode_token_when_access_valid_returns_user_id(self, shelf_seed: dict):
        token = create_token(shelf_seed["owner_id"], "access")

        actualResult = decode_token(token, expected_type="access")["user_id"]
        expectedResult = shelf_seed["owner_id"]

        assert actualResult == expectedResult


class TestGetCurrentUserViaShelf:
    def test_available_owned_when_bearer_valid_returns_200(
        self, client: TestClient, shelf_seed: dict
    ):
        token = create_token(shelf_seed["owner_id"], "access")

        response = client.get(
            "/v1/shelves/available-owned",
            headers={"Authorization": f"Bearer {token}"},
        )

        actualResult = response.status_code
        expectedResult = 200

        assert actualResult == expectedResult

    def test_available_owned_when_no_token_returns_401(self, client: TestClient):
        response = client.get("/v1/shelves/available-owned")

        actualResult = response.status_code
        expectedResult = 401

        assert actualResult == expectedResult

    def test_available_owned_when_viewer_is_owner_excludes_own_shelf(
        self, client: TestClient, shelf_seed: dict
    ):
        token = create_token(shelf_seed["owner_id"], "access")

        response = client.get(
            "/v1/shelves/available-owned",
            headers={"Authorization": f"Bearer {token}"},
        )
        payload = response.json()

        actualResult = [item["id"] for item in payload.get("items", [])]
        expectedResult: list[int] = []

        assert actualResult == expectedResult


class TestRegister:
    def test_register_when_skip_activation_returns_token_pair(
        self, client: TestClient, shelf_seed: dict
    ):
        response = client.post(
            "/auth/register",
            json={
                "username": "newbie",
                "email": "newbie@example.com",
                "password": "secret123",
            },
        )

        actualResult = (
            response.status_code == 201
            and "access" in response.json()
            and response.json()["user"]["username"] == "newbie"
        )
        expectedResult = True

        assert actualResult == expectedResult


class TestRefresh:
    def test_refresh_when_refresh_valid_returns_new_access(
        self, client: TestClient, shelf_seed: dict
    ):
        refresh = create_token(shelf_seed["owner_id"], "refresh")

        response = client.post("/auth/refresh", json={"refresh": refresh})

        actualResult = (
            response.status_code == 200 and bool(response.json().get("access"))
        )
        expectedResult = True

        assert actualResult == expectedResult
