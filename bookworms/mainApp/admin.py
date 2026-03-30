from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Book, BookExchangeRequest, CustomUser, Post, Shelf


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('biography', 'avatar')}),
    )

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Post)


# Нижче — реєстрація моделей бібліотеки в адмінці Django (/admin/) для перегляду та правок у БД.


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "isbn", "authors", "created_at")
    search_fields = ("title", "isbn", "authors")


@admin.register(Shelf)
class ShelfAdmin(admin.ModelAdmin):
    list_display = ("user", "book", "borrowed_from", "added_at")
    list_filter = ("added_at",)
    search_fields = ("user__username", "book__title", "book__isbn")


@admin.register(BookExchangeRequest)
class BookExchangeRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "requester", "shelf_owner", "target_shelf", "offer_shelf", "status", "created_at")
    list_filter = ("status", "created_at")
    raw_id_fields = ("target_shelf", "offer_shelf", "requester")
