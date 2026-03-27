from django.contrib.auth import login
from django.shortcuts import render
from .models import Post, CustomUser
from django.contrib.auth.views import LoginView
from .forms import UserLoginForm, UserRegisterForm
from django.views.generic import CreateView
from django.urls import reverse_lazy, reverse

def home(request):
    posts = Post.objects.all()
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
