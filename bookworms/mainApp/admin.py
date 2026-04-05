from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Book, BookExchangeRequest, CustomUser, Post, PrivateMessage, Shelf
from .models import AvatarCollection

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('biography', 'avatar')}),
    )

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Post)


# Нижче - реєстрація моделей бібліотеки в адмінці Django (/admin/) для перегляду та правок у БД.


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "isbn", "authors", "created_at")
    search_fields = ("title", "isbn", "authors")


@admin.register(Shelf)
class ShelfAdmin(admin.ModelAdmin):
    list_display = ("user", "book", "borrowed_from", "return_pending", "added_at")
    list_filter = ("added_at",)
    search_fields = ("user__username", "book__title", "book__isbn")


@admin.register(PrivateMessage)
class PrivateMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "sender", "recipient", "created_at", "read_at", "exchange_request")
    list_filter = ("created_at",)
    search_fields = ("body", "sender__username", "recipient__username")
    raw_id_fields = ("sender", "recipient", "exchange_request")


@admin.register(BookExchangeRequest)
class BookExchangeRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "requester", "shelf_owner", "target_shelf", "offer_shelf", "status", "created_at")
    list_filter = ("status", "created_at")
    raw_id_fields = ("target_shelf", "offer_shelf", "requester")

@admin.register(AvatarCollection)
class AvatarCollectionAdmin(admin.ModelAdmin):
    list_display = ("name", "image")
    search_fields = ("name",)