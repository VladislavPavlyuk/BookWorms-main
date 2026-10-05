"""
Repository-level tests — run against a live Django test DB
(SQLite locally, or Postgres when POSTGRES_HOST is set / test container).

Naming: test_<method>_<whenCondition>_<returnsExpected>
Assert style: actualResult / expectedResult; one assert per test.
Higher layers should mock ILibraryRepository.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from mainApp.library_repo import LibraryRepository
from mainApp.models import (
    Book,
    BookCopy,
    Library,
    LibraryAction,
    LibraryMembership,
    Shelf,
)

User = get_user_model()


class LibraryRepositoryTestBase(TestCase):
    def setUp(self):
        self.repo = LibraryRepository()
        self.admin = User.objects.create_user(username="lib_admin", password="x")
        self.member = User.objects.create_user(username="lib_member", password="x")
        self.book = Book.objects.create(isbn="9780000000101", title="Lib Book")
        self.library = Library.objects.create(
            name="Test Shared",
            admin=self.admin,
        )
        LibraryMembership.objects.create(
            library=self.library,
            user=self.admin,
            role=LibraryMembership.Role.ADMIN,
        )
        LibraryMembership.objects.create(
            library=self.library,
            user=self.member,
            role=LibraryMembership.Role.MEMBER,
        )
        self.copy = BookCopy.objects.create(
            book=self.book,
            owner=self.admin,
            library=self.library,
            added_by=self.member,
        )
        self.owner_shelf = Shelf.objects.create(
            user=self.member,
            book=self.book,
            copy=self.copy,
        )


class FindMembershipForUserTests(LibraryRepositoryTestBase):
    def test_find_membership_for_user_when_member_exists_returns_library(self):
        mem = self.repo.find_membership_for_user(self.member.id)

        actualResult = mem.library_id if mem else None
        expectedResult = self.library.id

        self.assertEqual(actualResult, expectedResult)

    def test_find_membership_for_user_when_no_membership_returns_none(self):
        stranger = User.objects.create_user(username="stranger", password="x")

        actualResult = self.repo.find_membership_for_user(stranger.id)
        expectedResult = None

        self.assertEqual(actualResult, expectedResult)


class CreatePersonalLibraryTests(LibraryRepositoryTestBase):
    def test_create_personal_library_when_orphan_copy_attaches_to_library(self):
        user = User.objects.create_user(username="solo", password="x")
        book = Book.objects.create(isbn="9780000000102", title="Solo")
        orphan = BookCopy.objects.create(book=book, owner=user, library=None)

        lib = self.repo.create_personal_library(user)
        orphan.refresh_from_db()

        actualResult = orphan.library_id
        expectedResult = lib.id

        self.assertEqual(actualResult, expectedResult)

    def test_create_personal_library_when_new_user_returns_admin_membership(self):
        user = User.objects.create_user(username="solo2", password="x")

        lib = self.repo.create_personal_library(user)
        mem = LibraryMembership.objects.get(user=user)

        actualResult = (mem.library_id, mem.role, lib.admin_id)
        expectedResult = (lib.id, LibraryMembership.Role.ADMIN, user.id)

        self.assertEqual(actualResult, expectedResult)


class CountMembershipsTests(LibraryRepositoryTestBase):
    def test_count_memberships_when_shared_library_returns_two(self):
        actualResult = self.repo.count_memberships(self.library.id)
        expectedResult = 2

        self.assertEqual(actualResult, expectedResult)


class CountIsbnTests(LibraryRepositoryTestBase):
    def test_count_isbn_when_one_copy_returns_one(self):
        actualResult = self.repo.count_isbn(self.library.id, self.book.id)
        expectedResult = 1

        self.assertEqual(actualResult, expectedResult)

    def test_count_isbn_when_no_copies_returns_zero(self):
        other = Book.objects.create(isbn="9780000000103", title="Other")

        actualResult = self.repo.count_isbn(self.library.id, other.id)
        expectedResult = 0

        self.assertEqual(actualResult, expectedResult)


class FindIsbnCountRowsTests(LibraryRepositoryTestBase):
    def test_find_isbn_count_rows_when_copy_exists_returns_book_row(self):
        rows = self.repo.find_isbn_count_rows(self.library.id)

        actualResult = [(r["book_id"], r["n"], r["book__isbn"]) for r in rows]
        expectedResult = [(self.book.id, 1, "9780000000101")]

        self.assertEqual(actualResult, expectedResult)


class FindOwnedShelfByIdTests(LibraryRepositoryTestBase):
    def test_find_owned_shelf_by_id_when_owned_returns_shelf(self):
        actualResult = self.repo.find_owned_shelf_by_id(self.owner_shelf.id)
        expectedResult = self.owner_shelf

        self.assertEqual(actualResult, expectedResult)

    def test_find_owned_shelf_by_id_when_loan_row_returns_none(self):
        borrower = User.objects.create_user(username="borrower", password="x")
        loan = Shelf.objects.create(
            user=borrower,
            book=self.book,
            copy=self.copy,
            borrowed_from=self.member,
        )

        actualResult = self.repo.find_owned_shelf_by_id(loan.id)
        expectedResult = None

        self.assertEqual(actualResult, expectedResult)


class FindShelfForRemovalTests(LibraryRepositoryTestBase):
    def test_find_shelf_for_removal_when_exists_returns_shelf(self):
        found = self.repo.find_shelf_for_removal(self.owner_shelf.id)

        actualResult = found.pk if found else None
        expectedResult = self.owner_shelf.pk

        self.assertEqual(actualResult, expectedResult)

    def test_find_shelf_for_removal_when_missing_returns_none(self):
        actualResult = self.repo.find_shelf_for_removal(999999)
        expectedResult = None

        self.assertEqual(actualResult, expectedResult)


class FindOwnedShelvesForCopyTests(LibraryRepositoryTestBase):
    def test_find_owned_shelves_for_copy_when_owned_row_exists_returns_pk(self):
        rows = self.repo.find_owned_shelves_for_copy(self.copy.id)

        actualResult = [r.pk for r in rows]
        expectedResult = [self.owner_shelf.pk]

        self.assertEqual(actualResult, expectedResult)


class DetachCopyFromLibraryTests(LibraryRepositoryTestBase):
    def test_detach_copy_from_library_when_attached_sets_library_none(self):
        self.repo.detach_copy_from_library(self.copy.id)
        self.copy.refresh_from_db()

        actualResult = self.copy.library_id
        expectedResult = None

        self.assertEqual(actualResult, expectedResult)


class CreateActionTests(LibraryRepositoryTestBase):
    def test_create_action_when_remove_copy_returns_pending(self):
        action = self.repo.create_action(
            library=self.library,
            initiator=self.member,
            action_type=LibraryAction.ActionType.REMOVE_COPY,
            payload={"shelf_id": self.owner_shelf.id, "title": "Lib Book"},
        )

        actualResult = (action.status, action.action_type, action.initiator_id)
        expectedResult = (
            LibraryAction.Status.PENDING,
            LibraryAction.ActionType.REMOVE_COPY,
            self.member.id,
        )

        self.assertEqual(actualResult, expectedResult)


class FindPendingActionByIdTests(LibraryRepositoryTestBase):
    def test_find_pending_action_by_id_when_pending_returns_action(self):
        action = LibraryAction.objects.create(
            library=self.library,
            initiator=self.member,
            action_type=LibraryAction.ActionType.LISTING,
            payload={"status": "available"},
        )

        found = self.repo.find_pending_action_by_id(action.id)

        actualResult = found.id if found else None
        expectedResult = action.id

        self.assertEqual(actualResult, expectedResult)

    def test_find_pending_action_by_id_when_approved_returns_none(self):
        action = LibraryAction.objects.create(
            library=self.library,
            initiator=self.member,
            action_type=LibraryAction.ActionType.LISTING,
            status=LibraryAction.Status.APPROVED,
            payload={},
        )

        actualResult = self.repo.find_pending_action_by_id(action.id)
        expectedResult = None

        self.assertEqual(actualResult, expectedResult)


class FindPendingActionsBetweenTests(LibraryRepositoryTestBase):
    def test_find_pending_actions_for_admin_from_when_pending_returns_action(self):
        action = LibraryAction.objects.create(
            library=self.library,
            initiator=self.member,
            action_type=LibraryAction.ActionType.REMOVE_COPY,
            payload={"title": "Lib Book"},
        )

        rows = self.repo.find_pending_actions_for_admin_from(
            self.admin.id, self.member.id
        )

        actualResult = [r.id for r in rows]
        expectedResult = [action.id]

        self.assertEqual(actualResult, expectedResult)

    def test_find_pending_actions_by_initiator_to_admin_when_pending_returns_action(
        self,
    ):
        action = LibraryAction.objects.create(
            library=self.library,
            initiator=self.member,
            action_type=LibraryAction.ActionType.ADD_COPY,
            payload={"isbn": "9780000000101"},
        )

        rows = self.repo.find_pending_actions_by_initiator_to_admin(
            self.member.id, self.admin.id
        )

        actualResult = [r.id for r in rows]
        expectedResult = [action.id]

        self.assertEqual(actualResult, expectedResult)


class FindActiveLoansByCopyTests(LibraryRepositoryTestBase):
    def test_find_active_loans_by_copy_when_loan_exists_returns_loan_shelf(self):
        borrower = User.objects.create_user(username="loaner", password="x")
        loan = Shelf.objects.create(
            user=borrower,
            book=self.book,
            copy=self.copy,
            borrowed_from=self.admin,
        )

        actualResult = self.repo.find_active_loans_by_copy(self.library.id)[
            self.copy.id
        ].pk
        expectedResult = loan.pk

        self.assertEqual(actualResult, expectedResult)

    def test_find_active_loans_by_copy_when_no_loan_returns_empty(self):
        actualResult = self.repo.find_active_loans_by_copy(self.library.id)
        expectedResult: dict = {}

        self.assertEqual(actualResult, expectedResult)
