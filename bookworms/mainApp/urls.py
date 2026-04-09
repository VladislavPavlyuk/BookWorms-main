"""
Маршрути застосунку. Блок /library/… - бібліотека, полиці інших, обмін і позика.
Порядок важливий: спочатку "конкретні" шляхи (exchange/new), потім загальні (exchange/).
"""
from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import (
    home,
    activate,
    confirm_email_view,
    CustomLoginView,
    CustomRegisterView,
    create_post,
    delete_post,
    edit_post,
    my_library,
    update_shelf_book_reader_age,
    unlock_shelf_reader_age_edit,
    remove_shelf_entry,
    return_borrowed_shelf_book,
    confirm_return_borrowed_shelf_book,
    browse_shelves,
    user_public_shelf,
    book_history,
    create_exchange,
    exchange_requests,
    exchange_accept,
    exchange_reject,
    exchange_cancel,
    message_thread,
)
from .views import add_comment
from .views import toggle_like

urlpatterns = [
    path('', home, name='home'),
    # --- Бібліотека та обмін книгами ---
    path('library/', my_library, name='my_library'),
    path(
        'library/shelf/<int:shelf_id>/reader-age/',
        update_shelf_book_reader_age,
        name='update_shelf_book_reader_age',
    ),
    path(
        'library/shelf/<int:shelf_id>/reader-age/unlock/',
        unlock_shelf_reader_age_edit,
        name='unlock_shelf_reader_age_edit',
    ),
    path('library/remove/<int:shelf_id>/', remove_shelf_entry, name='remove_shelf_entry'),
    path('library/return/<int:shelf_id>/', return_borrowed_shelf_book, name='return_borrowed_shelf_book'),
    path(
        'library/confirm-return/<int:shelf_id>/',
        confirm_return_borrowed_shelf_book,
        name='confirm_return_borrowed_shelf_book',
    ),
    path('library/browse/', browse_shelves, name='browse_shelves'),
    path('library/user/<int:user_id>/', user_public_shelf, name='user_public_shelf'),
    path('library/book/<int:book_id>/history/', book_history, name='book_history'),
    path('library/exchange/new/', create_exchange, name='create_exchange'),
    path('library/exchange/', exchange_requests, name='exchange_requests'),
    path('library/exchange/<int:request_id>/accept/', exchange_accept, name='exchange_accept'),
    path('library/exchange/<int:request_id>/reject/', exchange_reject, name='exchange_reject'),
    path('library/exchange/<int:request_id>/cancel/', exchange_cancel, name='exchange_cancel'),
    path('messages/<int:partner_id>/', message_thread, name='message_thread'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('register/', CustomRegisterView.as_view(), name='register'),
    path('register/confirm-email/', confirm_email_view, name='confirm_email'),
    path('activate/<str:uidb64>/<str:token>/', activate, name='activate'),
    path('posts/create/', create_post, name='create_post'),
    path('posts/delete/<int:post_id>/', delete_post, name='delete_post'),
    path('posts/edit/<int:post_id>/', edit_post, name='edit_post'),
    path('posts/<int:post_id>/comment/', add_comment, name='add_comment'),
    path('posts/<int:post_id>/like/', toggle_like, name='toggle_like'),
]
