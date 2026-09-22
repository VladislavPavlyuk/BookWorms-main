from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    AvatarCollection,
    Book,
    BookCopy,
    BookExchangeRequest,
    CopyEvent,
    CustomUser,
    Post,
    PrivateMessage,
    Shelf,
)

admin.site.site_header = "Реченець"
admin.site.site_title = "Реченець"
admin.site.index_title = "Адміністрування"

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = (
        "username",
        "email",
        "is_active",
        "email_confirmed",
        "date_joined",
        "is_staff",
    )
    list_filter = ("is_active", "email_confirmed", "is_staff", "date_joined")
    actions = ("purge_expired_unconfirmed",)
    fieldsets = UserAdmin.fieldsets + (
        (None, {"fields": ("biography", "avatar", "email_confirmed", "last_watched_post")}),
    )

    @admin.action(description="Видалити прострочених непідтверджених (email_confirmed=False)")
    def purge_expired_unconfirmed(self, request, queryset):
        from .registration_service import purge_expired_unactivated_users

        n = purge_expired_unactivated_users()
        self.message_user(request, f"Видалено: {n}")


admin.site.register(CustomUser, CustomUserAdmin)
@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "book", "created_ad")
    list_filter = ("created_ad",)
    search_fields = ("title", "text", "author__username")
    raw_id_fields = ("book",)


# Нижче - реєстрація моделей бібліотеки в адмінці Django (/admin/) для перегляду та правок у БД.


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "isbn", "authors", "min_readers_age", "max_readers_age", "created_at")
    search_fields = ("title", "isbn", "authors")


@admin.register(BookCopy)
class BookCopyAdmin(admin.ModelAdmin):
    list_display = ("id", "book", "owner", "created_at")
    list_filter = ("created_at",)
    search_fields = ("book__title", "book__isbn", "owner__username")
    raw_id_fields = ("book", "owner")


@admin.register(CopyEvent)
class CopyEventAdmin(admin.ModelAdmin):
    list_display = ("id", "copy", "code", "actor", "created_at")
    list_filter = ("code", "created_at")
    search_fields = ("copy__book__title", "copy__book__isbn", "actor__username")
    raw_id_fields = (
        "copy",
        "actor",
        "holder",
        "legal_owner",
        "previous_holder",
        "previous_owner",
        "counterparty",
        "exchange_request",
    )


@admin.register(Shelf)
class ShelfAdmin(admin.ModelAdmin):
    list_display = ("user", "book", "copy", "borrowed_from", "return_pending", "due_date", "added_at")
    list_filter = ("added_at", "return_pending", "due_date")
    search_fields = ("user__username", "book__title", "book__isbn")
    raw_id_fields = ("user", "book", "copy", "borrowed_from")


@admin.register(PrivateMessage)
class PrivateMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "sender", "recipient", "is_system", "created_at", "read_at", "exchange_request")
    list_filter = ("created_at", "is_system")
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