"""
Repository-level tests — run against a live Django test DB
(SQLite locally, or Postgres when POSTGRES_HOST is set / test container).

Naming: test_<method>_<whenCondition>_<returnsExpected>
Assert style: actualResult / expectedResult; one assert per test.
Higher layers should mock IShelfRepository.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from mainApp.exchange.repositories import ShelfRepository
from mainApp.models import Book, BookCopy, Shelf

User = get_user_model()


class ShelfRepositoryTestBase(TestCase):
    """Shared arrange helpers for shelf repository tests."""

    def setUp(self):
        self.repo = ShelfRepository()
        self.owner = User.objects.create_user(username="owner", password="x")
        self.borrower = User.objects.create_user(username="borrower", password="x")
        self.book = Book.objects.create(isbn="9780000000001", title="Test Book")
        self.copy = BookCopy.objects.create(book=self.book, owner=self.owner)
        self.owner_shelf = Shelf.objects.create(
            user=self.owner, book=self.book, copy=self.copy
        )

    def _lend_copy(self) -> Shelf:
        return Shelf.objects.create(
            user=self.borrower,
            book=self.book,
            copy=self.copy,
            borrowed_from=self.owner,
        )


class ExistsActiveLoanForCopyTests(ShelfRepositoryTestBase):
    def test_exists_active_loan_for_copy_when_loan_row_exists_returns_true(self):
        self._lend_copy()

        actualResult = self.repo.exists_active_loan_for_copy(self.copy.id)
        expectedResult = True

        self.assertEqual(actualResult, expectedResult)

    def test_exists_active_loan_for_copy_when_only_owner_row_returns_false(self):
        actualResult = self.repo.exists_active_loan_for_copy(self.copy.id)
        expectedResult = False

        self.assertEqual(actualResult, expectedResult)

    def test_exists_active_loan_for_copy_when_copy_id_is_none_returns_false(self):
        actualResult = self.repo.exists_active_loan_for_copy(None)
        expectedResult = False

        self.assertEqual(actualResult, expectedResult)


class FindAvailableOwnedTests(ShelfRepositoryTestBase):
    def test_find_available_owned_when_copy_free_returns_owner_shelf_pk(self):
        actualResult = list(
            self.repo.find_available_owned().values_list("pk", flat=True)
        )
        expectedResult = [self.owner_shelf.pk]

        self.assertEqual(actualResult, expectedResult)

    def test_find_available_owned_when_copy_lent_returns_empty(self):
        self._lend_copy()

        actualResult = list(
            self.repo.find_available_owned().values_list("pk", flat=True)
        )
        expectedResult: list[int] = []

        self.assertEqual(actualResult, expectedResult)

    def test_find_available_owned_when_exclude_owner_returns_empty(self):
        actualResult = list(
            self.repo.find_available_owned(exclude_user_id=self.owner.id).values_list(
                "pk", flat=True
            )
        )
        expectedResult: list[int] = []

        self.assertEqual(actualResult, expectedResult)


class FindPhysicalPresenceTests(ShelfRepositoryTestBase):
    def test_find_physical_presence_when_copy_free_includes_owner_shelf(self):
        actualResult = set(
            self.repo.find_physical_presence().values_list("pk", flat=True)
        )
        expectedResult = {self.owner_shelf.pk}

        self.assertEqual(actualResult, expectedResult)

    def test_find_physical_presence_when_copy_lent_includes_borrower_excludes_owner(self):
        loan_shelf = self._lend_copy()

        actualResult = set(
            self.repo.find_physical_presence().values_list("pk", flat=True)
        )
        expectedResult = {loan_shelf.pk}

        self.assertEqual(actualResult, expectedResult)

    def test_find_physical_presence_when_exclude_borrower_returns_empty(self):
        self._lend_copy()

        actualResult = list(
            self.repo.find_physical_presence(
                exclude_user_id=self.borrower.id
            ).values_list("pk", flat=True)
        )
        expectedResult: list[int] = []

        self.assertEqual(actualResult, expectedResult)


class FindLoanRowsByCopyIdsTests(ShelfRepositoryTestBase):
    def test_find_loan_rows_by_copy_ids_when_loan_exists_returns_loan_shelf(self):
        loan_shelf = self._lend_copy()

        actualResult = self.repo.find_loan_rows_by_copy_ids([self.copy.id])[
            self.copy.id
        ].pk
        expectedResult = loan_shelf.pk

        self.assertEqual(actualResult, expectedResult)

    def test_find_loan_rows_by_copy_ids_when_no_loan_returns_empty_dict(self):
        actualResult = self.repo.find_loan_rows_by_copy_ids([self.copy.id])
        expectedResult: dict = {}

        self.assertEqual(actualResult, expectedResult)


class FindOwnerShelfIdsByCopyIdsTests(ShelfRepositoryTestBase):
    def test_find_owner_shelf_ids_by_copy_ids_when_owner_row_exists_returns_pk(self):
        actualResult = self.repo.find_owner_shelf_ids_by_copy_ids([self.copy.id])[
            self.copy.id
        ]
        expectedResult = self.owner_shelf.pk

        self.assertEqual(actualResult, expectedResult)
