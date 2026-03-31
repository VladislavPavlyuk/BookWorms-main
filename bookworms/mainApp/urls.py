"""
Маршрути застосунку. Блок /library/… - бібліотека, полиці інших, обмін і позика.
Порядок важливий: спочатку "конкретні" шляхи (exchange/new), потім загальні (exchange/).
"""
from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import (
    home,
    profile,
    CustomLoginView,
    CustomRegisterView,
    create_post,
    delete_post,
    edit_post,
    edit_profile,
    my_library,
    remove_shelf_entry,
    return_borrowed_shelf_book,
    browse_shelves,
    create_exchange,
    exchange_requests,
    exchange_accept,
    exchange_reject,
    exchange_cancel,
    message_thread,
)

urlpatterns = [
    path('', home, name='home'),
    # --- Бібліотека та обмін книгами ---
    path('library/', my_library, name='my_library'),
    path('library/remove/<int:shelf_id>/', remove_shelf_entry, name='remove_shelf_entry'),
    path('library/return/<int:shelf_id>/', return_borrowed_shelf_book, name='return_borrowed_shelf_book'),
    path('library/browse/', browse_shelves, name='browse_shelves'),
    path('library/exchange/new/', create_exchange, name='create_exchange'),
    path('library/exchange/', exchange_requests, name='exchange_requests'),
    path('library/exchange/<int:request_id>/accept/', exchange_accept, name='exchange_accept'),
    path('library/exchange/<int:request_id>/reject/', exchange_reject, name='exchange_reject'),
    path('library/exchange/<int:request_id>/cancel/', exchange_cancel, name='exchange_cancel'),
    path('messages/<int:partner_id>/', message_thread, name='message_thread'),
    path('profile/', profile, name='profile'),
    path('profile/edit/', edit_profile, name='edit_profile'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('register/', CustomRegisterView.as_view(), name='register'),
    path('posts/create/', create_post, name='create_post'),
    path('posts/delete/<int:post_id>/', delete_post, name='delete_post'),
    path('posts/edit/<int:post_id>/', edit_post, name='edit_post'),
]
