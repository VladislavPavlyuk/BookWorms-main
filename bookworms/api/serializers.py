from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from mainApp.models import (
    Book,
    BookCopy,
    BookExchangeRequest,
    Comment,
    CopyEvent,
    Like,
    LoanHandoff,
    Post,
    PrivateMessage,
    READER_AGE_MAX,
    READER_AGE_MIN,
    Shelf,
)

User = get_user_model()


class UserPublicSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "biography", "avatar_url")

    def get_avatar_url(self, obj):
        if not obj.avatar:
            return None
        request = self.context.get("request")
        url = obj.avatar.url
        return request.build_absolute_uri(url) if request else url


class MeSerializer(UserPublicSerializer):
    class Meta(UserPublicSerializer.Meta):
        fields = (
            "id",
            "username",
            "email",
            "biography",
            "avatar_url",
            "date_joined",
            "last_watched_post_id",
        )


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    biography = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Цей логін уже зайнятий.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Ця електронна адреса вже використовується.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value


class MeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("username", "biography", "avatar")


class BookSerializer(serializers.ModelSerializer):
    reader_age_summary = serializers.CharField(read_only=True)
    photo_urls = serializers.SerializerMethodField()
    isbn_missing = serializers.SerializerMethodField()
    note = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = (
            "id",
            "isbn",
            "title",
            "authors",
            "publisher",
            "publish_date",
            "cover_url",
            "info_url",
            "cover_text",
            "photo_urls",
            "min_readers_age",
            "max_readers_age",
            "reader_age_summary",
            "isbn_missing",
            "note",
        )

    def get_photo_urls(self, obj):
        from mainApp.book_photos import book_photo_urls

        return book_photo_urls(obj, request=self.context.get("request"))

    def get_isbn_missing(self, obj):
        from mainApp.book_photos import is_local_isbn

        flagged = getattr(obj, "_isbn_missing", None)
        if flagged is not None:
            return bool(flagged)
        return is_local_isbn(obj.isbn)

    def get_note(self, obj):
        from mainApp.book_cover_ai import NO_ISBN_NOTE
        from mainApp.book_photos import is_local_isbn

        note = getattr(obj, "_isbn_note", None)
        if note is not None:
            return note
        return NO_ISBN_NOTE if is_local_isbn(obj.isbn) else ""

class CommentSerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ("id", "author", "text", "created_at")
        read_only_fields = ("id", "author", "created_at")


class PostSerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)
    book = BookSerializer(read_only=True)
    likes_count = serializers.IntegerField(read_only=True)
    comments_count = serializers.IntegerField(read_only=True)
    liked_by_me = serializers.SerializerMethodField()
    comments = CommentSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = (
            "id",
            "author",
            "book",
            "title",
            "text",
            "created_ad",
            "likes_count",
            "comments_count",
            "liked_by_me",
            "comments",
        )

    def get_liked_by_me(self, obj):
        user = self.context["request"].user
        if not user.is_authenticated:
            return False
        if hasattr(obj, "liked_by_me"):
            return bool(obj.liked_by_me)
        return Like.objects.filter(post=obj, user=user).exists()


class PostWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    text = serializers.CharField()
    book_id = serializers.IntegerField(required=False, allow_null=True)
    confirm_new_post = serializers.BooleanField(required=False, default=False)


