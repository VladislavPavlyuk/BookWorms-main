"""
Repository-level tests for profile-aware feed filtering — live Django test DB.

Naming: test_<method>_<whenCondition>_<returnsExpected>
Assert style: actualResult / expectedResult; one assert per test.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from mainApp.feed_profile import apply_profile_feed_filter
from mainApp.feed_resume import feed_queryset
from mainApp.models import Book, Post, UserSubProfile

User = get_user_model()


class FeedProfileRepositoryTestBase(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="author", password="x")
        self.reader = User.objects.create_user(username="reader", password="x")

        self.fiction_book = Book.objects.create(
            isbn="9780002000001",
            title="Fiction Book",
            subjects=["Fiction"],
            min_readers_age=10,
            max_readers_age=18,
        )
        self.kids_book = Book.objects.create(
            isbn="9780002000002",
            title="Kids Book",
            subjects=["Children"],
            min_readers_age=0,
            max_readers_age=8,
        )
        self.science_book = Book.objects.create(
            isbn="9780002000003",
            title="Science Book",
            subjects=["Science"],
            min_readers_age=12,
            max_readers_age=18,
        )

        self.post_fiction = Post.objects.create(
            author=self.author,
            book=self.fiction_book,
            title="F",
            text="fiction post",
        )
        self.post_kids = Post.objects.create(
            author=self.author,
            book=self.kids_book,
            title="K",
            text="kids post",
        )
        self.post_science = Post.objects.create(
            author=self.author,
            book=self.science_book,
            title="S",
            text="science post",
        )
        self.post_no_book = Post.objects.create(
            author=self.author,
            book=None,
            title="Event",
            text="no book",
        )


class ApplyProfileFeedFilterTests(FeedProfileRepositoryTestBase):
    def test_apply_profile_feed_filter_when_no_prefs_returns_all_post_ids(self):
        qs = Post.objects.all()

        actualResult = set(
            apply_profile_feed_filter(qs, self.reader).values_list("pk", flat=True)
        )
        expectedResult = {
            self.post_fiction.pk,
            self.post_kids.pk,
            self.post_science.pk,
            self.post_no_book.pk,
        }

        self.assertEqual(actualResult, expectedResult)

    def test_apply_profile_feed_filter_when_theme_fiction_returns_fiction_and_bookless(
        self,
    ):
        self.reader.preferred_subjects = ["Fiction"]
        self.reader.save(update_fields=["preferred_subjects"])
        qs = Post.objects.all()

        actualResult = set(
            apply_profile_feed_filter(qs, self.reader).values_list("pk", flat=True)
        )
        expectedResult = {self.post_fiction.pk, self.post_no_book.pk}

        self.assertEqual(actualResult, expectedResult)

    def test_apply_profile_feed_filter_when_age_5_returns_kids_and_bookless(self):
        self.reader.age = 5
        self.reader.save(update_fields=["age"])
        qs = Post.objects.all()

        actualResult = set(
            apply_profile_feed_filter(qs, self.reader).values_list("pk", flat=True)
        )
        expectedResult = {self.post_kids.pk, self.post_no_book.pk}

        self.assertEqual(actualResult, expectedResult)

    def test_apply_profile_feed_filter_when_age_and_theme_and_returns_intersection(self):
        self.reader.age = 12
        self.reader.preferred_subjects = ["Fiction"]
        self.reader.save(update_fields=["age", "preferred_subjects"])
        qs = Post.objects.all()

        actualResult = set(
            apply_profile_feed_filter(qs, self.reader).values_list("pk", flat=True)
        )
        expectedResult = {self.post_fiction.pk, self.post_no_book.pk}

        self.assertEqual(actualResult, expectedResult)

    def test_apply_profile_feed_filter_when_subprofile_matches_returns_union(self):
        self.reader.preferred_subjects = ["Science"]
        self.reader.save(update_fields=["preferred_subjects"])
        UserSubProfile.objects.create(
            user=self.reader,
            name="Kid",
            age=5,
            preferred_subjects=["Children"],
        )
        qs = Post.objects.all()

        actualResult = set(
            apply_profile_feed_filter(qs, self.reader).values_list("pk", flat=True)
        )
        expectedResult = {
            self.post_science.pk,
            self.post_kids.pk,
            self.post_no_book.pk,
        }

        self.assertEqual(actualResult, expectedResult)

    def test_apply_profile_feed_filter_when_user_unauthenticated_returns_unfiltered(
        self,
    ):
        from django.contrib.auth.models import AnonymousUser

        qs = Post.objects.all()

        actualResult = set(
            apply_profile_feed_filter(qs, AnonymousUser()).values_list(
                "pk", flat=True
            )
        )
        expectedResult = set(Post.objects.values_list("pk", flat=True))

        self.assertEqual(actualResult, expectedResult)


class FeedQuerysetTests(FeedProfileRepositoryTestBase):
    def test_feed_queryset_when_filter_my_returns_only_author_posts(self):
        other = User.objects.create_user(username="other", password="x")
        Post.objects.create(author=other, title="X", text="other")

        actualResult = set(
            feed_queryset(filter_my=True, user=self.author).values_list(
                "pk", flat=True
            )
        )
        expectedResult = {
            self.post_fiction.pk,
            self.post_kids.pk,
            self.post_science.pk,
            self.post_no_book.pk,
        }

        self.assertEqual(actualResult, expectedResult)

    def test_feed_queryset_when_reader_has_theme_applies_profile_filter(self):
        self.reader.preferred_subjects = ["Children"]
        self.reader.save(update_fields=["preferred_subjects"])

        actualResult = set(
            feed_queryset(filter_my=False, user=self.reader).values_list(
                "pk", flat=True
            )
        )
        expectedResult = {self.post_kids.pk, self.post_no_book.pk}

        self.assertEqual(actualResult, expectedResult)

    def test_feed_queryset_when_filter_my_ignores_profile_theme_prefs(self):
        self.author.preferred_subjects = ["Science"]
        self.author.save(update_fields=["preferred_subjects"])

        actualResult = set(
            feed_queryset(filter_my=True, user=self.author).values_list(
                "pk", flat=True
            )
        )
        expectedResult = {
            self.post_fiction.pk,
            self.post_kids.pk,
            self.post_science.pk,
            self.post_no_book.pk,
        }

        self.assertEqual(actualResult, expectedResult)
