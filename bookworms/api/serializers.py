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
            "min_readers_age",
            "max_readers_age",
            "reader_age_summary",
        )


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
            "added_at",
        )

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

    class Meta:
        model = BookCopy
        fields = ("id", "book", "owner", "created_at")


class AddIsbnSerializer(serializers.Serializer):
    isbn = serializers.CharField(max_length=32)


class AddBookManualSerializer(serializers.Serializer):
    isbn = serializers.CharField(max_length=32)
    title = serializers.CharField(max_length=500)
    authors = serializers.CharField(required=False, allow_blank=True, default="")
    publisher = serializers.CharField(required=False, allow_blank=True, default="")
    publish_date = serializers.CharField(required=False, allow_blank=True, default="")
    cover_url = serializers.URLField(required=False, allow_blank=True, default="")
    info_url = serializers.URLField(required=False, allow_blank=True, default="")


class ReaderAgeSerializer(serializers.Serializer):
    min_readers_age = serializers.IntegerField(min_value=READER_AGE_MIN, max_value=READER_AGE_MAX)
    max_readers_age = serializers.IntegerField(min_value=READER_AGE_MIN, max_value=READER_AGE_MAX)

    def validate(self, attrs):
        mn, mx = attrs["min_readers_age"], attrs["max_readers_age"]
        if mn > mx:
            attrs["min_readers_age"], attrs["max_readers_age"] = mx, mn
        return attrs


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