class ShelfSerializer(serializers.ModelSerializer):
    book = BookSerializer(read_only=True)
    user = UserPublicSerializer(read_only=True)
    borrowed_from = UserPublicSerializer(read_only=True)
    lent_to = serializers.SerializerMethodField()
    loan_due_date = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    days_left = serializers.SerializerMethodField()
    is_lent_out = serializers.SerializerMethodField()
    pending_return_shelf_id = serializers.SerializerMethodField()
    request_shelf_id = serializers.SerializerMethodField()
    can_edit_manual = serializers.SerializerMethodField()
    price_eval = serializers.SerializerMethodField()
    is_fee_sharing = serializers.SerializerMethodField()
    is_hidden = serializers.SerializerMethodField()
    is_for_sale = serializers.SerializerMethodField()
    is_for_rent = serializers.SerializerMethodField()
    is_as_gift = serializers.SerializerMethodField()
    is_for_exchange = serializers.SerializerMethodField()
    is_free_of_deposit = serializers.SerializerMethodField()
    listing_labels = serializers.SerializerMethodField()
    sale_gift = serializers.SerializerMethodField()
    sale_price = serializers.SerializerMethodField()
    rent_price_per_day = serializers.SerializerMethodField()
    requires_deposit = serializers.SerializerMethodField()
    is_publicly_listed = serializers.SerializerMethodField()
    listing_status_display = serializers.SerializerMethodField()

    class Meta:
        model = Shelf
        fields = (
            "id",
            "user",
            "book",
            "copy_id",
            "borrowed_from",
            "lent_to",
            "return_pending",
            "due_date",
            "loan_due_date",
            "is_overdue",
            "days_left",
            "is_lent_out",
            "pending_return_shelf_id",
            "request_shelf_id",
            "can_edit_manual",
            "price_eval",
            "is_fee_sharing",
            "is_hidden",
            "is_for_sale",
            "is_for_rent",
            "is_as_gift",
            "is_for_exchange",
            "is_free_of_deposit",
            "listing_labels",
            "sale_gift",
            "sale_price",
            "rent_price_per_day",
            "requires_deposit",
            "is_publicly_listed",
            "listing_status_display",
            "added_at",
        )

    def _copy(self, obj):
        return getattr(obj, "copy", None)

    def get_is_fee_sharing(self, obj):
        c = self._copy(obj)
        return bool(c.is_fee_sharing) if c else True

    def get_is_hidden(self, obj):
        c = self._copy(obj)
        return bool(c.is_hidden) if c else False

    def get_is_for_sale(self, obj):
        c = self._copy(obj)
        return bool(c.is_for_sale) if c else False

    def get_is_for_rent(self, obj):
        c = self._copy(obj)
        return bool(c.is_for_rent) if c else False

    def get_is_as_gift(self, obj):
        c = self._copy(obj)
        return bool(c.is_as_gift) if c else False

    def get_is_for_exchange(self, obj):
        c = self._copy(obj)
        return bool(c.is_for_exchange) if c else False

    def get_is_free_of_deposit(self, obj):
        c = self._copy(obj)
        return bool(c.is_free_of_deposit) if c else False

    def get_listing_labels(self, obj):
        c = self._copy(obj)
        return c.listing_labels() if c else []

    def get_sale_gift(self, obj):
        c = self._copy(obj)
        if not c:
            return ""
        if c.is_for_sale:
            return "for_sale"
        if c.is_as_gift:
            return "as_gift"
        return ""

    def get_sale_price(self, obj):
        c = self._copy(obj)
        if not c or c.sale_price is None:
            return None
        return str(c.sale_price)

    def get_rent_price_per_day(self, obj):
        c = self._copy(obj)
        if not c or c.rent_price_per_day is None:
            return None
        return str(c.rent_price_per_day)

    def get_requires_deposit(self, obj):
        c = self._copy(obj)
        return bool(c.requires_deposit) if c else True

    def get_is_publicly_listed(self, obj):
        c = self._copy(obj)
        return bool(c.is_publicly_listed) if c else True

    def get_listing_status_display(self, obj):
        c = self._copy(obj)
        return ", ".join(c.listing_labels()) if c else ""

    def get_price_eval(self, obj):
        # Only expose on the owner's library endpoint (my_shelf / refresh).
        if not self.context.get("include_price_eval"):
            return None
        from mainApp.book_price import serialize_evaluation

        ev = getattr(obj.book, "price_evaluation", None)
        if ev is None:
            try:
                ev = obj.book.price_evaluation
            except Exception:
                ev = None
        return serialize_evaluation(ev)

    def get_can_edit_manual(self, obj):
        if obj.borrowed_from_id:
            return False
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        if not user or not user.is_authenticated:
            return False
        if user.pk != obj.user_id:
            return False
        from mainApp.book_photos import user_can_edit_manual_book
        from mainApp.exchange_service import is_copy_lent_out

        if is_copy_lent_out(obj.copy_id):
            return False
        return user_can_edit_manual_book(user, obj.book)

    def get_lent_to(self, obj):
        loan = getattr(obj, "loan_row", None)
        if not loan:
            return None
        return UserPublicSerializer(loan.user, context=self.context).data

    def get_loan_due_date(self, obj):
        loan = getattr(obj, "loan_row", None)
        if loan and loan.due_date:
            return loan.due_date
        return None

    def _effective_due(self, obj):
        if obj.borrowed_from_id and obj.due_date:
            return obj.due_date
        loan = getattr(obj, "loan_row", None)
        if loan and loan.due_date:
            return loan.due_date
        return None

    def get_is_overdue(self, obj):
        due = self._effective_due(obj)
        if not due:
            return False
        return due < timezone.now().date()

    def get_days_left(self, obj):
        due = self._effective_due(obj)
        if not due:
            return None
        return (due - timezone.now().date()).days

    def get_is_lent_out(self, obj):
        if getattr(obj, "is_lent_out", None) is not None:
            return bool(obj.is_lent_out)
        if obj.borrowed_from_id:
            return False
        from mainApp.exchange_service import is_copy_lent_out

        return is_copy_lent_out(getattr(obj, "copy_id", None))

    def get_pending_return_shelf_id(self, obj):
        if getattr(obj, "pending_return_shelf_id", None) is not None:
            return obj.pending_return_shelf_id
        return None

    def get_request_shelf_id(self, obj):
        """Id полиці власника для create_exchange (для позики = сам рядок)."""
        rid = getattr(obj, "request_shelf_id", None)
        if rid is not None:
            return rid
        if obj.borrowed_from_id:
            return None
        return obj.pk


