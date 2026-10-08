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
    UserSubProfile,
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


class SubProfileSerializer(serializers.ModelSerializer):
    age = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=120
    )
    place = serializers.CharField(
        required=False, allow_blank=True, max_length=255, default=""
    )
    preferred_subjects = serializers.ListField(
        child=serializers.CharField(max_length=200, allow_blank=False),
        required=False,
        allow_empty=True,
        default=list,
    )

    class Meta:
        model = UserSubProfile
        fields = (
            "id",
            "name",
            "age",
            "place",
            "preferred_subjects",
            "sort_order",
            "created_at",
        )
        read_only_fields = ("id", "created_at", "sort_order")

    def validate_preferred_subjects(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Очікується список рядків.")
        out = []
        seen = set()
        for item in value:
            label = (item if isinstance(item, str) else str(item or "")).strip()
            if not label:
                continue
            key = label.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(label)
        return out

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Назва обов’язкова.")
        return value[:100]


class MeSerializer(UserPublicSerializer):
    subprofiles = SubProfileSerializer(many=True, read_only=True)

    class Meta(UserPublicSerializer.Meta):
        fields = (
            "id",
            "username",
            "email",
            "biography",
            "avatar_url",
            "age",
            "place",
            "preferred_subjects",
            "subprofiles",
            "date_joined",
            "last_watched_post_id",
        )


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    biography = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_username(self, value):
        from mainApp.registration_availability import suggest_usernames, username_taken

        value = (value or "").strip()
        if username_taken(value):
            suggestions = suggest_usernames(value)
            detail = "Цей логін уже зайнятий."
            if suggestions:
                detail = (
                    "Цей логін уже зайнятий. Оберіть запропонований унікальний логін "
                    f"(напр. {suggestions[0]})."
                )
            raise serializers.ValidationError(detail)
        return value

    def validate_email(self, value):
        from mainApp.registration_availability import email_taken

        value = (value or "").strip()
        if email_taken(value):
            raise serializers.ValidationError(
                "Ця електронна адреса вже використовується."
            )
        return value

    def validate_password(self, value):
        validate_password(value)
        return value


class MeUpdateSerializer(serializers.ModelSerializer):
    age = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=120
    )
    place = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )
    preferred_subjects = serializers.ListField(
        child=serializers.CharField(max_length=200, allow_blank=False),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = User
        fields = (
            "username",
            "biography",
            "avatar",
            "age",
            "place",
            "preferred_subjects",
        )

    def to_internal_value(self, data):
        # Multipart: preferred_subjects may arrive as a JSON string; age as "".
        mutable = data.copy() if hasattr(data, "copy") else dict(data)
        if "age" in mutable and mutable.get("age") in ("", None):
            mutable["age"] = None
        ps = mutable.get("preferred_subjects")
        if isinstance(ps, str):
            import json

            raw = ps.strip()
            if not raw:
                mutable["preferred_subjects"] = []
            else:
                try:
                    mutable["preferred_subjects"] = json.loads(raw)
                except json.JSONDecodeError:
                    mutable["preferred_subjects"] = [
                        s.strip() for s in raw.split(",") if s.strip()
                    ]
        return super().to_internal_value(mutable)

    def validate_preferred_subjects(self, value):
        if value is None:
            return []
        out = []
        seen = set()
        for item in value:
            label = (item if isinstance(item, str) else str(item or "")).strip()
            if not label:
                continue
            key = label.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(label)
        return out

    def validate_age(self, value):
        if value is None or value == "":
            return None
        try:
            age = int(value)
        except (TypeError, ValueError):
            raise serializers.ValidationError("Вік має бути числом.")
        if age < 0 or age > 120:
            raise serializers.ValidationError("Вік: 0–120.")
        return age


class BookSerializer(serializers.ModelSerializer):
    reader_age_summary = serializers.CharField(read_only=True)
    photo_urls = serializers.SerializerMethodField()
    cover_url = serializers.SerializerMethodField()
    isbn_missing = serializers.SerializerMethodField()
    note = serializers.SerializerMethodField()
    msrp = serializers.DecimalField(
        max_digits=10, decimal_places=2, coerce_to_string=True, allow_null=True, required=False
    )

    class Meta:
        model = Book
        fields = (
            "id",
            "isbn",
            "isbn10",
            "title",
            "title_long",
            "authors",
            "publisher",
            "publish_date",
            "binding",
            "language",
            "edition",
            "pages",
            "dimensions",
            "dimensions_data",
            "dewey_decimal",
            "overview",
            "synopsis",
            "excerpt",
            "msrp",
            "subjects",
            "other_isbns",
            "cover_url",
            "cover_url_original",
            "info_url",
            "catalog_source",
            "cover_text",
            "photo_urls",
            "min_readers_age",
            "max_readers_age",
            "reader_age_summary",
            "isbn_missing",
            "note",
        )

    def get_cover_url(self, obj):
        from mainApp.catalog_media import media_url_for_request

        return media_url_for_request(obj.cover_url, self.context.get("request"))

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
    library_owners = serializers.SerializerMethodField()
    owners_label = serializers.SerializerMethodField()
    requires_qr_scan = serializers.SerializerMethodField()

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
            "library_owners",
            "owners_label",
            "requires_qr_scan",
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

    def get_library_owners(self, obj):
        owners = getattr(obj, "library_owners", None)
        if owners is None:
            legal = obj.borrowed_from if obj.borrowed_from_id else obj.user
            owners = [legal] if legal else []
        return UserPublicSerializer(owners, many=True, context=self.context).data

    def get_owners_label(self, obj):
        label = getattr(obj, "owners_label", None)
        if label:
            return label
        owners = getattr(obj, "library_owners", None)
        if owners:
            return " + ".join(u.username for u in owners)
        legal = obj.borrowed_from if obj.borrowed_from_id else obj.user
        return legal.username if legal else ""

    def get_requires_qr_scan(self, obj):
        """Bound QR → receive/return into next library must scan the label."""
        c = self._copy(obj)
        return bool(c and c.qr_token and c.qr_attached_at)

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
    has_qr = serializers.SerializerMethodField()
    qr_attached = serializers.SerializerMethodField()
    qr_attached_at = serializers.DateTimeField(read_only=True)
    requires_qr_scan = serializers.SerializerMethodField()
    qr_payload = serializers.SerializerMethodField()

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
            "has_qr",
            "qr_attached",
            "qr_attached_at",
            "requires_qr_scan",
            "qr_payload",
            "created_at",
        )

    def get_has_qr(self, obj):
        # Late binding: "has QR" only after glue+scan attach.
        return bool(obj.qr_token and obj.qr_attached_at)

    def get_qr_attached(self, obj):
        return bool(obj.qr_token and obj.qr_attached_at)

    def get_requires_qr_scan(self, obj):
        return bool(obj.qr_token and obj.qr_attached_at)

    def get_qr_payload(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        if (
            not obj.qr_token
            or not obj.qr_attached_at
            or not user
            or not user.is_authenticated
        ):
            return None
        if user.id != obj.owner_id:
            return None
        from mainApp.copy_qr import qr_payload_for_token

        return qr_payload_for_token(obj.qr_token)

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
    confirm_extra = serializers.BooleanField(required=False, default=False)


class AddBookManualSerializer(serializers.Serializer):
    isbn = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    title = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    authors = serializers.CharField(required=False, allow_blank=True, default="")
    publisher = serializers.CharField(required=False, allow_blank=True, default="")
    publish_date = serializers.CharField(required=False, allow_blank=True, default="")
    cover_url = serializers.URLField(required=False, allow_blank=True, default="")
    info_url = serializers.URLField(required=False, allow_blank=True, default="")
    cover_text = serializers.CharField(required=False, allow_blank=True, default="")
    confirm_extra = serializers.BooleanField(required=False, default=False)


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
    can_propose_due = serializers.SerializerMethodField()
    can_confirm_due = serializers.SerializerMethodField()
    can_pick_offer = serializers.SerializerMethodField()

    class Meta:
        model = BookExchangeRequest
        fields = (
            "id",
            "requester",
            "shelf_owner",
            "target_shelf",
            "offer_shelf",
            "offer_open",
            "status",
            "kind",
            "is_transmission",
            "proposed_due_date",
            "due_date_proposer",
            "due_date_confirmed",
            "can_propose_due",
            "can_confirm_due",
            "can_pick_offer",
            "created_at",
            "resolved_at",
        )

    def get_kind(self, obj):
        if obj.offer_shelf_id:
            return "exchange"
        if getattr(obj, "offer_open", False):
            return "borrow_open_exchange"
        return "borrow"

    def get_is_transmission(self, obj):
        """Pending borrow while copy is currently lent → owner would transmit to requester."""
        if obj.offer_shelf_id or obj.status != BookExchangeRequest.Status.PENDING:
            return False
        copy_id = getattr(obj.target_shelf, "copy_id", None)
        if not copy_id:
            return False
        from mainApp.exchange_service import is_copy_lent_out

        return is_copy_lent_out(copy_id)

    def _viewer(self):
        request = self.context.get("request")
        return getattr(request, "user", None) if request else None

    def get_can_propose_due(self, obj):
        user = self._viewer()
        if (
            not user
            or not user.is_authenticated
            or obj.status != BookExchangeRequest.Status.PENDING
            or obj.offer_shelf_id
        ):
            return False
        return user.id in (obj.shelf_owner_id, obj.requester_id)

    def get_can_confirm_due(self, obj):
        user = self._viewer()
        if (
            not user
            or not user.is_authenticated
            or obj.status != BookExchangeRequest.Status.PENDING
            or obj.offer_shelf_id
            or not obj.proposed_due_date
            or obj.due_date_confirmed
        ):
            return False
        proposer = obj.due_date_proposer or "requester"
        if proposer == "owner":
            return user.id == obj.requester_id
        return user.id == obj.shelf_owner_id

    def get_can_pick_offer(self, obj):
        user = self._viewer()
        return bool(
            user
            and user.is_authenticated
            and obj.status == BookExchangeRequest.Status.PENDING
            and getattr(obj, "offer_open", False)
            and not obj.offer_shelf_id
            and user.id == obj.shelf_owner_id
        )


class CreateExchangeSerializer(serializers.Serializer):
    target_shelf_id = serializers.IntegerField()
    offer_shelf_id = serializers.IntegerField(required=False, allow_null=True)
    proposed_due_date = serializers.DateField(required=False, allow_null=True)
    offer_open = serializers.BooleanField(required=False, default=False)


class PickOfferSerializer(serializers.Serializer):
    offer_shelf_id = serializers.IntegerField()


class BookBrowseGroupSerializer(serializers.Serializer):
    """Один ISBN: обкладинка + список власників + примірники для запиту."""

    book = BookSerializer()
    owners = UserPublicSerializer(many=True)
    owners_label = serializers.CharField(required=False, allow_blank=True)
    copies = ShelfSerializer(many=True)

    def to_representation(self, instance):
        # instance: {book, owners, shelves, owners_label?}
        ctx = self.context
        owners = instance.get("owners") or []
        label = instance.get("owners_label") or " + ".join(u.username for u in owners)
        return {
            "book": BookSerializer(instance["book"], context=ctx).data,
            "owners": UserPublicSerializer(owners, many=True, context=ctx).data,
            "owners_label": label,
            "copies": ShelfSerializer(
                instance["shelves"], many=True, context=ctx
            ).data,
        }


class MessageSerializer(serializers.ModelSerializer):
    sender = UserPublicSerializer(read_only=True)
    recipient = UserPublicSerializer(read_only=True)
    library_invite = serializers.SerializerMethodField()
    library_action = serializers.SerializerMethodField()
    exchange_request_detail = serializers.SerializerMethodField()

    class Meta:
        model = PrivateMessage
        fields = (
            "id",
            "sender",
            "recipient",
            "body",
            "exchange_request",
            "exchange_request_detail",
            "library_invite",
            "library_action",
            "created_at",
            "read_at",
            "is_system",
        )

    def get_exchange_request_detail(self, obj):
        req = obj.exchange_request
        if not req:
            return None
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        pending = req.status == "pending"
        can_accept = bool(
            user
            and user.is_authenticated
            and pending
            and req.shelf_owner_id == user.id
        )
        can_reject = can_accept
        can_cancel = bool(
            user
            and user.is_authenticated
            and pending
            and req.requester_id == user.id
        )
        title = ""
        try:
            title = req.target_shelf.book.title
        except Exception:
            pass
        offer_open = bool(getattr(req, "offer_open", False)) and not req.offer_shelf_id
        can_pick_offer = bool(can_accept and offer_open)
        if req.offer_shelf_id:
            kind = "exchange"
        elif offer_open:
            kind = "borrow_open_exchange"
        else:
            kind = "loan"
        return {
            "id": req.id,
            "status": req.status,
            "kind": kind,
            "offer_open": bool(getattr(req, "offer_open", False)),
            "is_transmission": bool(
                getattr(req, "is_transmission", False)
                or (
                    not req.offer_shelf_id
                    and getattr(getattr(req, "target_shelf", None), "borrowed_from_id", None)
                )
            ),
            "book_title": title,
            "proposed_due_date": (
                req.proposed_due_date.isoformat() if req.proposed_due_date else None
            ),
            "due_date_proposer": getattr(req, "due_date_proposer", None) or "requester",
            "due_date_confirmed": bool(getattr(req, "due_date_confirmed", False)),
            "can_accept": can_accept,
            "can_reject": can_reject,
            "can_cancel": can_cancel,
            "can_pick_offer": can_pick_offer,
            "can_propose_due": bool(
                pending
                and user
                and user.is_authenticated
                and not req.offer_shelf_id
                and user.id in (req.shelf_owner_id, req.requester_id)
            ),
            "can_confirm_due": bool(
                pending
                and user
                and user.is_authenticated
                and not req.offer_shelf_id
                and req.proposed_due_date
                and not getattr(req, "due_date_confirmed", False)
                and (
                    (
                        (getattr(req, "due_date_proposer", None) or "requester") == "owner"
                        and user.id == req.requester_id
                    )
                    or (
                        (getattr(req, "due_date_proposer", None) or "requester") != "owner"
                        and user.id == req.shelf_owner_id
                    )
                )
            ),
        }

    def get_library_invite(self, obj):
        inv = obj.library_invite
        if not inv:
            return None
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        can_respond = bool(
            user
            and user.is_authenticated
            and inv.status == "pending"
            and inv.to_user_id == user.id
        )
        can_cancel = bool(
            user
            and user.is_authenticated
            and inv.status in ("pending", "awaiting_isbn")
            and (inv.from_user_id == user.id)
        )
        overlap = None
        if can_respond:
            try:
                from mainApp.library_service import (
                    ensure_personal_library,
                    merge_overlap_preview,
                )

                overlap = merge_overlap_preview(
                    inv.library, ensure_personal_library(user)
                )
            except Exception:
                overlap = []
        return {
            "id": inv.id,
            "status": inv.status,
            "library_name": inv.library.display_name if inv.library_id else "",
            "message": inv.message,
            "can_respond": can_respond,
            "can_cancel": can_cancel,
            "overlap": overlap,
        }

    def get_library_action(self, obj):
        act = obj.library_action
        if not act:
            return None
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        payload = act.payload or {}
        can_decide = bool(
            user
            and user.is_authenticated
            and act.status == "pending"
            and act.library_id
            and act.library.admin_id == user.id
        )
        return {
            "id": act.id,
            "status": act.status,
            "action_type": act.action_type,
            "action_type_label": act.get_action_type_display(),
            "title": payload.get("title") or "",
            "isbn": payload.get("isbn") or "",
            "existing_count": payload.get("existing_count") or 0,
            "count": payload.get("count") or 1,
            "can_decide": can_decide,
            "initiator_username": (
                act.initiator.username if act.initiator_id else ""
            ),
        }


class SendMessageSerializer(serializers.Serializer):
    body = serializers.CharField()


class LoanHandoffSerializer(serializers.ModelSerializer):
    owner = UserPublicSerializer(read_only=True)
    from_user = UserPublicSerializer(read_only=True)
    to_user = UserPublicSerializer(read_only=True)
    book_title = serializers.CharField(source="copy.book.title", read_only=True)
    copy_id = serializers.IntegerField(read_only=True)
    requires_qr_scan = serializers.SerializerMethodField()
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
            "requires_qr_scan",
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

    def get_requires_qr_scan(self, obj):
        c = getattr(obj, "copy", None)
        return bool(c and c.qr_token and c.qr_attached_at)

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
