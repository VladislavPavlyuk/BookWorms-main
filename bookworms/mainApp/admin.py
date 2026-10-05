from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    AvatarCollection,
    Book,
    BookCopy,
    BookExchangeRequest,
    BookPhoto,
    CopyEvent,
    CustomUser,
    Library,
    LibraryAction,
    LibraryAdminElection,
    LibraryAdminVote,
    LibraryInvite,
    LibraryMembership,
    LoanHandoff,
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


class BookPhotoInline(admin.TabularInline):
    model = BookPhoto
    extra = 0


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "isbn", "authors", "min_readers_age", "max_readers_age", "created_at")
    search_fields = ("title", "isbn", "authors")
    inlines = (BookPhotoInline,)


@admin.register(BookCopy)
class BookCopyAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "book",
        "owner",
        "library",
        "added_by",
        "is_fee_sharing",
        "is_hidden",
        "is_for_sale",
        "is_for_rent",
        "is_as_gift",
        "is_for_exchange",
        "is_free_of_deposit",
        "sale_price",
        "rent_price_per_day",
        "created_at",
    )
    list_filter = (
        "is_fee_sharing",
        "is_hidden",
        "is_for_sale",
        "is_for_rent",
        "is_as_gift",
        "is_for_exchange",
        "is_free_of_deposit",
        "created_at",
    )
    search_fields = ("book__title", "book__isbn", "owner__username")
    raw_id_fields = ("book", "owner", "library", "added_by")


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


@admin.register(LoanHandoff)
class LoanHandoffAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "copy",
        "owner",
        "from_user",
        "to_user",
        "status",
        "created_at",
    )
    list_filter = ("status", "created_at")
    raw_id_fields = (
        "copy",
        "owner",
        "from_user",
        "to_user",
        "exchange_request",
        "from_shelf",
    )


@admin.register(AvatarCollection)
class AvatarCollectionAdmin(admin.ModelAdmin):
    list_display = ("name", "image")
    search_fields = ("name",)

@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "admin", "created_at")
    search_fields = ("name", "admin__username")
    raw_id_fields = ("admin",)


@admin.register(LibraryMembership)
class LibraryMembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "library", "user", "role", "joined_at")
    list_filter = ("role",)
    raw_id_fields = ("library", "user")


@admin.register(LibraryInvite)
class LibraryInviteAdmin(admin.ModelAdmin):
    list_display = ("id", "library", "from_user", "to_user", "status", "created_at")
    list_filter = ("status",)
    raw_id_fields = ("library", "from_user", "to_user")


@admin.register(LibraryAction)
class LibraryActionAdmin(admin.ModelAdmin):
    list_display = ("id", "library", "initiator", "action_type", "status", "created_at")
    list_filter = ("action_type", "status")
    raw_id_fields = ("library", "initiator", "resolved_by")


@admin.register(LibraryAdminElection)
class LibraryAdminElectionAdmin(admin.ModelAdmin):
    list_display = ("id", "library", "status", "started_by", "winner", "created_at")
    list_filter = ("status",)
    raw_id_fields = ("library", "started_by", "winner")


@admin.register(LibraryAdminVote)
class LibraryAdminVoteAdmin(admin.ModelAdmin):
    list_display = ("id", "election", "voter", "candidate", "created_at")
    raw_id_fields = ("election", "voter", "candidate")
