"""
Service-level tests for feed_profile helpers (no live DB).

Naming: test_<method>_<whenCondition>_<returnsExpected>
Assert style: actualResult / expectedResult; one assert per test.
"""
from __future__ import annotations

from django.test import SimpleTestCase

from mainApp.feed_profile import (
    _clamp_reader_age,
    _norm_subjects,
    persona_match_q,
)
from mainApp.models import READER_AGE_MAX


class NormSubjectsTests(SimpleTestCase):
    def test_norm_subjects_when_duplicates_returns_unique_preserving_order(self):
        actualResult = _norm_subjects(["Fiction", " fiction ", "Science", ""])
        expectedResult = ["Fiction", "Science"]

        self.assertEqual(actualResult, expectedResult)

    def test_norm_subjects_when_not_list_returns_empty(self):
        actualResult = _norm_subjects("Fiction")
        expectedResult: list[str] = []

        self.assertEqual(actualResult, expectedResult)

    def test_norm_subjects_when_none_returns_empty(self):
        actualResult = _norm_subjects(None)
        expectedResult: list[str] = []

        self.assertEqual(actualResult, expectedResult)


class ClampReaderAgeTests(SimpleTestCase):
    def test_clamp_reader_age_when_above_max_returns_reader_age_max(self):
        actualResult = _clamp_reader_age(35)
        expectedResult = READER_AGE_MAX

        self.assertEqual(actualResult, expectedResult)

    def test_clamp_reader_age_when_negative_returns_zero(self):
        actualResult = _clamp_reader_age(-3)
        expectedResult = 0

        self.assertEqual(actualResult, expectedResult)

    def test_clamp_reader_age_when_in_range_returns_same(self):
        actualResult = _clamp_reader_age(10)
        expectedResult = 10

        self.assertEqual(actualResult, expectedResult)


class PersonaMatchQTests(SimpleTestCase):
    def test_persona_match_q_when_no_age_and_no_subjects_returns_none(self):
        actualResult = persona_match_q(age=None, subjects=[])
        expectedResult = None

        self.assertEqual(actualResult, expectedResult)

    def test_persona_match_q_when_age_only_returns_q(self):
        actualResult = persona_match_q(age=8, subjects=[]) is not None
        expectedResult = True

        self.assertEqual(actualResult, expectedResult)

    def test_persona_match_q_when_subjects_only_returns_q(self):
        actualResult = persona_match_q(age=None, subjects=["Fiction"]) is not None
        expectedResult = True

        self.assertEqual(actualResult, expectedResult)

    def test_persona_match_q_when_both_set_returns_q(self):
        actualResult = persona_match_q(age=10, subjects=["Fiction"]) is not None
        expectedResult = True

        self.assertEqual(actualResult, expectedResult)
