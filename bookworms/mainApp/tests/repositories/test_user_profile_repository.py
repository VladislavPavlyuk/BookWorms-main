"""
Repository-level tests for CustomUser profile fields + UserSubProfile — live DB.

Naming: test_<method>_<whenCondition>_<returnsExpected>
Assert style: actualResult / expectedResult; one assert per test.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from mainApp.models import UserSubProfile

User = get_user_model()


class UserProfileRepositoryTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="profile_user",
            password="x",
            age=30,
            place="Kyiv",
            preferred_subjects=["Fiction", "History"],
        )


class CustomUserProfileFieldsTests(UserProfileRepositoryTestBase):
    def test_create_user_when_profile_fields_set_returns_persisted_values(self):
        self.user.refresh_from_db()

        actualResult = (
            self.user.age,
            self.user.place,
            list(self.user.preferred_subjects),
        )
        expectedResult = (30, "Kyiv", ["Fiction", "History"])

        self.assertEqual(actualResult, expectedResult)

    def test_update_preferred_subjects_when_new_list_returns_updated_list(self):
        self.user.preferred_subjects = ["Science"]
        self.user.save(update_fields=["preferred_subjects"])
        self.user.refresh_from_db()

        actualResult = list(self.user.preferred_subjects)
        expectedResult = ["Science"]

        self.assertEqual(actualResult, expectedResult)


class UserSubProfileRepositoryTests(UserProfileRepositoryTestBase):
    def test_create_subprofile_when_valid_returns_related_on_user(self):
        sp = UserSubProfile.objects.create(
            user=self.user,
            name="Для сина",
            age=7,
            place="Kyiv",
            preferred_subjects=["Children"],
        )

        actualResult = list(
            self.user.subprofiles.values_list("id", "name", "age", flat=False)
        )
        expectedResult = [(sp.id, "Для сина", 7)]

        self.assertEqual(actualResult, expectedResult)

    def test_delete_subprofile_when_exists_returns_empty_related(self):
        sp = UserSubProfile.objects.create(
            user=self.user,
            name="Temp",
            preferred_subjects=[],
        )
        sp.delete()

        actualResult = self.user.subprofiles.count()
        expectedResult = 0

        self.assertEqual(actualResult, expectedResult)

    def test_subprofiles_ordering_when_sort_order_set_returns_sorted_names(self):
        UserSubProfile.objects.create(
            user=self.user, name="B", sort_order=2, preferred_subjects=[]
        )
        UserSubProfile.objects.create(
            user=self.user, name="A", sort_order=1, preferred_subjects=[]
        )

        actualResult = list(self.user.subprofiles.values_list("name", flat=True))
        expectedResult = ["A", "B"]

        self.assertEqual(actualResult, expectedResult)
