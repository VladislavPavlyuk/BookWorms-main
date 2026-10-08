"""
Service-level tests for feed_search helpers (no live DB).

Naming: test_<method>_<whenCondition>_<returnsExpected>
Assert style: actualResult / expectedResult; one assert per test.
"""
from __future__ import annotations

from django.test import SimpleTestCase

from mainApp.feed_search import (
    _clamp_year,
    _int_or_none,
    _year_range_q,
    advanced_active,
    search_active,
)


class IntOrNoneTests(SimpleTestCase):
    def test_int_or_none_when_valid_string_returns_int(self):
        actualResult = _int_or_none("42")
        expectedResult = 42

        self.assertEqual(actualResult, expectedResult)

    def test_int_or_none_when_empty_string_returns_none(self):
        actualResult = _int_or_none("")
        expectedResult = None

        self.assertEqual(actualResult, expectedResult)

    def test_int_or_none_when_invalid_returns_none(self):
        actualResult = _int_or_none("x")
        expectedResult = None

        self.assertEqual(actualResult, expectedResult)


class ClampYearTests(SimpleTestCase):
    def test_clamp_year_when_below_min_returns_min(self):
        actualResult = _clamp_year(500)
        expectedResult = 1000

        self.assertEqual(actualResult, expectedResult)

    def test_clamp_year_when_above_max_returns_max(self):
        actualResult = _clamp_year(9999)
        expectedResult = 2100

        self.assertEqual(actualResult, expectedResult)

    def test_clamp_year_when_none_returns_none(self):
        actualResult = _clamp_year(None)
        expectedResult = None

        self.assertEqual(actualResult, expectedResult)


class YearRangeQTests(SimpleTestCase):
    def test_year_range_q_when_both_none_returns_none(self):
        actualResult = _year_range_q(None, None)
        expectedResult = None

        self.assertEqual(actualResult, expectedResult)

    def test_year_range_q_when_from_set_returns_q_object(self):
        actualResult = _year_range_q(2010, None) is not None
        expectedResult = True

        self.assertEqual(actualResult, expectedResult)


class SearchActiveTests(SimpleTestCase):
    def test_search_active_when_subject_set_returns_true(self):
        actualResult = search_active({"subject": "Fiction"})
        expectedResult = True

        self.assertEqual(actualResult, expectedResult)

    def test_search_active_when_year_from_set_returns_true(self):
        actualResult = search_active({"year_from": "2000"})
        expectedResult = True

        self.assertEqual(actualResult, expectedResult)

    def test_search_active_when_blank_values_returns_false(self):
        actualResult = search_active({"subject": "  ", "q": ""})
        expectedResult = False

        self.assertEqual(actualResult, expectedResult)


class AdvancedActiveTests(SimpleTestCase):
    def test_advanced_active_when_only_q_returns_false(self):
        actualResult = advanced_active({"q": "Harry"})
        expectedResult = False

        self.assertEqual(actualResult, expectedResult)

    def test_advanced_active_when_subject_set_returns_true(self):
        actualResult = advanced_active({"subject": "Fiction"})
        expectedResult = True

        self.assertEqual(actualResult, expectedResult)
