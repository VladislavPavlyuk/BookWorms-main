from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

import logging

from mainApp.exchange_service import (
    accept_exchange_request,
    add_owned_copy,
    cancel_exchange_request,
    cancel_loan_handoff,
    confirm_borrow_return,
    confirm_exchange_due_date,
    confirm_handoff_give,
    confirm_handoff_receive,
    create_exchange_request,
    ensure_shelves_have_copies,
    get_or_create_book_from_payload,
    is_copy_lent_out,
    propose_exchange_due_date,
    reject_exchange_request,
    remove_owned_shelf,
    request_borrow_return,
    resolve_and_sync_book_by_isbn,
)
from mainApp import queue_service
from mainApp.message_service import mark_messages_read_for_user
from mainApp.messaging import (
    MessagingForbidden,
    MessagingNotFound,
    get_messaging_service,
)
from mainApp.notification_service import (
    list_notifications,
    notification_payload,
    unread_count,
)
from mainApp.models import (
    Book,
    BookCopy,
    BookExchangeRequest,
    Comment,
    CopyEvent,
    Like,
    Post,
    PrivateMessage,
    Shelf,
)
from mainApp.exceptions import ExchangeError
from mainApp.book_lookup import normalize_isbn

from mainApp.web3forms_mail import (
    activation_payload,
    activation_url_for,
    stash_web3forms_bridge,
)
from mainApp.registration_service import (
    activation_timeout,
    is_activation_expired,
    purge_expired_unactivated_users,
)
from .serializers import (
    AddBookManualSerializer,
    AddIsbnSerializer,
    BookBrowseGroupSerializer,
    BookCopySerializer,
    BookSerializer,
    CommentSerializer,
    CopyEventSerializer,
    CopyListingSerializer,
    CreateExchangeSerializer,
    ExchangeRequestSerializer,
    LoanHandoffSerializer,
    MeSerializer,
    MeUpdateSerializer,
    MessageSerializer,
    PostSerializer,
    PostWriteSerializer,
    ReaderAgeSerializer,
    RegisterSerializer,
    SendMessageSerializer,
    ShelfSerializer,
    UpdateBookManualSerializer,
    UserPublicSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


def _tokens(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": MeSerializer(user, context={"request": None}).data,
    }


def _error(detail, code=400):
    return Response({"detail": detail}, status=code)


class PostPagination(PageNumberPagination):
    page_size = 10


def _annotate_posts(qs, user):
    qs = qs.annotate(
        likes_count=Count("likes", distinct=True),
        comments_count=Count("comments", distinct=True),
    )
    if user.is_authenticated:
        qs = qs.annotate(
            liked_by_me=Exists(Like.objects.filter(post=OuterRef("pk"), user=user))
        )
    return qs


def _posts_same_book(book):
    if not book:
        return Post.objects.none()
    q = Q(book=book)
    isbn = (book.isbn or "").strip()
    if isbn:
        q |= Q(book__isbn=isbn)
    title = (book.title or "").strip()
    if title:
        q |= Q(book__title__iexact=title)
    return Post.objects.filter(q, book__isnull=False)


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """
    Cheap by default — docker/nginx probe every ~15s must not block gthread workers.
    ?deep=1 → purge status + Open Library ping (short timeout).
    ?test_mail=1 → Web3Forms probe.
    """
    from django.db import connection

    payload = {
        "status": "ok",
        "app": "rechenets",
        "code_rev": "2026-09-24-handoff-for-update",
    }
    try:
        connection.ensure_connection()
        payload["db"] = "ok"
    except Exception as e:
        payload["status"] = "degraded"
        payload["db"] = f"fail: {e}"

    if request.GET.get("deep") == "1":
        from mainApp.book_lookup import metadata_providers_ping
        from mainApp.registration_service import purge_status

        payload.update(purge_status())
        payload.update(metadata_providers_ping())

    if request.GET.get("test_mail") == "1":
        from mainApp.web3forms_mail import Web3FormsError, send_web3forms

        payload["web3forms_key_set"] = bool(getattr(settings, "WEB3FORMS_ACCESS_KEY", ""))
        payload["web3forms_key_suffix"] = (
            getattr(settings, "WEB3FORMS_ACCESS_KEY", "") or ""
        )[-6:]
        payload["public_base_url"] = getattr(settings, "PUBLIC_BASE_URL", "") or None
        try:
            send_web3forms(
                {
                    "access_key": settings.WEB3FORMS_ACCESS_KEY,
                    "subject": "Реченець — health test",
                    "from_name": "Реченець",
                    "name": "health-check",
                    "email": "health@localhost",
                    "message": "Тестовий ping з /api/health/?test_mail=1 — якщо бачиш цей лист, Web3Forms працює.",
                }
            )
            payload["web3forms_test"] = "accepted"
        except Web3FormsError as e:
            payload["web3forms_test"] = f"failed: {e}"
        except Exception as e:
            payload["web3forms_test"] = f"error: {e}"
    return Response(payload)


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    purge_expired_unactivated_users()
    ser = RegisterSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    user = User(
        username=ser.validated_data["username"],
        email=ser.validated_data["email"],
        biography=ser.validated_data.get("biography") or "",
        is_active=bool(settings.SKIP_EMAIL_ACTIVATION),
        email_confirmed=bool(settings.SKIP_EMAIL_ACTIVATION),
    )
    user.set_password(ser.validated_data["password"])
    user.save()
    minutes = int(activation_timeout().total_seconds() // 60)
    if not user.is_active:
        url = activation_url_for(user, request)
        w3_payload = activation_payload(user, url)
        # Free Web3Forms: server-side і RN fetch блокуються.
        # Лист іде лише з браузерної bridge-сторінки (FormData + Origin).
        email_sent = False
        server_error = (
            "Free Web3Forms: лише client-side. Відкрий web3forms_browser_url у браузері."
        )
        bridge = stash_web3forms_bridge(w3_payload, url, request)
        return Response(
            {
                "detail": (
                    f"Акаунт створено. Підтвердіть протягом {minutes} хв. "
                    f"Відкриється сторінка відправки листа; також є лінк активації."
                ),
                "needs_activation": True,
                "email_sent": email_sent,
                "server_error": server_error,
                "web3forms_payload": w3_payload,
                "web3forms_browser_url": bridge,
                "activation_url": url,
                "activation_timeout_minutes": minutes,
            },
            status=status.HTTP_201_CREATED,
        )
    payload = _tokens(user)
    payload["user"] = MeSerializer(user, context={"request": request}).data
    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    purge_expired_unactivated_users()
    username = (request.data.get("username") or "").strip()
    password = request.data.get("password") or ""
    user = User.objects.filter(username=username).first()
    if user is None or not user.check_password(password):
        return _error("Невірний логін або пароль.", 401)
    if not user.is_active:
        if is_activation_expired(user):
            user.delete()
            return _error("Час підтвердження email вичерпано. Акаунт видалено — зареєструйтесь знову.", 403)
        minutes = int(activation_timeout().total_seconds() // 60)
        return _error(
            f"Акаунт не активовано. Підтвердіть email протягом {minutes} хв після реєстрації.",
            403,
        )
    payload = _tokens(user)
    payload["user"] = MeSerializer(user, context={"request": request}).data
    return Response(payload)


@api_view(["GET", "PATCH"])
@parser_classes([JSONParser, MultiPartParser, FormParser])
def me(request):
    if request.method == "GET":
        return Response(MeSerializer(request.user, context={"request": request}).data)
    ser = MeUpdateSerializer(request.user, data=request.data, partial=True)
    ser.is_valid(raise_exception=True)
    ser.save()
    return Response(MeSerializer(request.user, context={"request": request}).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def contact_config(request):
    """Public Web3Forms config for RN / SPA client-side submit (same as /contact/)."""
    from mainApp.forms import (
        CONTACT_MAX_FILE_BYTES,
        CONTACT_MAX_SCREENSHOTS,
        CONTACT_MESSAGE_MAX,
    )

    return Response(
        {
            "access_key": (settings.WEB3FORMS_ACCESS_KEY or "").strip(),
            "endpoint": "https://api.web3forms.com/submit",
            "max_screenshots": CONTACT_MAX_SCREENSHOTS,
            "max_file_bytes": CONTACT_MAX_FILE_BYTES,
            "message_max": CONTACT_MESSAGE_MAX,
            "to_hint": "vladpavliuk@gmail.com",
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def post_list(request):
    from mainApp.feed_resume import (
        FEED_ORDER,
        feed_queryset,
        qs_from_post_inclusive,
    )

    filter_my = request.GET.get("filter") == "my" and request.user.is_authenticated
    qs = feed_queryset(filter_my=filter_my, user=request.user)

    # Resume: стрічка починаючи з last watched (включно) → вниз до старіших
    from_id = request.GET.get("from_id") or request.GET.get("resume_from")
    if from_id and str(from_id).isdigit():
        anchor = qs.filter(pk=int(from_id)).first()
        if anchor:
            qs = qs_from_post_inclusive(qs, anchor).order_by(*FEED_ORDER)

    comments_qs = Comment.objects.select_related("author").order_by("created_at")
    qs = qs.prefetch_related(Prefetch("comments", queryset=comments_qs))
    qs = _annotate_posts(qs, request.user)
    paginator = PostPagination()
    page = paginator.paginate_queryset(qs, request)
    ser = PostSerializer(page, many=True, context={"request": request})
    return paginator.get_paginated_response(ser.data)


@api_view(["POST"])
def post_mark_watched(request, post_id):
    from mainApp.feed_resume import set_last_watched_post

    post = set_last_watched_post(request.user, post_id)
    if not post:
        return _error("Пост не знайдено.", 404)
    return Response({"ok": True, "last_watched_post_id": post.id})


@api_view(["GET"])
@permission_classes([AllowAny])
def book_search(request):
    """Пошук по довіднику Book (не по постах)."""
    from mainApp.feed_search import apply_book_search, search_active

    if not search_active(request.GET) and not any(request.GET.keys()):
        qs = Book.objects.all().order_by("title")
    else:
        qs = apply_book_search(Book.objects.all(), request.GET)
    paginator = PostPagination()
    page = paginator.paginate_queryset(qs, request)
    ser = BookSerializer(page, many=True, context={"request": request})
    return paginator.get_paginated_response(ser.data)


@api_view(["POST"])
def post_create(request):
    ser = PostWriteSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    book = None
    book_id = ser.validated_data.get("book_id")
    if book_id:
        if not Shelf.objects.filter(user=request.user, book_id=book_id).exists():
            return _error("Книги немає на вашій полиці.")
        book = Book.objects.filter(pk=book_id).first()
        if book and not ser.validated_data.get("confirm_new_post"):
            related = (
                _posts_same_book(book)
                .exclude(author=request.user)
                .select_related("author", "book")
            )
            if related.exists():
                return Response(
                    {
                        "needs_confirm": True,
                        "detail": "Інші користувачі вже писали про цю книгу.",
                        "related_posts": PostSerializer(
                            related[:10], many=True, context={"request": request}
                        ).data,
                    },
                    status=409,
                )
    post = Post.objects.create(
        author=request.user,
        title=ser.validated_data["title"][:200],
        text=ser.validated_data["text"],
        book=book,
    )
    post = _annotate_posts(
        Post.objects.filter(pk=post.pk).select_related("author", "book"),
        request.user,
    ).first()
    return Response(PostSerializer(post, context={"request": request}).data, status=201)


@api_view(["GET", "PATCH", "DELETE"])
def post_detail(request, post_id):
    post = Post.objects.select_related("author", "book").filter(pk=post_id).first()
    if not post:
        return _error("Пост не знайдено.", 404)
    if request.method == "GET":
        comments_qs = Comment.objects.select_related("author").order_by("created_at")
        post = (
            _annotate_posts(Post.objects.filter(pk=post_id), request.user)
            .select_related("author", "book")
            .prefetch_related(Prefetch("comments", queryset=comments_qs))
            .first()
        )
        return Response(PostSerializer(post, context={"request": request}).data)
    if post.author_id != request.user.id:
        return _error("Можна змінювати лише свої пости.", 403)
    if request.method == "DELETE":
        post.delete()
        return Response(status=204)
    title = (request.data.get("title") or "").strip()
    text = (request.data.get("text") or "").strip()
    if not title or not text:
        return _error("Заповніть заголовок і текст.")
    post.title = title[:200]
    post.text = text
    post.save(update_fields=["title", "text"])
    return Response(PostSerializer(post, context={"request": request}).data)


@api_view(["POST"])
def post_like(request, post_id):
    post = Post.objects.filter(pk=post_id).first()
    if not post:
        return _error("Пост не знайдено.", 404)
    like = Like.objects.filter(post=post, user=request.user).first()
    if like:
        like.delete()
        liked = False
    else:
        Like.objects.create(post=post, user=request.user)
        liked = True
    return Response({"liked": liked, "likes_count": post.likes.count()})


@api_view(["POST"])
def post_comment(request, post_id):
    post = Post.objects.filter(pk=post_id).first()
    if not post:
        return _error("Пост не знайдено.", 404)
    ser = CommentSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    comment = Comment.objects.create(
        post=post, author=request.user, text=ser.validated_data["text"]
    )
    return Response(CommentSerializer(comment, context={"request": request}).data, status=201)


@api_view(["GET"])
def my_shelf(request):
    from mainApp.library_service import (
        ensure_personal_library,
        library_active_loans_by_copy,
        list_my_library_shelves,
    )

    shelves_all = list_my_library_shelves(request.user)
    shelves_all = ensure_shelves_have_copies(shelves_all)
    lib = ensure_personal_library(request.user)
    member_count = lib.memberships.count()
    pending = list(
        Shelf.objects.filter(borrowed_from=request.user, return_pending=True)
        .select_related("user", "book", "borrowed_from", "copy")
        .order_by("-added_at")
    )
    pending = ensure_shelves_have_copies(pending)
    loan_by_copy = library_active_loans_by_copy(lib)
    pending_by_copy = {p.copy_id: p.id for p in pending if p.copy_id}
    lent_out_count = 0
    for s in shelves_all:
        s.is_lent_out = (not s.borrowed_from_id) and (s.copy_id in loan_by_copy)
        if s.is_lent_out:
            lent_out_count += 1
        s.loan_row = None if s.borrowed_from_id else loan_by_copy.get(s.copy_id)
        s.pending_return_shelf_id = (
            None if s.borrowed_from_id else pending_by_copy.get(s.copy_id)
        )
    # Фізична наявність: без власних, що вже у позиці
    shelves = [s for s in shelves_all if not s.is_lent_out]
    from mainApp.book_price import library_price_total_uah
    from mainApp.models import BookPriceEvaluation

    ctx = {"request": request, "include_price_eval": True}
    evals = []
    for s in shelves:
        ev = getattr(s.book, "price_evaluation", None)
        if ev and ev.status == BookPriceEvaluation.Status.READY:
            evals.append(ev)
    return Response(
        {
            "shelves": ShelfSerializer(shelves, many=True, context=ctx).data,
            "pending_returns": ShelfSerializer(
                pending, many=True, context={"request": request}
            ).data,
            "lent_out_count": lent_out_count,
            "price_total_uah": str(library_price_total_uah(evals)),
            "is_shared_library": member_count >= 2,
            "shared_member_count": member_count,
            "shared_library_name": lib.display_name,
            "i_am_library_admin": lib.admin_id == request.user.id,
        }
    )


@api_view(["POST"])
def book_price_refresh(request, book_id):
    """Owner-only: re-run ISBN market price evaluation."""
    from mainApp.book_price import ensure_pending_and_schedule, serialize_evaluation
    from mainApp.models import Book

    if not Shelf.objects.filter(user=request.user, book_id=book_id).exists():
        return _error("Книга не на вашій полиці.", 403)
    book = Book.objects.filter(pk=book_id).first()
    if not book:
        return _error("Книгу не знайдено.", 404)
    ev = ensure_pending_and_schedule(book, force=True)
    return Response({"ok": True, "price_eval": serialize_evaluation(ev)})


@api_view(["GET"])
def due_slips(request):
    """Date Due Slip: позичені мною + видані мною з терміном."""
    borrowed = (
        request.user.shelf_entries.filter(borrowed_from__isnull=False)
        .select_related("book", "borrowed_from", "user")
        .order_by("due_date")
    )
    lent = (
        Shelf.objects.filter(borrowed_from=request.user)
        .select_related("book", "user", "borrowed_from")
        .order_by("due_date")
    )
    return Response(
        {
            "borrowed": ShelfSerializer(borrowed, many=True, context={"request": request}).data,
            "lent": ShelfSerializer(lent, many=True, context={"request": request}).data,
            "loan_days": settings.DEFAULT_LOAN_DAYS,
        }
    )


@api_view(["POST"])
def shelf_add_isbn(request):
    from mainApp.library_service import (
        IsbnConfirmNeeded,
        LibraryAction,
        LibraryError,
        add_copy_for_user,
    )

    ser = AddIsbnSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    book = resolve_and_sync_book_by_isbn(ser.validated_data["isbn"])
    try:
        result = add_copy_for_user(
            request.user,
            book,
            confirm_extra=bool(ser.validated_data.get("confirm_extra")),
        )
    except LibraryError as e:
        return _error(e.message)
    if isinstance(result, IsbnConfirmNeeded):
        return Response(
            {
                "needs_confirmation": True,
                "isbn": result.isbn,
                "existing_count": result.existing_count,
                "title": result.title,
                "detail": (
                    f"У бібліотеці вже є {result.existing_count} примірник(и) "
                    f"«{result.title}» (ISBN {result.isbn}). "
                    f"Додати ще один фізичний примірник?"
                ),
            },
            status=409,
        )
    if isinstance(result, LibraryAction):
        return Response(
            {
                "pending_approval": True,
                "action_id": result.id,
                "chat_partner_id": result.library.admin_id,
                "detail": (
                    "У бібліотеці вже є цей ISBN. Запит надіслано адміністратору в чат — "
                    "очікуйте підтвердження або відхилення."
                ),
            },
            status=202,
        )
    shelf = Shelf.objects.select_related("book", "borrowed_from", "user", "copy").get(
        pk=result.pk
    )
    return Response(ShelfSerializer(shelf, context={"request": request}).data, status=201)


@api_view(["POST"])
@parser_classes([JSONParser, MultiPartParser, FormParser])
def shelf_add_manual(request):
    ser = AddBookManualSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    d = ser.validated_data
    raw_isbn = (d.get("isbn") or "").strip()
    title = (d.get("title") or "").strip()
    files = request.FILES.getlist("photos")
    if not files and request.FILES.get("photo"):
        files = [request.FILES.get("photo")]
    if raw_isbn and not normalize_isbn(raw_isbn):
        return _error(
            "Невірний ISBN (10 або 13). Залиште порожнім — збережемо з фото."
        )
    if not title and not files:
        return _error("Вкажіть назву або прикріпіть хоча б одне фото обкладинки.")
    from mainApp.book_photos import create_manual_book, save_book_photos

    book = create_manual_book(
        isbn=raw_isbn,
        title=title,
        authors=(d.get("authors") or "").strip(),
        publisher=(d.get("publisher") or "").strip(),
        publish_date=(d.get("publish_date") or "").strip(),
        cover_url=(d.get("cover_url") or "").strip(),
        info_url=(d.get("info_url") or "").strip(),
        cover_text=(d.get("cover_text") or "").strip(),
    )
    save_book_photos(book, files, request=request)
    book.refresh_from_db()
    from mainApp.library_service import (
        IsbnConfirmNeeded,
        LibraryAction,
        LibraryError,
        add_copy_for_user,
    )

    try:
        result = add_copy_for_user(
            request.user,
            book,
            confirm_extra=bool(d.get("confirm_extra")),
        )
    except LibraryError as e:
        return _error(e.message)
    if isinstance(result, IsbnConfirmNeeded):
        return Response(
            {
                "needs_confirmation": True,
                "isbn": result.isbn,
                "existing_count": result.existing_count,
                "title": result.title,
                "detail": (
                    f"У бібліотеці вже є {result.existing_count} примірник(и) "
                    f"з ISBN {result.isbn}. Додати ще один?"
                ),
            },
            status=409,
        )
    if isinstance(result, LibraryAction):
        return Response(
            {
                "pending_approval": True,
                "action_id": result.id,
                "chat_partner_id": result.library.admin_id,
                "detail": (
                    "У бібліотеці вже є цей ISBN. Запит надіслано адміністратору в чат — "
                    "очікуйте підтвердження або відхилення."
                ),
            },
            status=202,
        )
    shelf = (
        Shelf.objects.select_related("book", "borrowed_from", "user", "copy")
        .prefetch_related("book__photos")
        .get(pk=result.pk)
    )
    return Response(ShelfSerializer(shelf, context={"request": request}).data, status=201)


@api_view(["POST", "PATCH", "PUT"])
@parser_classes([JSONParser, MultiPartParser, FormParser])
def shelf_update_manual(request, shelf_id):
    """Update bibliographic fields / photos of a sole-owned manually added book."""
    shelf = (
        Shelf.objects.select_related("book", "copy", "borrowed_from", "user")
        .prefetch_related("book__photos")
        .filter(pk=shelf_id, user=request.user)
        .first()
    )
    if not shelf:
        return _error("Запис не знайдено.", 404)
    if shelf.borrowed_from_id:
        return _error("Позичену книгу не можна редагувати.")
    if is_copy_lent_out(shelf.copy_id):
        return _error("Примірник зараз у позиці — спочатку дочекайтесь повернення.")

    from mainApp.book_photos import (
        delete_book_photos,
        save_book_photos,
        update_manual_book,
        user_can_edit_manual_book,
    )

    book = shelf.book
    if not user_can_edit_manual_book(request.user, book):
        return _error(
            "Редагувати можна лише власні вручну додані книги (локальний ISBN або з вашими фото).",
            403,
        )

    ser = UpdateBookManualSerializer(data=request.data, partial=True)
    ser.is_valid(raise_exception=True)
    d = ser.validated_data

    raw_delete = d.pop("delete_photo_ids", "") or ""
    if hasattr(request.data, "getlist"):
        extra = request.data.getlist("delete_photo_ids")
        if extra:
            raw_delete = ",".join(str(x) for x in extra if x)
    delete_ids: list[int] = []
    for part in str(raw_delete).replace(" ", ",").split(","):
        part = part.strip()
        if part.isdigit():
            delete_ids.append(int(part))

    try:
        book = update_manual_book(
            book,
            isbn=d["isbn"] if "isbn" in d else None,
            title=d["title"] if "title" in d else None,
            authors=d["authors"] if "authors" in d else None,
            publisher=d["publisher"] if "publisher" in d else None,
            publish_date=d["publish_date"] if "publish_date" in d else None,
            cover_url=d["cover_url"] if "cover_url" in d else None,
            info_url=d["info_url"] if "info_url" in d else None,
            cover_text=d["cover_text"] if "cover_text" in d else None,
        )
    except ValueError as exc:
        return _error(str(exc))

    if delete_ids:
        delete_book_photos(book, delete_ids)

    files = request.FILES.getlist("photos")
    if not files and request.FILES.get("photo"):
        files = [request.FILES.get("photo")]
    if files:
        save_book_photos(book, files, request=request)

    book.refresh_from_db()
    shelf = (
        Shelf.objects.select_related("book", "borrowed_from", "user", "copy")
        .prefetch_related("book__photos")
        .get(pk=shelf.pk)
    )
    return Response(ShelfSerializer(shelf, context={"request": request}).data)


@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
def shelf_recognize_cover(request):
    """AI: extract title / authors / ISBN from cover photo(s) (manual add)."""
    files = list(request.FILES.getlist("photos") or [])
    if not files:
        one = request.FILES.get("photo")
        if one:
            files = [one]
    if not files:
        return _error("Потрібне фото обкладинки (поле photo або photos).")
    from mainApp.book_cover_ai import CoverAIError, recognize_book_covers, vision_configured

    if not vision_configured():
        return _error(
            "Розпізнавання не налаштовано (OCR_SPACE_API_KEY або OPENAI_API_KEY).",
            503,
        )
    try:
        data = recognize_book_covers(files)
    except CoverAIError as exc:
        return _error(exc.message, exc.status)
    return Response(data)


@api_view(["DELETE"])
def shelf_remove(request, shelf_id):
    from mainApp.library_service import (
        LibraryAction,
        LibraryError,
        get_removable_shelf,
        request_remove_copy,
    )

    try:
        shelf = get_removable_shelf(request.user, shelf_id)
    except LibraryError as e:
        status = 404 if "не знайдено" in (e.message or "").lower() else 403
        return _error(e.message, status)
    if is_copy_lent_out(shelf.copy_id):
        return _error("Примірник зараз у позиці — спочатку дочекайтесь повернення.")
    try:
        result = request_remove_copy(request.user, shelf)
    except LibraryError as e:
        return _error(e.message)
    if isinstance(result, LibraryAction):
        return Response(
            {
                "pending_approval": True,
                "action_id": result.id,
                "chat_partner_id": result.library.admin_id,
                "detail": "Запит на видалення надіслано адміністратору в чат.",
            },
            status=202,
        )
    return Response(status=204)


@api_view(["POST"])
def shelf_reader_age(request, shelf_id):
    shelf = Shelf.objects.select_related("book").filter(pk=shelf_id, user=request.user).first()
    if not shelf:
        return _error("Запис не знайдено.", 404)
    ser = ReaderAgeSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    book = shelf.book
    book.min_readers_age = ser.validated_data["min_readers_age"]
    book.max_readers_age = ser.validated_data["max_readers_age"]
    try:
        book.full_clean()
    except DjangoValidationError as exc:
        return _error(str(exc))
    book.save(update_fields=["min_readers_age", "max_readers_age"])
    return Response(BookSerializer(book).data)


@api_view(["POST"])
def shelf_listing(request, shelf_id):
    """Admin applies listing immediately; shared-library members need approval."""
    from mainApp.library_service import (
        LibraryAction,
        LibraryError,
        request_listing_change,
    )

    shelf = (
        Shelf.objects.select_related("copy", "book", "copy__library", "copy__book")
        .filter(pk=shelf_id, user=request.user)
        .first()
    )
    if not shelf:
        return _error("Запис не знайдено.", 404)
    if shelf.borrowed_from_id:
        return _error("Статус можна змінити лише для власного примірника.")
    if not shelf.copy_id:
        return _error("Це не ваш примірник.")
    copy = shelf.copy
    ser = CopyListingSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    vd = ser.validated_data
    listing_kwargs = dict(
        flags={
            k: vd.get(k)
            for k in (
                "is_fee_sharing",
                "is_hidden",
                "is_for_rent",
                "is_for_exchange",
                "is_free_of_deposit",
            )
            if k in vd
        }
        or None,
        sale_gift=vd.get("sale_gift") if "sale_gift" in vd else None,
        sale_price=vd.get("sale_price"),
        rent_price_per_day=vd.get("rent_price_per_day"),
        listing_status=vd.get("listing_status") or None,
    )
    try:
        result = request_listing_change(request.user, copy, listing_kwargs)
    except (DjangoValidationError, LibraryError) as exc:
        return _error(str(getattr(exc, "message", exc)))
    if isinstance(result, LibraryAction):
        return Response(
            {
                "pending_approval": True,
                "action_id": result.id,
                "chat_partner_id": result.library.admin_id,
                "detail": "Запит на зміну статусу надіслано адміністратору в чат.",
            },
            status=202,
        )
    shelf.refresh_from_db()
    shelf.copy.refresh_from_db()
    return Response(ShelfSerializer(shelf, context={"request": request}).data)


@api_view(["POST"])
def shelf_bulk(request):
    """Bulk listing / delete for selected owned shelves."""
    from mainApp.library_service import (
        LibraryError,
        request_bulk_listing,
        request_bulk_remove,
    )

    shelf_ids = request.data.get("shelf_ids") or []
    if not isinstance(shelf_ids, (list, tuple)):
        return _error("shelf_ids має бути списком.")
    action = (request.data.get("action") or "").strip()
    try:
        if action == "delete":
            result = request_bulk_remove(request.user, list(shelf_ids))
        elif action == "listing":
            ser = CopyListingSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            vd = ser.validated_data
            listing_kwargs = dict(
                flags={
                    k: vd.get(k)
                    for k in (
                        "is_fee_sharing",
                        "is_hidden",
                        "is_for_rent",
                        "is_for_exchange",
                        "is_free_of_deposit",
                    )
                    if k in vd
                }
                or None,
                sale_gift=vd.get("sale_gift") if "sale_gift" in vd else None,
                sale_price=vd.get("sale_price"),
                rent_price_per_day=vd.get("rent_price_per_day"),
                listing_status=vd.get("listing_status") or None,
            )
            result = request_bulk_listing(request.user, list(shelf_ids), listing_kwargs)
        else:
            return _error("action має бути delete або listing.")
    except (DjangoValidationError, LibraryError) as exc:
        return _error(str(getattr(exc, "message", exc)))

    if result.get("pending_approval"):
        return Response(
            {
                "pending_approval": True,
                "action_id": result.get("action_id"),
                "chat_partner_id": result.get("admin_id"),
                "count": result.get("count"),
                "detail": "Запит надіслано адміністратору спільної бібліотеки в чат.",
            },
            status=202,
        )
    return Response(
        {
            "ok": True,
            "removed": result.get("removed"),
            "updated": result.get("updated"),
            "blocked": result.get("blocked") or [],
        }
    )


@api_view(["POST"])
def shelf_return(request, shelf_id):
    request_borrow_return(shelf_id, request.user)
    return Response({"ok": True})


@api_view(["POST"])
def shelf_confirm_return(request, shelf_id):
    confirm_borrow_return(shelf_id, request.user)
    return Response({"ok": True})


@api_view(["GET"])
def browse_shelves(request):
    from mainApp.exchange import get_shelf_query_service

    catalog = get_shelf_query_service().load_browse_catalog(
        request.user, ensure_copies=True
    )
    ctx = {"request": request}
    return Response(
        {
            "others": ShelfSerializer(catalog.others, many=True, context=ctx).data,
            "others_grouped": BookBrowseGroupSerializer(
                catalog.others_grouped, many=True, context=ctx
            ).data,
            "my_owned": ShelfSerializer(catalog.my_owned, many=True, context=ctx).data,
        }
    )


@api_view(["GET"])
def user_shelf(request, user_id):
    from mainApp.exchange import get_shelf_query_service

    owner = User.objects.filter(pk=user_id).first()
    if not owner:
        return _error("Користувача не знайдено.", 404)
    shelves = get_shelf_query_service().for_user_physical_shelf(
        owner, ensure_copies=True, viewer=request.user
    )
    ctx = {"request": request}
    return Response(
        {
            "user": UserPublicSerializer(owner, context=ctx).data,
            "is_own": request.user.pk == owner.pk,
            "shelves": ShelfSerializer(shelves, many=True, context=ctx).data,
        }
    )


@api_view(["GET"])
def book_detail(request, book_id):
    from mainApp.exchange import get_shelf_query_service

    book = Book.objects.filter(pk=book_id).first()
    if not book:
        return _error("Книгу не знайдено.", 404)
    holders = get_shelf_query_service().for_book_physical_holders(
        book, ensure_copies=True, viewer=request.user
    )
    owners = []
    seen = set()
    for h in holders:
        for u in getattr(h, "library_owners", None) or [
            h.borrowed_from if h.borrowed_from_id else h.user
        ]:
            if u and u.id not in seen:
                seen.add(u.id)
                owners.append(u)
    owners_label = " + ".join(u.username for u in owners)
    comments_qs = Comment.objects.select_related("author").order_by("created_at")
    posts = (
        _annotate_posts(Post.objects.filter(book=book), request.user)
        .select_related("author", "book")
        .prefetch_related(Prefetch("comments", queryset=comments_qs))
        .order_by("-created_ad")
    )
    ctx = {"request": request}
    return Response(
        {
            "book": BookSerializer(book).data,
            "owners": UserPublicSerializer(owners, many=True, context=ctx).data,
            "owners_label": owners_label,
            "holders": ShelfSerializer(holders, many=True, context=ctx).data,
            "posts": PostSerializer(posts, many=True, context=ctx).data,
        }
    )


@api_view(["GET"])
def copy_history(request, copy_id):
    """Історія подій одного примірника + поточні полиці + черга."""
    from mainApp.exchange import get_shelf_query_service

    copy = (
        BookCopy.objects.filter(pk=copy_id)
        .select_related("book", "owner")
        .first()
    )
    if not copy:
        return _error("Примірник не знайдено.", 404)
    holders = get_shelf_query_service().for_copy_physical_holders(
        copy, ensure_copies=True
    )
    events = (
        CopyEvent.objects.filter(copy=copy)
        .select_related(
            "actor",
            "holder",
            "legal_owner",
            "previous_holder",
            "previous_owner",
            "counterparty",
        )
        .order_by("-created_at")
    )
    ctx = {"request": request}
    my_entry = (
        queue_service.active_queue_qs(copy_id)
        .filter(user=request.user)
        .first()
        if request.user.is_authenticated
        else None
    )
    return Response(
        {
            "copy": BookCopySerializer(copy, context=ctx).data,
            "holders": ShelfSerializer(holders, many=True, context=ctx).data,
            "events": CopyEventSerializer(events, many=True, context=ctx).data,
            "queue": queue_service.serialize_queue(copy_id),
            "queue_length": queue_service.active_queue_qs(copy_id).count(),
            "my_queue_position": (
                queue_service.queue_position(my_entry) if my_entry else None
            ),
            "is_lent_out": is_copy_lent_out(copy_id),
        }
    )


@api_view(["GET"])
def copy_queue_list(request, copy_id):
    if not BookCopy.objects.filter(pk=copy_id).exists():
        return _error("Примірник не знайдено.", 404)
    my_entry = queue_service.active_queue_qs(copy_id).filter(user=request.user).first()
    return Response(
        {
            "queue": queue_service.serialize_queue(copy_id),
            "my_queue_position": (
                queue_service.queue_position(my_entry) if my_entry else None
            ),
            "is_lent_out": is_copy_lent_out(copy_id),
        }
    )


@api_view(["POST"])
def copy_queue_join(request, copy_id):
    copy = BookCopy.objects.filter(pk=copy_id).select_related("book", "owner").first()
    if not copy:
        return _error("Примірник не знайдено.", 404)
    entry, err = queue_service.join_queue(request.user, copy, notify=True)
    if err:
        return _error(err)
    return Response(
        {
            "ok": True,
            "position": queue_service.queue_position(entry),
            "queue": queue_service.serialize_queue(copy_id),
        },
        status=201,
    )


@api_view(["POST"])
def copy_queue_leave(request, copy_id):
    ok, err = queue_service.leave_queue(request.user, copy_id)
    if not ok:
        return _error(err or "Помилка.")
    return Response({"ok": True, "queue": queue_service.serialize_queue(copy_id)})


@api_view(["GET"])
def my_queues(request):
    """Мої активні позиції в чергах."""
    from mainApp.models import CopyQueueEntry

    entries = (
        CopyQueueEntry.objects.filter(
            user=request.user,
            status__in=queue_service.ACTIVE,
        )
        .select_related("copy", "copy__book", "copy__owner")
        .order_by("created_at")
    )
    items = []
    for e in entries:
        items.append(
            {
                "id": e.pk,
                "copy_id": e.copy_id,
                "book_title": e.copy.book.title,
                "owner_id": e.copy.owner_id,
                "owner_username": e.copy.owner.username,
                "status": e.status,
                "position": queue_service.queue_position(e),
                "created_at": e.created_at,
            }
        )
    return Response({"results": items})


@api_view(["GET"])
def exchange_list(request):
    ctx = {"request": request}
    pending_in = BookExchangeRequest.objects.filter(
        status=BookExchangeRequest.Status.PENDING,
        shelf_owner=request.user,
    ).select_related(
        "requester", "shelf_owner", "target_shelf__book", "target_shelf__user",
        "offer_shelf__book", "offer_shelf__user", "target_shelf__borrowed_from",
        "offer_shelf__borrowed_from",
    )
    pending_out = BookExchangeRequest.objects.filter(
        status=BookExchangeRequest.Status.PENDING,
        requester=request.user,
    ).select_related(
        "requester", "shelf_owner", "target_shelf__book", "target_shelf__user",
        "offer_shelf__book", "offer_shelf__user", "target_shelf__borrowed_from",
        "offer_shelf__borrowed_from",
    )
    history = (
        BookExchangeRequest.objects.filter(
            status__in=[
                BookExchangeRequest.Status.ACCEPTED,
                BookExchangeRequest.Status.REJECTED,
                BookExchangeRequest.Status.CANCELLED,
            ]
        )
        .filter(Q(requester=request.user) | Q(shelf_owner=request.user))
        .select_related(
            "requester", "shelf_owner", "target_shelf__book", "target_shelf__user",
            "offer_shelf__book", "offer_shelf__user", "target_shelf__borrowed_from",
            "offer_shelf__borrowed_from",
        )[:50]
    )
    return Response(
        {
            "pending_in": ExchangeRequestSerializer(pending_in, many=True, context=ctx).data,
            "pending_out": ExchangeRequestSerializer(pending_out, many=True, context=ctx).data,
            "history": ExchangeRequestSerializer(history, many=True, context=ctx).data,
        }
    )


@api_view(["POST"])
def exchange_create(request):
    items = request.data.get("items")
    if items is None:
        ser = CreateExchangeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        items = [ser.validated_data]
    else:
        ser = CreateExchangeSerializer(data=items, many=True)
        ser.is_valid(raise_exception=True)
        items = ser.validated_data

    created = []
    errors = []
    for row in items:
        target = Shelf.objects.filter(pk=row["target_shelf_id"]).select_related("book").first()
        if not target:
            errors.append(f"Полицю #{row['target_shelf_id']} не знайдено.")
            continue
        offer = None
        oid = row.get("offer_shelf_id")
        if is_copy_lent_out(target.copy_id) or target.borrowed_from_id:
            oid = None
        if oid:
            from mainApp.exchange import get_shelf_query_service

            offer = get_shelf_query_service().get_available_owned_offer(
                request.user, oid
            )
            if not offer:
                errors.append(
                    f'"{target.book.title[:45]}": книгу для обміну не знайдено серед вільних.'
                )
                continue
        try:
            req = create_exchange_request(
                request.user,
                target,
                offer,
                proposed_due_date=row.get("proposed_due_date"),
            )
            created.append(req)
        except ExchangeError as exc:
            errors.append(f'"{target.book.title[:45]}": {exc.message}')
    ctx = {"request": request}
    return Response(
        {
            "created": ExchangeRequestSerializer(created, many=True, context=ctx).data,
            "errors": errors,
        },
        status=201 if created else 400,
    )


def _exchange_action(request, request_id, fn, **kwargs):
    fn(request_id, request.user, **kwargs)
    return Response({"ok": True})


@api_view(["POST"])
def exchange_accept_view(request, request_id):
    due = request.data.get("due_date") if hasattr(request, "data") else None
    return _exchange_action(
        request, request_id, accept_exchange_request, due_date=due
    )


@api_view(["POST"])
def exchange_propose_due_view(request, request_id):
    due = request.data.get("due_date") or request.data.get("proposed_due_date")
    try:
        req = propose_exchange_due_date(request_id, request.user, due)
    except ExchangeError as exc:
        return _error(exc.message, getattr(exc, "status", 400) or 400)
    return Response(
        ExchangeRequestSerializer(req, context={"request": request}).data
    )


@api_view(["POST"])
def exchange_confirm_due_view(request, request_id):
    try:
        req = confirm_exchange_due_date(request_id, request.user)
    except ExchangeError as exc:
        return _error(exc.message, getattr(exc, "status", 400) or 400)
    return Response(
        ExchangeRequestSerializer(req, context={"request": request}).data
    )


@api_view(["POST"])
def exchange_reject_view(request, request_id):
    return _exchange_action(request, request_id, reject_exchange_request)


@api_view(["POST"])
def exchange_cancel_view(request, request_id):
    return _exchange_action(request, request_id, cancel_exchange_request)


@api_view(["GET"])
def message_partners(request):
    partners = get_messaging_service().list_partners(request.user)
    return Response(UserPublicSerializer(partners, many=True, context={"request": request}).data)


@api_view(["GET", "POST"])
def message_thread(request, partner_id):
    chat = get_messaging_service()
    if request.method == "POST":
        ser = SendMessageSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            msg = chat.send(request.user, partner_id, ser.validated_data["body"])
        except MessagingForbidden as exc:
            return _error(exc.message, 403)
        except MessagingNotFound as exc:
            return _error(exc.message, 404)
        if not msg:
            return _error("Порожній текст.")
        return Response(
            MessageSerializer(msg, context={"request": request}).data, status=201
        )

    try:
        thread = chat.open_thread(request.user, partner_id)
    except MessagingForbidden as exc:
        return _error(exc.message, 403)
    except MessagingNotFound as exc:
        return _error(exc.message, 404)

    pending_returns = ensure_shelves_have_copies(list(thread.pending_returns))
    ctx = {"request": request}
    return Response(
        {
            "partner": UserPublicSerializer(thread.partner, context=ctx).data,
            "messages": MessageSerializer(thread.timeline, many=True, context=ctx).data,
            "pending_in": ExchangeRequestSerializer(
                thread.pending_in, many=True, context=ctx
            ).data,
            "pending_out": ExchangeRequestSerializer(
                thread.pending_out, many=True, context=ctx
            ).data,
            "pending_returns": ShelfSerializer(
                pending_returns, many=True, context=ctx
            ).data,
            "handoffs": LoanHandoffSerializer(
                thread.handoffs, many=True, context=ctx
            ).data,
            "library_invites_in": thread.library_invites_in,
            "library_invites_out": thread.library_invites_out,
            "library_actions_in": thread.library_actions_in,
            "library_actions_out": thread.library_actions_out,
        }
    )


@api_view(["POST"])
def handoff_confirm_give(request, handoff_id):
    qr = None
    if hasattr(request, "data"):
        qr = request.data.get("qr_payload") or request.data.get("qr")
    try:
        confirm_handoff_give(handoff_id, request.user, qr_payload=qr)
    except ExchangeError as exc:
        return _error(exc.message, exc.http_status)
    return Response({"ok": True})


@api_view(["POST"])
def handoff_confirm_receive(request, handoff_id):
    qr = None
    if hasattr(request, "data"):
        qr = request.data.get("qr_payload") or request.data.get("qr")
    try:
        confirm_handoff_receive(handoff_id, request.user, qr_payload=qr)
    except ExchangeError as exc:
        return _error(exc.message, exc.http_status)
    return Response({"ok": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def copy_qr_ensure_api(request, copy_id):
    """Late binding: no token on copy until scan. Point client to print."""
    copy = BookCopy.objects.filter(pk=copy_id).select_related("book", "owner").first()
    if not copy:
        return _error("Примірник не знайдено.", 404)
    if copy.owner_id != request.user.id:
        return _error("QR може друкувати лише власник.", 403)
    from mainApp.copy_qr import serialize_copy_qr

    return Response(
        {
            "ok": True,
            "late_binding": True,
            "detail": "Роздрукуйте наклейки, наклейте, потім Скан QR.",
            "copy": BookCopySerializer(copy, context={"request": request}).data,
            "qr": serialize_copy_qr(copy),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def copy_qr_attach_api(request, copy_id):
    from mainApp.copy_qr import attach_copy_qr, serialize_copy_qr

    payload = request.data.get("qr_payload") or request.data.get("qr") or ""
    try:
        copy = attach_copy_qr(copy_id, request.user, payload)
    except ExchangeError as exc:
        return _error(exc.message, exc.http_status)
    return Response(
        {
            "ok": True,
            "copy": BookCopySerializer(copy, context={"request": request}).data,
            "qr": serialize_copy_qr(copy),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def copy_qr_rotate_api(request, copy_id):
    from mainApp.copy_qr import rotate_copy_qr, serialize_copy_qr

    try:
        copy = rotate_copy_qr(copy_id, request.user)
    except ExchangeError as exc:
        return _error(exc.message, exc.http_status)
    return Response(
        {
            "ok": True,
            "copy": BookCopySerializer(copy, context={"request": request}).data,
            "qr": serialize_copy_qr(copy),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def copy_qr_resolve_api(request):
    """Identify a book instance by scanned QR; optional handoff confirm."""
    from mainApp.copy_qr import resolve_copy_by_qr, serialize_copy_qr
    from mainApp.exchange.handoff import active_handoff_for_copy

    payload = request.data.get("qr_payload") or request.data.get("qr") or ""
    action = (request.data.get("action") or "").strip()
    handoff_id = request.data.get("handoff_id")
    try:
        if handoff_id and action in ("give", "receive"):
            if action == "give":
                confirm_handoff_give(
                    int(handoff_id), request.user, qr_payload=payload
                )
            else:
                confirm_handoff_receive(
                    int(handoff_id), request.user, qr_payload=payload
                )
            return Response({"ok": True, "action": action, "handoff_id": int(handoff_id)})
        copy = resolve_copy_by_qr(payload)
    except ExchangeError as exc:
        return _error(exc.message, exc.http_status)
    except (TypeError, ValueError):
        return _error("Некоректний handoff_id.", 400)
    handoff = active_handoff_for_copy(copy.id)
    return Response(
        {
            "copy": BookCopySerializer(copy, context={"request": request}).data,
            "qr": serialize_copy_qr(copy),
            "active_handoff": (
                LoanHandoffSerializer(handoff, context={"request": request}).data
                if handoff
                else None
            ),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def copy_qr_print_labels_api(request):
    """JSON labels (data-URI PNGs) for A4 print / client rendering."""
    from mainApp.copy_qr import (
        A4_COLS,
        A4_ROWS,
        LABEL_H_MM,
        LABEL_W_MM,
        QR_PRINT_MM,
        SLOTS_PER_A4_PAGE,
        build_full_a4_print_pages,
    )

    raw = request.query_params.get("ids") or ""
    copy_ids = [int(x) for x in raw.split(",") if x.strip().isdigit()]
    single = request.query_params.get("copy_id")
    if single and str(single).isdigit():
        copy_ids = [int(single)]
    pages_raw = request.query_params.get("pages") or "1"
    try:
        page_count = max(1, min(20, int(pages_raw)))
    except ValueError:
        page_count = 1
    pages = build_full_a4_print_pages(
        request.user, copy_ids=copy_ids or None, page_count=page_count
    )

    def lab_json(lab):
        return {
            "copy_id": lab.copy_id,
            "title": lab.title,
            "payload": lab.payload,
            "data_uri": lab.data_uri,
            "attached": lab.attached,
        }

    return Response(
        {
            "qr_mm": float(f"{QR_PRINT_MM:g}"),
            "label_w_mm": float(f"{LABEL_W_MM:.4f}"),
            "label_h_mm": float(f"{LABEL_H_MM:.4f}"),
            "cols": A4_COLS,
            "rows": A4_ROWS,
            "slots_per_page": SLOTS_PER_A4_PAGE,
            "pages": [[lab_json(lab) for lab in page] for page in pages],
            "labels": [lab_json(lab) for page in pages for lab in page],
        }
    )


@api_view(["POST"])
def handoff_cancel(request, handoff_id):
    cancel_loan_handoff(handoff_id, request.user)
    return Response({"ok": True})


@api_view(["GET"])
def notifications_list(request):
    """Скринька сповіщень (запити на книги) з chat_partner_id для переходу в чат."""
    items = []
    for m in list_notifications(request.user, limit=80):
        p = notification_payload(m)
        p["created_at"] = m.created_at
        p["read_at"] = m.read_at
        p["sender"] = UserPublicSerializer(m.sender, context={"request": request}).data
        items.append(p)
    return Response(
        {
            "unread_count": unread_count(request.user),
            "results": items,
        }
    )


@api_view(["GET"])
def notifications_unread_count(request):
    return Response({"unread_count": unread_count(request.user)})


@api_view(["POST"])
def notifications_mark_read(request):
    """
    body: { "ids": [1,2] } — конкретні; без ids — усі непрочитані.
    """
    ids = request.data.get("ids")
    if ids is not None and not isinstance(ids, list):
        return _error("ids має бути списком.")
    n = mark_messages_read_for_user(request.user, ids if ids is not None else None)
    return Response({"marked": n, "unread_count": unread_count(request.user)})


@api_view(["GET"])
def library_mine(request):
    from mainApp.library_service import library_snapshot

    return Response(library_snapshot(request.user))


@api_view(["POST"])
def library_invite(request):
    from mainApp.library_service import LibraryError, invite_to_library

    username = (request.data.get("username") or "").strip()
    message = (request.data.get("message") or "").strip()
    if not username:
        return _error("Вкажіть username.")
    try:
        inv = invite_to_library(request.user, username, message)
    except LibraryError as e:
        return _error(e.message)
    return Response(
        {
            "id": inv.id,
            "to_username": inv.to_user.username,
            "to_user_id": inv.to_user_id,
            "chat_partner_id": inv.to_user_id,
        },
        status=201,
    )


@api_view(["POST"])
def library_invite_cancel(request, invite_id):
    from mainApp.library_service import LibraryError, cancel_invite

    try:
        cancel_invite(request.user, invite_id)
    except LibraryError as e:
        return _error(e.message)
    return Response({"ok": True})


@api_view(["POST"])
def library_invite_reject(request, invite_id):
    from mainApp.library_service import LibraryError, reject_invite

    try:
        reject_invite(request.user, invite_id)
    except LibraryError as e:
        return _error(e.message)
    return Response({"ok": True})


@api_view(["POST"])
def library_invite_accept(request, invite_id):
    from mainApp.library_service import AwaitAdminIsbn, LibraryError, accept_invite

    try:
        result = accept_invite(request.user, invite_id)
    except LibraryError as e:
        return _error(e.message)
    if isinstance(result, AwaitAdminIsbn):
        return Response(
            {
                "awaiting_admin_isbn": True,
                "invite_id": result.invite.id,
                "overlap": result.overlap,
                "detail": (
                    "Об'єднання очікує підтвердження кількості примірників адміністратором."
                ),
            },
            status=200,
        )
    return Response(
        {"ok": True, "library_id": result.id, "name": result.display_name}
    )


@api_view(["POST"])
def library_invite_confirm_isbn(request, invite_id):
    from mainApp.library_service import LibraryError, admin_confirm_merge_isbn

    raw = request.data.get("isbn_counts") or {}
    if not isinstance(raw, dict):
        return _error("isbn_counts має бути об'єктом {isbn: count}.")
    try:
        lib = admin_confirm_merge_isbn(request.user, invite_id, isbn_counts=raw)
    except LibraryError as e:
        overlap = getattr(e, "overlap", None)
        if overlap is not None:
            return Response(
                {
                    "needs_isbn_counts": True,
                    "awaiting_admin_isbn": True,
                    "overlap": overlap,
                    "detail": e.message,
                },
                status=409,
            )
        return _error(e.message)
    return Response({"ok": True, "library_id": lib.id, "name": lib.display_name})


@api_view(["POST"])
def library_action_resolve(request, action_id):
    from mainApp.library_service import LibraryError, resolve_action

    approve = bool(request.data.get("approve", True))
    try:
        action = resolve_action(request.user, action_id, approve=approve)
    except LibraryError as e:
        return _error(e.message)
    return Response(
        {
            "ok": True,
            "status": action.status,
            "action_id": action.id,
            "result_note": action.result_note,
        }
    )


@api_view(["POST"])
def library_split_leave(request):
    from mainApp.library_service import LibraryAction, LibraryError, request_split_leave

    copy_ids = request.data.get("copy_ids") or []
    if not isinstance(copy_ids, list):
        return _error("copy_ids має бути списком.")
    try:
        result = request_split_leave(request.user, copy_ids)
    except LibraryError as e:
        return _error(e.message)
    if isinstance(result, LibraryAction):
        return Response(
            {
                "pending_approval": True,
                "action_id": result.id,
                "detail": "Запит на вихід/поділ надіслано адміністратору.",
            },
            status=202,
        )
    return Response({"ok": True, "library_id": result.id})


@api_view(["POST"])
def library_election_start(request):
    from mainApp.library_service import LibraryError, election_tally, start_admin_election

    try:
        el = start_admin_election(
            request.user, reason=(request.data.get("reason") or "")[:200]
        )
    except LibraryError as e:
        return _error(e.message)
    return Response(election_tally(el), status=201)


@api_view(["POST"])
def library_election_vote(request, election_id):
    from mainApp.library_service import LibraryError, cast_admin_vote, election_tally

    try:
        cid = int(request.data.get("candidate_id"))
    except (TypeError, ValueError):
        return _error("candidate_id обов'язковий.")
    try:
        el = cast_admin_vote(request.user, election_id, cid)
    except LibraryError as e:
        return _error(e.message)
    data = election_tally(el)
    data["status"] = el.status
    data["winner_id"] = el.winner_id
    return Response(data)


@api_view(["POST"])
def library_election_finalize(request, election_id):
    from mainApp.library_service import LibraryError, election_tally, finalize_admin_election

    try:
        el = finalize_admin_election(request.user, election_id)
    except LibraryError as e:
        return _error(e.message)
    data = election_tally(el) if el.status == "open" else {
        "election_id": el.id,
        "status": el.status,
        "winner_id": el.winner_id,
    }
    return Response(data)


@api_view(["POST"])
def library_election_cancel(request, election_id):
    from mainApp.library_service import LibraryError, cancel_admin_election

    try:
        el = cancel_admin_election(request.user, election_id)
    except LibraryError as e:
        return _error(e.message)
    return Response({"ok": True, "status": el.status})
