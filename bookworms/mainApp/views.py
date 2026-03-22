from django.shortcuts import render
from .models import Post


def home(request):
    posts = Post.objects.all()
    return render(request, 'mainApp/index.html', {'posts': posts})


def profile(request):
    return render(request, 'mainApp/profile.html')