from django.urls import path
from .views import home, CustomLoginView, CustomRegisterView, delete_post
from django.contrib.auth.views import LogoutView
from .views import create_post
from .views import edit_post, edit_profile

urlpatterns = [
    path('', home, name='home'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('register/', CustomRegisterView.as_view(), name='register'),
    path('posts/create/', create_post, name='create_post'),
    path('posts/delete/<int:post_id>/', delete_post, name='delete_post'),
    path('posts/edit/<int:post_id>/', edit_post, name='edit_post'),
]