from django.urls import path

from .views import (
    edit_profile,
    profile,
    subprofile_create,
    subprofile_delete,
    subprofile_edit,
)

app_name = "profile_app"

urlpatterns = [
    path("", profile, name="profile"),
    path("edit/", edit_profile, name="edit_profile"),
    path("subprofiles/new/", subprofile_create, name="subprofile_create"),
    path("subprofiles/<int:pk>/edit/", subprofile_edit, name="subprofile_edit"),
    path("subprofiles/<int:pk>/delete/", subprofile_delete, name="subprofile_delete"),
]