class CopyEventSerializer(serializers.ModelSerializer):
    code_display = serializers.CharField(source="get_code_display", read_only=True)
    actor = UserPublicSerializer(read_only=True)
    holder = UserPublicSerializer(read_only=True)
    legal_owner = UserPublicSerializer(read_only=True)
    previous_holder = UserPublicSerializer(read_only=True)
    previous_owner = UserPublicSerializer(read_only=True)
    counterparty = UserPublicSerializer(read_only=True)

    class Meta:
        model = CopyEvent
        fields = (
            "id",
            "code",
            "code_display",
            "actor",
            "holder",
            "legal_owner",
            "previous_holder",
            "previous_owner",
            "counterparty",
            "exchange_request_id",
            "created_at",
        )


class BookCopySerializer(serializers.ModelSerializer):
    book = BookSerializer(read_only=True)
    owner = UserPublicSerializer(read_only=True)
    listing_labels = serializers.SerializerMethodField()
    sale_gift = serializers.SerializerMethodField()
    requires_deposit = serializers.BooleanField(read_only=True)
    is_publicly_listed = serializers.BooleanField(read_only=True)
    listing_status_display = serializers.SerializerMethodField()

    class Meta:
        model = BookCopy
        fields = (
            "id",
            "book",
            "owner",
            "is_fee_sharing",
            "is_hidden",
            "is_for_sale",
            "is_for_rent",
            "is_as_gift",
            "is_for_exchange",
            "is_free_of_deposit",
            "listing_labels",
            "sale_gift",
            "sale_price",
            "rent_price_per_day",
            "requires_deposit",
            "is_publicly_listed",
            "listing_status_display",
            "created_at",
        )

    def get_listing_labels(self, obj):
        return obj.listing_labels()

    def get_sale_gift(self, obj):
        if obj.is_for_sale:
            return "for_sale"
        if obj.is_as_gift:
            return "as_gift"
        return ""

    def get_listing_status_display(self, obj):
        return ", ".join(obj.listing_labels())


class AddIsbnSerializer(serializers.Serializer):
    isbn = serializers.CharField(max_length=32)


class AddBookManualSerializer(serializers.Serializer):
    isbn = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    title = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    authors = serializers.CharField(required=False, allow_blank=True, default="")
    publisher = serializers.CharField(required=False, allow_blank=True, default="")
    publish_date = serializers.CharField(required=False, allow_blank=True, default="")
    cover_url = serializers.URLField(required=False, allow_blank=True, default="")
    info_url = serializers.URLField(required=False, allow_blank=True, default="")
    cover_text = serializers.CharField(required=False, allow_blank=True, default="")


class UpdateBookManualSerializer(serializers.Serializer):
    isbn = serializers.CharField(max_length=32, required=False, allow_blank=True)
    title = serializers.CharField(max_length=500, required=False, allow_blank=True)
    authors = serializers.CharField(required=False, allow_blank=True)
    publisher = serializers.CharField(required=False, allow_blank=True)
    publish_date = serializers.CharField(required=False, allow_blank=True)
    cover_url = serializers.URLField(required=False, allow_blank=True)
    info_url = serializers.URLField(required=False, allow_blank=True)
    cover_text = serializers.CharField(required=False, allow_blank=True)
    # Comma-separated or repeated form keys; parsed in the view.
    delete_photo_ids = serializers.CharField(required=False, allow_blank=True, default="")


class ReaderAgeSerializer(serializers.Serializer):
    min_readers_age = serializers.IntegerField(min_value=READER_AGE_MIN, max_value=READER_AGE_MAX)
    max_readers_age = serializers.IntegerField(min_value=READER_AGE_MIN, max_value=READER_AGE_MAX)

    def validate(self, attrs):
        mn, mx = attrs["min_readers_age"], attrs["max_readers_age"]
        if mn > mx:
            attrs["min_readers_age"], attrs["max_readers_age"] = mx, mn
        return attrs


class CopyListingSerializer(serializers.Serializer):
    is_fee_sharing = serializers.BooleanField(required=False)
    is_hidden = serializers.BooleanField(required=False)
    is_for_rent = serializers.BooleanField(required=False)
    is_for_exchange = serializers.BooleanField(required=False)
    is_free_of_deposit = serializers.BooleanField(required=False)
    sale_gift = serializers.ChoiceField(
        choices=[("", "Neither"), ("for_sale", "For sale"), ("as_gift", "As a gift")],
        required=False,
        allow_blank=True,
    )
    sale_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    rent_price_per_day = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    # legacy single-status clients
    listing_status = serializers.CharField(required=False, allow_blank=True)


