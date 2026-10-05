"""
Service-level tests for messaging helpers — ILibraryRepository mocked.

Naming: test_<method>_<whenCondition>_<returnsExpected>
Assert style: actualResult / expectedResult; one assert per test.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from django.test import SimpleTestCase

from mainApp.library_repo import reset_library_defaults, set_library_repository
from mainApp.messaging.thread import library_actions_with_partner
from mainApp.models import LibraryAction


class LibraryActionsWithPartnerTests(SimpleTestCase):
    def setUp(self):
        self.repo = MagicMock()
        set_library_repository(self.repo)
        self.addCleanup(reset_library_defaults)

    def test_library_actions_with_partner_when_pending_in_returns_row(self):
        user = MagicMock(id=1)
        initiator = MagicMock(username="member")
        library = MagicMock()
        library.display_name = "Shared"
        action = MagicMock(
            id=7,
            action_type=LibraryAction.ActionType.REMOVE_COPY,
            payload={"title": "Book", "count": 1},
            initiator=initiator,
            library=library,
        )
        action.get_action_type_display.return_value = "Прибрати примірник"
        self.repo.find_pending_actions_for_admin_from.return_value = [action]
        self.repo.find_pending_actions_by_initiator_to_admin.return_value = []

        incoming, _outgoing = library_actions_with_partner(user, partner_id=2)

        actualResult = incoming[0]["id"]
        expectedResult = 7

        self.assertEqual(actualResult, expectedResult)

    def test_library_actions_with_partner_when_none_returns_empty_lists(self):
        user = MagicMock(id=1)
        self.repo.find_pending_actions_for_admin_from.return_value = []
        self.repo.find_pending_actions_by_initiator_to_admin.return_value = []

        actualResult = library_actions_with_partner(user, partner_id=2)
        expectedResult = ([], [])

        self.assertEqual(actualResult, expectedResult)
