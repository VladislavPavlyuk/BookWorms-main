from .book_search import (
    has_active_book_search,
    unique_author_choices,
    unique_publisher_choices,
)
from .models import Book


def nav_book_search(request):
    if not request.user.is_authenticated:
        return {
            "nav_book_search_expanded": False,
            "nav_book_search_books": [],
            "nav_book_search_authors": [],
            "nav_book_search_publishers": [],
        }
    books = Book.objects.only("id", "title", "isbn").order_by("title")
    return {
        "nav_book_search_expanded": has_active_book_search(request.GET),
        "nav_book_search_books": books,
        "nav_book_search_authors": unique_author_choices(),
        "nav_book_search_publishers": unique_publisher_choices(),
    }
