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
    confirm_handoff_give,
    confirm_handoff_receive,
    create_exchange_request,
    ensure_shelves_have_copies,
    get_or_create_book_from_payload,
    is_copy_lent_out,
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
    shelves_all = list(
        request.user.shelf_entries.select_related("book", "borrowed_from", "user", "copy")
        .order_by("-added_at")
    )
    shelves_all = ensure_shelves_have_copies(shelves_all)
    pending = list(
        Shelf.objects.filter(borrowed_from=request.user, return_pending=True)
        .select_related("user", "book", "borrowed_from", "copy")
        .order_by("-added_at")
    )
    pending = ensure_shelves_have_copies(pending)
    loan_by_copy = {
        row.copy_id: row
        for row in Shelf.objects.filter(borrowed_from=request.user).select_related(
            "user", "book", "copy"
        )
        if row.copy_id
    }
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
    return Response(
        {
            "shelves": ShelfSerializer(shelves, many=True, context={"request": request}).data,
            "pending_returns": ShelfSerializer(
                pending, many=True, context={"request": request}
            ).data,
            "lent_out_count": lent_out_count,
        }
    )


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
    ser = AddIsbnSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    book = resolve_and_sync_book_by_isbn(ser.validated_data["isbn"])
    shelf = add_owned_copy(request.user, book)
    shelf = Shelf.objects.select_related("book", "borrowed_from", "user", "copy").get(
        pk=shelf.pk
    )
    return Response(ShelfSerializer(shelf, context={"request": request}).data, status=201)


@api_view(["POST"])
def shelf_add_manual(request):
    ser = AddBookManualSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    d = ser.validated_data
    isbn = normalize_isbn(d["isbn"])
    if not isbn:
        return _error("Невірний ISBN.")
    payload = {
        "isbn": isbn,
        "title": d["title"].strip(),
        "authors": (d.get("authors") or "").strip(),
        "publisher": (d.get("publisher") or "").strip(),
        "publish_date": (d.get("publish_date") or "").strip(),
        "cover_url": (d.get("cover_url") or "").strip(),
        "info_url": (d.get("info_url") or "").strip(),
    }
    book, _ = get_or_create_book_from_payload(payload)
    shelf = add_owned_copy(request.user, book)
    shelf = Shelf.objects.select_related("book", "borrowed_from", "user", "copy").get(
        pk=shelf.pk
    )
    return Response(ShelfSerializer(shelf, context={"request": request}).data, status=201)


@api_view(["DELETE"])
def shelf_remove(request, shelf_id):
    shelf = Shelf.objects.filter(pk=shelf_id, user=request.user).select_related("copy").first()
    if not shelf:
        return _error("Запис не знайдено.", 404)
    if shelf.borrowed_from_id:
        return _error("Позичену книгу не можна видалити — лише повернути власнику.")
    if is_copy_lent_out(shelf.copy_id):
        return _error("Примірник зараз у позиці — спочатку дочекайтесь повернення.")
    remove_owned_shelf(shelf)
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
        owner, ensure_copies=True
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
        book, ensure_copies=True
    )
    owners = []
    seen = set()
    for h in holders:
        oid = h.borrowed_from_id or h.user_id
        u = h.borrowed_from if h.borrowed_from_id else h.user
        if oid not in seen:
            seen.add(oid)
            owners.append(u)
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
            req = create_exchange_request(request.user, target, offer)
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


def _exchange_action(request, request_id, fn):
    fn(request_id, request.user)
    return Response({"ok": True})


@api_view(["POST"])
def exchange_accept_view(request, request_id):
    return _exchange_action(request, request_id, accept_exchange_request)


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
        }
    )


@api_view(["POST"])
def handoff_confirm_give(request, handoff_id):
    confirm_handoff_give(handoff_id, request.user)
    return Response({"ok": True})


@api_view(["POST"])
def handoff_confirm_receive(request, handoff_id):
    confirm_handoff_receive(handoff_id, request.user)
    return Response({"ok": True})


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