class ExchangeRequestSerializer(serializers.ModelSerializer):
    requester = UserPublicSerializer(read_only=True)
    shelf_owner = UserPublicSerializer(read_only=True)
    target_shelf = ShelfSerializer(read_only=True)
    offer_shelf = ShelfSerializer(read_only=True)
    kind = serializers.SerializerMethodField()
    is_transmission = serializers.SerializerMethodField()

    class Meta:
        model = BookExchangeRequest
        fields = (
            "id",
            "requester",
            "shelf_owner",
            "target_shelf",
            "offer_shelf",
            "status",
            "kind",
            "is_transmission",
            "created_at",
            "resolved_at",
        )

    def get_kind(self, obj):
        return "exchange" if obj.offer_shelf_id else "borrow"

    def get_is_transmission(self, obj):
        """Pending borrow while copy is currently lent → owner would transmit to requester."""
        if obj.offer_shelf_id or obj.status != BookExchangeRequest.Status.PENDING:
            return False
        copy_id = getattr(obj.target_shelf, "copy_id", None)
        if not copy_id:
            return False
        from mainApp.exchange_service import is_copy_lent_out

        return is_copy_lent_out(copy_id)


class CreateExchangeSerializer(serializers.Serializer):
    target_shelf_id = serializers.IntegerField()
    offer_shelf_id = serializers.IntegerField(required=False, allow_null=True)


class BookBrowseGroupSerializer(serializers.Serializer):
    """Один ISBN: обкладинка + список власників + примірники для запиту."""

    book = BookSerializer()
    owners = UserPublicSerializer(many=True)
    copies = ShelfSerializer(many=True)

    def to_representation(self, instance):
        # instance: {book, owners, shelves}
        ctx = self.context
        return {
            "book": BookSerializer(instance["book"], context=ctx).data,
            "owners": UserPublicSerializer(
                instance["owners"], many=True, context=ctx
            ).data,
            "copies": ShelfSerializer(
                instance["shelves"], many=True, context=ctx
            ).data,
        }


class MessageSerializer(serializers.ModelSerializer):
    sender = UserPublicSerializer(read_only=True)
    recipient = UserPublicSerializer(read_only=True)

    class Meta:
        model = PrivateMessage
        fields = (
            "id",
            "sender",
            "recipient",
            "body",
            "exchange_request",
            "created_at",
            "read_at",
        )


class SendMessageSerializer(serializers.Serializer):
    body = serializers.CharField()


class LoanHandoffSerializer(serializers.ModelSerializer):
    owner = UserPublicSerializer(read_only=True)
    from_user = UserPublicSerializer(read_only=True)
    to_user = UserPublicSerializer(read_only=True)
    book_title = serializers.CharField(source="copy.book.title", read_only=True)
    copy_id = serializers.IntegerField(read_only=True)
    my_role = serializers.SerializerMethodField()
    can_confirm_give = serializers.SerializerMethodField()
    can_confirm_receive = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    participants = serializers.SerializerMethodField()

    class Meta:
        model = LoanHandoff
        fields = (
            "id",
            "copy_id",
            "book_title",
            "owner",
            "from_user",
            "to_user",
            "status",
            "giver_confirmed_at",
            "receiver_confirmed_at",
            "exchange_request_id",
            "created_at",
            "my_role",
            "can_confirm_give",
            "can_confirm_receive",
            "can_cancel",
            "participants",
        )

    def _req_user(self):
        req = self.context.get("request")
        return getattr(req, "user", None) if req else None

    def get_my_role(self, obj):
        u = self._req_user()
        if not u or not u.is_authenticated:
            return None
        if u.id == obj.owner_id:
            return "owner"
        if u.id == obj.from_user_id:
            return "giver"
        if u.id == obj.to_user_id:
            return "receiver"
        return None

    def get_can_confirm_give(self, obj):
        u = self._req_user()
        return bool(
            u
            and u.is_authenticated
            and u.id == obj.from_user_id
            and obj.status == "awaiting_give"
        )

    def get_can_confirm_receive(self, obj):
        u = self._req_user()
        return bool(
            u
            and u.is_authenticated
            and u.id == obj.to_user_id
            and obj.status == "awaiting_receive"
        )

    def get_can_cancel(self, obj):
        u = self._req_user()
        return bool(
            u
            and u.is_authenticated
            and u.id == obj.owner_id
            and obj.status in ("awaiting_give", "awaiting_receive")
        )

    def get_participants(self, obj):
        ctx = self.context
        return [
            UserPublicSerializer(obj.owner, context=ctx).data,
            UserPublicSerializer(obj.from_user, context=ctx).data,
            UserPublicSerializer(obj.to_user, context=ctx).data,
        ]
