"""
Repository-level tests for Book catalog search / subjects — live Django test DB.

Naming: test_<method>_<whenCondition>_<returnsExpected>
Assert style: actualResult / expectedResult; one assert per test.
"""
from __future__ import annotations

from django.test import TestCase

from mainApp.book_subjects import catalog_subjects, invalidate_catalog_subjects_cache
from mainApp.feed_search import apply_book_search, search_active
from mainApp.models import Book


class BookSearchRepositoryTestBase(TestCase):
    def setUp(self):
        invalidate_catalog_subjects_cache()
        self.fiction = Book.objects.create(
            isbn="9780001000001",
            title="Alpha Fiction",
            authors="Author A",
            publisher="Pub One",
            publish_date="2010",
            language="eng",
            subjects=["Fiction", "Adventure"],
            min_readers_age=8,
            max_readers_age=14,
        )
        self.science = Book.objects.create(
            isbn="9780001000002",
            title="Beta Science",
            authors="Author B",
            publisher="Pub Two",
            publish_date="2020-05",
            language="ukr",
            subjects=["Science"],
            min_readers_age=12,
            max_readers_age=18,
        )
        self.kids = Book.objects.create(
            isbn="9780001000003",
            title="Gamma Kids",
            authors="Author C",
            publisher="Pub One",
            publish_date="2015",
            language="eng",
            subjects=["Fiction", "Children"],
            min_readers_age=0,
            max_readers_age=7,
        )


class CatalogSubjectsTests(BookSearchRepositoryTestBase):
    def test_catalog_subjects_when_books_have_subjects_returns_sorted_unique(self):
        actualResult = catalog_subjects(use_cache=False)
        expectedResult = ["Adventure", "Children", "Fiction", "Science"]

        self.assertEqual(actualResult, expectedResult)

    def test_catalog_subjects_when_duplicate_case_keeps_first_seen_label(self):
        Book.objects.create(
            isbn="9780001000004",
            title="Dup",
            subjects=["fiction"],
        )

        actualResult = catalog_subjects(use_cache=False)
        expectedResult = ["Adventure", "Children", "Fiction", "Science"]

        self.assertEqual(actualResult, expectedResult)

    def test_catalog_subjects_when_empty_subjects_ignored_returns_existing(self):
        Book.objects.create(isbn="9780001000005", title="Empty", subjects=[])

        actualResult = catalog_subjects(use_cache=False)
        expectedResult = ["Adventure", "Children", "Fiction", "Science"]

        self.assertEqual(actualResult, expectedResult)


class ApplyBookSearchSubjectTests(BookSearchRepositoryTestBase):
    def test_apply_book_search_when_subject_fiction_returns_matching_isbns(self):
        actualResult = list(
            apply_book_search(params={"subject": "Fiction"}).values_list(
                "isbn", flat=True
            )
        )
        expectedResult = ["9780001000001", "9780001000003"]

        self.assertEqual(actualResult, expectedResult)

    def test_apply_book_search_when_subject_unknown_returns_empty(self):
        actualResult = list(
            apply_book_search(params={"subject": "NoSuchTheme"}).values_list(
                "isbn", flat=True
            )
        )
        expectedResult: list[str] = []

        self.assertEqual(actualResult, expectedResult)

    def test_apply_book_search_when_theme_alias_returns_matching_isbn(self):
        actualResult = list(
            apply_book_search(params={"theme": "Science"}).values_list(
                "isbn", flat=True
            )
        )
        expectedResult = ["9780001000002"]

        self.assertEqual(actualResult, expectedResult)


class ApplyBookSearchYearTests(BookSearchRepositoryTestBase):
    def test_apply_book_search_when_year_from_to_returns_books_in_range(self):
        actualResult = list(
            apply_book_search(
                params={"year_from": "2014", "year_to": "2016"}
            ).values_list("isbn", flat=True)
        )
        expectedResult = ["9780001000003"]

        self.assertEqual(actualResult, expectedResult)

    def test_apply_book_search_when_year_from_only_returns_later_books(self):
        actualResult = set(
            apply_book_search(params={"year_from": "2015"}).values_list(
                "isbn", flat=True
            )
        )
        expectedResult = {"9780001000002", "9780001000003"}

        self.assertEqual(actualResult, expectedResult)


class ApplyBookSearchLanguageTests(BookSearchRepositoryTestBase):
    def test_apply_book_search_when_language_eng_returns_english_books(self):
        actualResult = list(
            apply_book_search(params={"language": "eng"}).values_list(
                "isbn", flat=True
            )
        )
        expectedResult = ["9780001000001", "9780001000003"]

        self.assertEqual(actualResult, expectedResult)


class ApplyBookSearchAgeTests(BookSearchRepositoryTestBase):
    def test_apply_book_search_when_age_min_10_excludes_kids_only(self):
        actualResult = set(
            apply_book_search(params={"age_min": "10"}).values_list(
                "isbn", flat=True
            )
        )
        expectedResult = {"9780001000001", "9780001000002"}

        self.assertEqual(actualResult, expectedResult)

    def test_apply_book_search_when_age_max_7_returns_kids(self):
        actualResult = list(
            apply_book_search(params={"age_max": "7"}).values_list(
                "isbn", flat=True
            )
        )
        expectedResult = ["9780001000003"]

        self.assertEqual(actualResult, expectedResult)


class ApplyBookSearchCombinedTests(BookSearchRepositoryTestBase):
    def test_apply_book_search_when_subject_and_language_returns_intersection(self):
        actualResult = list(
            apply_book_search(
                params={"subject": "Fiction", "language": "eng"}
            ).values_list("isbn", flat=True)
        )
        expectedResult = ["9780001000001", "9780001000003"]

        self.assertEqual(actualResult, expectedResult)

    def test_apply_book_search_when_title_query_returns_matching_book(self):
        actualResult = list(
            apply_book_search(params={"q": "Beta"}).values_list("isbn", flat=True)
        )
        expectedResult = ["9780001000002"]

        self.assertEqual(actualResult, expectedResult)


class SearchActiveRepositorySmokeTests(BookSearchRepositoryTestBase):
    def test_search_active_when_subject_param_returns_true(self):
        actualResult = search_active({"subject": "Fiction"})
        expectedResult = True

        self.assertEqual(actualResult, expectedResult)

    def test_search_active_when_empty_params_returns_false(self):
        actualResult = search_active({})
        expectedResult = False

        self.assertEqual(actualResult, expectedResult)
