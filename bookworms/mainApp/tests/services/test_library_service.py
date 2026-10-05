"""
Service-level tests — ILibraryRepository is mocked (no live DB).

Naming: test_<method>_<whenCondition>_<returnsExpected>
Assert style: actualResult / expectedResult; one assert per test.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from mainApp.library_repo import reset_library_defaults, set_library_repository
from mainApp.library_service import (
    LibraryError,
    _action_needs_admin,
    _library_is_shared,
    _owners_to_inform,
    count_isbn_in_library,
    ensure_personal_library,
    get_removable_shelf,
    is_library_admin,
    library_active_loans_by_copy,
    library_isbn_counts,
    remove_library_copy,
    request_remove_copy,
)
from mainApp.models import LibraryAction


class LibraryServiceTestBase(SimpleTestCase):
    def setUp(self):
        self.repo = MagicMock()
        set_library_repository(self.repo)
        self.addCleanup(reset_library_defaults)


class EnsurePersonalLibraryTests(LibraryServiceTestBase):
    def test_ensure_personal_library_when_membership_exists_returns_library(self):
        user = MagicMock(id=1)
        lib = MagicMock()
        mem = MagicMock(library=lib)
        self.repo.find_membership_for_user.return_value = mem

        actualResult = ensure_personal_library(user)
        expectedResult = lib

        self.assertEqual(actualResult, expectedResult)

    def test_ensure_personal_library_when_no_membership_creates_library(self):
        user = MagicMock(id=2)
        lib = MagicMock()
        self.repo.find_membership_for_user.return_value = None
        self.repo.create_personal_library.return_value = lib

        actualResult = ensure_personal_library(user)
        expectedResult = lib

        self.assertEqual(actualResult, expectedResult)


class CountIsbnInLibraryTests(LibraryServiceTestBase):
    def test_count_isbn_in_library_when_repo_returns_count_returns_same(self):
        lib = MagicMock(id=10)
        book = MagicMock(id=20)
        self.repo.count_isbn.return_value = 3

        actualResult = count_isbn_in_library(lib, book)
        expectedResult = 3

        self.assertEqual(actualResult, expectedResult)


class LibraryIsbnCountsTests(LibraryServiceTestBase):
    def test_library_isbn_counts_when_rows_exist_maps_by_isbn(self):
        lib = MagicMock(id=10)
        self.repo.find_isbn_count_rows.return_value = [
            {
                "book_id": 5,
                "book__isbn": "9781",
                "book__title": "T",
                "n": 2,
            }
        ]

        actualResult = library_isbn_counts(lib)
        expectedResult = {
            "9781": {"isbn": "9781", "title": "T", "book_id": 5, "count": 2}
        }

        self.assertEqual(actualResult, expectedResult)


class IsLibraryAdminTests(LibraryServiceTestBase):
    def test_is_library_admin_when_user_is_admin_returns_true(self):
        user = MagicMock(id=1)
        lib = MagicMock(admin_id=1)

        actualResult = is_library_admin(user, lib)
        expectedResult = True

        self.assertEqual(actualResult, expectedResult)

    def test_is_library_admin_when_user_is_member_returns_false(self):
        user = MagicMock(id=2)
        lib = MagicMock(admin_id=1)

        actualResult = is_library_admin(user, lib)
        expectedResult = False

        self.assertEqual(actualResult, expectedResult)


class LibraryActiveLoansByCopyTests(LibraryServiceTestBase):
    def test_library_active_loans_by_copy_when_repo_returns_map_returns_same(self):
        lib = MagicMock(id=10)
        loan = MagicMock()
        self.repo.find_active_loans_by_copy.return_value = {5: loan}

        actualResult = library_active_loans_by_copy(lib)
        expectedResult = {5: loan}

        self.assertEqual(actualResult, expectedResult)


class LibraryIsSharedTests(LibraryServiceTestBase):
    def test_library_is_shared_when_two_members_returns_true(self):
        lib = MagicMock(id=1)
        self.repo.count_memberships.return_value = 2

        actualResult = _library_is_shared(lib)
        expectedResult = True

        self.assertEqual(actualResult, expectedResult)

    def test_library_is_shared_when_one_member_returns_false(self):
        lib = MagicMock(id=1)
        self.repo.count_memberships.return_value = 1

        actualResult = _library_is_shared(lib)
        expectedResult = False

        self.assertEqual(actualResult, expectedResult)


class ActionNeedsAdminTests(LibraryServiceTestBase):
    def test_action_needs_admin_when_user_is_admin_returns_false(self):
        user = MagicMock(id=1)
        lib = MagicMock(id=10, admin_id=1)

        actualResult = _action_needs_admin(user, lib)
        expectedResult = False

        self.assertEqual(actualResult, expectedResult)

    def test_action_needs_admin_when_member_of_shared_returns_true(self):
        user = MagicMock(id=2)
        lib = MagicMock(id=10, admin_id=1)
        self.repo.count_memberships.return_value = 2

        actualResult = _action_needs_admin(user, lib)
        expectedResult = True

        self.assertEqual(actualResult, expectedResult)


class GetRemovableShelfTests(LibraryServiceTestBase):
    def test_get_removable_shelf_when_own_shelf_returns_shelf(self):
        user = MagicMock(id=1)
        shelf = MagicMock(user_id=1, pk=10, copy_id=None)
        self.repo.find_owned_shelf_by_id.return_value = shelf

        actualResult = get_removable_shelf(user, 10)
        expectedResult = shelf

        self.assertEqual(actualResult, expectedResult)

    def test_get_removable_shelf_when_missing_raises_library_error(self):
        user = MagicMock(id=1)
        self.repo.find_owned_shelf_by_id.return_value = None

        with self.assertRaises(LibraryError) as ctx:
            get_removable_shelf(user, 99)

        actualResult = str(ctx.exception)
        expectedResult = "Запис не знайдено."

        self.assertEqual(actualResult, expectedResult)

    def test_get_removable_shelf_when_admin_of_copy_library_returns_shelf(self):
        user = MagicMock(id=1)
        lib = MagicMock(id=50, admin_id=1)
        copy = MagicMock(library_id=50)
        shelf = MagicMock(user_id=2, pk=10, copy_id=7, copy=copy)
        self.repo.find_owned_shelf_by_id.return_value = shelf
        self.repo.find_membership_for_user.return_value = MagicMock(library=lib)

        actualResult = get_removable_shelf(user, 10)
        expectedResult = shelf

        self.assertEqual(actualResult, expectedResult)

    def test_get_removable_shelf_when_not_owner_nor_admin_raises(self):
        user = MagicMock(id=3)
        lib = MagicMock(id=50, admin_id=1)
        copy = MagicMock(library_id=50)
        shelf = MagicMock(user_id=2, pk=10, copy_id=7, copy=copy)
        self.repo.find_owned_shelf_by_id.return_value = shelf
        self.repo.find_membership_for_user.return_value = MagicMock(library=lib)

        with self.assertRaises(LibraryError) as ctx:
            get_removable_shelf(user, 10)

        actualResult = str(ctx.exception)
        expectedResult = "Немає права видалити цей примірник."

        self.assertEqual(actualResult, expectedResult)


class OwnersToInformTests(SimpleTestCase):
    def test_owners_to_inform_when_added_by_differs_returns_contributor(self):
        actor = MagicMock(id=1)
        contributor = MagicMock(id=2)
        lib = MagicMock(admin_id=1)
        owner = MagicMock(id=1)
        copy = MagicMock(added_by=contributor, owner=owner, library=lib)
        shelf = MagicMock(copy=copy, user=actor)

        actualResult = [u.id for u in _owners_to_inform(shelf, actor)]
        expectedResult = [2]

        self.assertEqual(actualResult, expectedResult)


class RemoveLibraryCopyTests(LibraryServiceTestBase):
    @patch("mainApp.library_service._notify")
    def test_remove_library_copy_when_copy_attached_detaches_library(self, _notify):
        with patch("mainApp.exchange.copies.remove_owned_shelf") as rem:
            actor = MagicMock(id=1, username="admin")
            copy = MagicMock(id=9, pk=9, library_id=50, book_id=None)
            shelf = MagicMock(pk=10, copy=copy, book_id=None)
            owned = MagicMock()
            self.repo.find_shelf_for_removal.return_value = shelf
            self.repo.find_owned_shelves_for_copy.return_value = [owned]
            self.repo.detach_copy_from_library.return_value = 1

            remove_library_copy(actor, shelf, notify_owners=False)

            actualResult = (
                self.repo.detach_copy_from_library.call_args[0][0],
                rem.call_count,
            )
            expectedResult = (9, 1)

            self.assertEqual(actualResult, expectedResult)


class RequestRemoveCopyTests(LibraryServiceTestBase):
    @patch("mainApp.library_service._notify")
    @patch("mainApp.library_service.remove_library_copy")
    def test_request_remove_copy_when_admin_removes_immediately_returns_shelf(
        self, remove_fn, _notify
    ):
        user = MagicMock(id=1, username="admin")
        lib = MagicMock(id=50, admin_id=1)
        copy = MagicMock(library_id=50, id=9, book_id=1, book=MagicMock(title="T"))
        shelf = MagicMock(id=10, copy=copy)
        self.repo.find_membership_for_user.return_value = MagicMock(library=lib)
        self.repo.count_memberships.return_value = 2

        actualResult = request_remove_copy(user, shelf)
        expectedResult = shelf

        self.assertEqual(actualResult, expectedResult)

    @patch("mainApp.library_service._notify")
    def test_request_remove_copy_when_member_of_shared_returns_action(self, notify):
        user = MagicMock(id=2, username="member")
        admin = MagicMock(id=1)
        lib = MagicMock(id=50, admin_id=1, admin=admin)
        copy = MagicMock(library_id=50, id=9, book_id=1, book=MagicMock(title="T"))
        shelf = MagicMock(id=10, copy=copy)
        action = MagicMock(spec=LibraryAction)
        self.repo.find_membership_for_user.return_value = MagicMock(library=lib)
        self.repo.count_memberships.return_value = 2
        self.repo.create_action.return_value = action

        actualResult = request_remove_copy(user, shelf)
        expectedResult = action

        self.assertEqual(actualResult, expectedResult)

    @patch("mainApp.library_service.remove_library_copy")
    def test_request_remove_copy_when_foreign_library_raises(self, _remove):
        user = MagicMock(id=1)
        lib = MagicMock(id=50, admin_id=1)
        copy = MagicMock(library_id=99)
        shelf = MagicMock(copy=copy)
        self.repo.find_membership_for_user.return_value = MagicMock(library=lib)

        with self.assertRaises(LibraryError) as ctx:
            request_remove_copy(user, shelf)

        actualResult = str(ctx.exception)
        expectedResult = "Примірник не з вашої бібліотеки."

        self.assertEqual(actualResult, expectedResult)
