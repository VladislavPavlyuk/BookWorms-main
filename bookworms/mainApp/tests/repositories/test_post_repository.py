"""
Repository-level tests for Post model relations — live Django test DB.

Naming: test_<method>_<whenCondition>_<returnsExpected>
Assert style: actualResult / expectedResult; one assert per test.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from mainApp.models import Post

User = get_user_model()


class PostRepositoryTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alexi_admin",
            password="password123",
            biography="Тестова Про себе користувача",
        )


class PostCreateTests(PostRepositoryTestBase):
    def test_create_post_when_title_and_text_set_returns_persisted_fields(self):
        post = Post.objects.create(
            author=self.user,
            title="Тестовий заголовок",
            text="Текст тестового повідомлення",
        )

        actualResult = (post.title, post.text, self.user.biography)
        expectedResult = (
            "Тестовий заголовок",
            "Текст тестового повідомлення",
            "Тестова Про себе користувача",
        )

        self.assertEqual(actualResult, expectedResult)


class UserPostsRelationTests(PostRepositoryTestBase):
    def test_posts_related_when_two_created_returns_count_two(self):
        Post.objects.create(author=self.user, title="Запис 1", text="...")
        Post.objects.create(author=self.user, title="Запис 2", text="...")

        actualResult = self.user.posts.count()
        expectedResult = 2

        self.assertEqual(actualResult, expectedResult)
