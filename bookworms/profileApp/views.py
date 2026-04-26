from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from mainApp.forms import UserUpdateForm


# Create your views here.
def profile(request):
    return render(request, 'profileApp/profile.html')

@login_required
def edit_profile(request):
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile_app:profile')
    else:
        form = UserUpdateForm(instance=request.user)

    return render(request, 'profileApp/profile_edit.html', {'form': form})