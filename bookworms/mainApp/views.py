from django.contrib.auth import login
from django.shortcuts import render, redirect
from .models import Post, CustomUser
from django.contrib.auth.views import LoginView
from .forms import UserLoginForm, UserRegisterForm
from django.views.generic import CreateView
from django.urls import reverse_lazy, reverse
from django.contrib.auth.decorators import login_required
from .models import Post
from .forms import UserUpdateForm

def home(request):
    posts = Post.objects.all().order_by('-created_ad')
    return render(request, 'mainApp/index.html', {'posts': posts})


def profile(request):
    return render(request, 'mainApp/profile.html')

class CustomLoginView(LoginView):
    template_name = 'mainApp/login.html'
    authentication_form = UserLoginForm

class CustomRegisterView(CreateView):
    template_name = 'mainApp/register.html'
    form_class = UserRegisterForm
    success_url = reverse_lazy('home')

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response

@login_required
def create_post(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        text = request.POST.get('text')

        if title and text:
            Post.objects.create(
                author=request.user,
                title=title,
                text=text
            )
            return redirect('home')

    return render(request, 'mainApp/form.html')


@login_required
def delete_post(request, post_id):
    post = Post.objects.get(id=post_id)

    if post.author == request.user:
        post.delete()

    return redirect('home')

@login_required
def edit_post(request, post_id):
    post = Post.objects.get(id=post_id)

    if post.author != request.user:
        return redirect('home')

    if request.method == 'POST':
        post.title = request.POST.get('title')
        post.text = request.POST.get('text')
        post.save()
        return redirect('home')

    return render(request, 'mainApp/form.html', {'post': post})

@login_required
def edit_profile(request):
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = UserUpdateForm(instance=request.user)

    return render(request, 'mainApp/profile_edit.html', {'form': form})
