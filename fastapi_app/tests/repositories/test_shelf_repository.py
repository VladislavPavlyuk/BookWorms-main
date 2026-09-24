"""
Repository-level tests — live Postgres (docker-compose.test.yml).

Naming: test_<method>_<whenCondition>_<returnsExpected>
Assert style: actualResult / expectedResult; one assert per test.
Higher layers should mock the shelf repository functions / port.
"""
from __future__ import annotations

from sqlalchemy.engine import Connection

from fastapi_app.repositories import shelf as shelf_repo
from fastapi_app.tests.repositories.seed_helpers import lend_copy


class TestFindAvailableOwned:
    def test_find_available_owned_when_copy_free_returns_owner_shelf_id(
        self, conn: Connection, shelf_seed: dict
    ):
        rows = shelf_repo.find_available_owned(conn)

        actualResult = [row["id"] for row in rows]
        expectedResult = [shelf_seed["owner_shelf_id"]]

        assert actualResult == expectedResult

    def test_find_available_owned_when_copy_lent_returns_empty(
        self, conn: Connection, shelf_seed: dict
    ):
        lend_copy(conn, shelf_seed)

        actualResult = [row["id"] for row in shelf_repo.find_available_owned(conn)]
        expectedResult: list[int] = []

        assert actualResult == expectedResult

    def test_find_available_owned_when_exclude_owner_returns_empty(
        self, conn: Connection, shelf_seed: dict
    ):
        rows = shelf_repo.find_available_owned(
            conn, exclude_user_id=shelf_seed["owner_id"]
        )

        actualResult = [row["id"] for row in rows]
        expectedResult: list[int] = []

        assert actualResult == expectedResult


class TestFindPhysicalPresence:
    def test_find_physical_presence_when_copy_free_returns_owner_shelf_id(
        self, conn: Connection, shelf_seed: dict
    ):
        rows = shelf_repo.find_physical_presence(conn)

        actualResult = [row["id"] for row in rows]
        expectedResult = [shelf_seed["owner_shelf_id"]]

        assert actualResult == expectedResult

    def test_find_physical_presence_when_copy_lent_returns_borrower_shelf_id(
        self, conn: Connection, shelf_seed: dict
    ):
        loan_shelf_id = lend_copy(conn, shelf_seed)

        actualResult = [row["id"] for row in shelf_repo.find_physical_presence(conn)]
        expectedResult = [loan_shelf_id]

        assert actualResult == expectedResult

    def test_find_physical_presence_when_exclude_borrower_returns_empty(
        self, conn: Connection, shelf_seed: dict
    ):
        lend_copy(conn, shelf_seed)

        rows = shelf_repo.find_physical_presence(
            conn, exclude_user_id=shelf_seed["borrower_id"]
        )

        actualResult = [row["id"] for row in rows]
        expectedResult: list[int] = []

        assert actualResult == expectedResult
