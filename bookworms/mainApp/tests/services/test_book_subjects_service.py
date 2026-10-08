"""
Service-level tests for book_subjects helpers (no live DB).

Naming: test_<method>_<whenCondition>_<returnsExpected>
Assert style: actualResult / expectedResult; one assert per test.
"""
from __future__ import annotations

from unittest.mock import patch

from django.db.models import Q
from django.test import SimpleTestCase

from mainApp.book_subjects import _normalize_subject, subjects_contain_q


class NormalizeSubjectTests(SimpleTestCase):
    def test_normalize_subject_when_padded_string_returns_stripped(self):
        actualResult = _normalize_subject("  Fiction  ")
        expectedResult = "Fiction"

        self.assertEqual(actualResult, expectedResult)

    def test_normalize_subject_when_none_returns_empty(self):
        actualResult = _normalize_subject(None)
        expectedResult = ""

        self.assertEqual(actualResult, expectedResult)

    def test_normalize_subject_when_non_string_returns_stripped_str(self):
        actualResult = _normalize_subject(42)
        expectedResult = "42"

        self.assertEqual(actualResult, expectedResult)


class SubjectsContainQTests(SimpleTestCase):
    def test_subjects_contain_q_when_empty_subject_returns_empty_match(self):
        actualResult = subjects_contain_q("  ")
        expectedResult = Q(pk__in=[])

        self.assertEqual(actualResult, expectedResult)

    @patch("mainApp.book_subjects.connection")
    def test_subjects_contain_q_when_postgresql_returns_contains_lookup(self, conn):
        conn.vendor = "postgresql"

        actualResult = subjects_contain_q("Fiction")
        expectedResult = Q(subjects__contains=["Fiction"])

        self.assertEqual(actualResult, expectedResult)

    @patch("mainApp.book_subjects.connection")
    def test_subjects_contain_q_when_sqlite_returns_icontains_quoted(self, conn):
        conn.vendor = "sqlite"

        actualResult = subjects_contain_q("Fiction")
        expectedResult = Q(subjects__icontains='"Fiction"')

        self.assertEqual(actualResult, expectedResult)
