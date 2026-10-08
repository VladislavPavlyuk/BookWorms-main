from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from mainApp.book_subjects import catalog_subjects
from mainApp.forms import SubProfileForm, UserUpdateForm
from mainApp.models import UserSubProfile

MAX_SUBPROFILES = 8


@login_required
def profile(request):
    sub_count = request.user.subprofiles.count()
    return render(
        request,
        "profileApp/profile.html",
        {
            "subprofiles": request.user.subprofiles.all(),
            "catalog_subjects": catalog_subjects(),
            "can_add_sub": sub_count < MAX_SUBPROFILES,
            "max_subprofiles": MAX_SUBPROFILES,
        },
    )


@login_required
def edit_profile(request):
    if request.method == "POST":
        form = UserUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect("profile_app:profile")
    else:
        form = UserUpdateForm(instance=request.user)

    return render(
        request,
        "profileApp/profile_edit.html",
        {
            "form": form,
            "subprofiles": request.user.subprofiles.all(),
            "can_add_sub": request.user.subprofiles.count() < MAX_SUBPROFILES,
            "max_subprofiles": MAX_SUBPROFILES,
        },
    )


@login_required
def subprofile_create(request):
    if request.user.subprofiles.count() >= MAX_SUBPROFILES:
        return redirect("profile_app:edit_profile")
    if request.method == "POST":
        form = SubProfileForm(request.POST)
        if form.is_valid():
            sp = form.save(commit=False)
            sp.user = request.user
            sp.sort_order = request.user.subprofiles.count()
            sp.save()
            return redirect("profile_app:profile")
    else:
        form = SubProfileForm()
    return render(
        request,
        "profileApp/subprofile_edit.html",
        {"form": form, "creating": True},
    )


@login_required
def subprofile_edit(request, pk):
    sp = get_object_or_404(UserSubProfile, pk=pk, user=request.user)
    if request.method == "POST":
        form = SubProfileForm(request.POST, instance=sp)
        if form.is_valid():
            form.save()
            return redirect("profile_app:profile")
    else:
        form = SubProfileForm(instance=sp)
    return render(
        request,
        "profileApp/subprofile_edit.html",
        {"form": form, "creating": False, "subprofile": sp},
    )


@login_required
@require_POST
def subprofile_delete(request, pk):
    sp = get_object_or_404(UserSubProfile, pk=pk, user=request.user)
    sp.delete()
    return redirect("profile_app:profile")
