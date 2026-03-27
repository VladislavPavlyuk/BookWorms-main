from django.urls import path
from .views import home, profile, CustomLoginView, CustomRegisterView
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('', home, name='home'),
    path('profile/', profile, name='profile'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('register/', CustomRegisterView.as_view(), name='register'),
]