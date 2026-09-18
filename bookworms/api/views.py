from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
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
    available_owned_shelves_qs,
    cancel_exchange_request,
    confirm_borrow_return,
    create_exchange_request,
    get_or_create_book_from_payload,
    is_book_lent_out,
    reject_exchange_request,
    request_borrow_return,
)
from mainApp.message_service import (
    get_exchange_message_partners,
    mark_messages_read_for_user,
    mark_thread_read,
    send_user_message,
)
from mainApp.notification_service import (
    list_notifications,
    notification_payload,
    unread_count,
)
from mainApp.models import (
    Book,
    BookExchangeRequest,
    Comment,
    Like,
    Post,
    PrivateMessage,
    Shelf,
)
from mainApp.openlibrary import fetch_book_by_isbn, normalize_isbn
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
    BookSerializer,
    CommentSerializer,
    CreateExchangeSerializer,
    ExchangeRequestSerializer,
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
    from mainApp.registration_service import purge_expired_unactivated_users, purge_status
    from mainApp.web3forms_mail import Web3FormsError, send_web3forms

    purged = purge_expired_unactivated_users()
    st = purge_status()
    from mainApp.openlibrary import openlibrary_ping

    payload = {
        "status": "ok",
        "app": "date-due-slip",
        "code_rev": "2026-09-18-confirm-marks-notif-read",
        "purged_now": purged,
        **st,
        "web3forms_key_set": bool(getattr(settings, "WEB3FORMS_ACCESS_KEY", "")),
        "web3forms_key_suffix": (getattr(settings, "WEB3FORMS_ACCESS_KEY", "") or "")[-6:],
        "public_base_url": getattr(settings, "PUBLIC_BASE_URL", "") or None,
        **openlibrary_ping(),
    }
    if request.GET.get("test_mail") == "1":
        try:
            send_web3forms(
                {
                    "access_key": settings.WEB3FORMS_ACCESS_KEY,
                    "subject": "Date Due Slip — health test",
                    "from_name": "Date Due Slip",
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
    qs = Post.objects.select_related("author", "book").order_by("-created_ad")
    if request.GET.get("filter") == "my" and request.user.is_authenticated:
        qs = qs.filter(author=request.user)
    comments_qs = Comment.objects.select_related("author").order_by("created_at")
    qs = qs.prefetch_related(Prefetch("comments", queryset=comments_qs))
    qs = _annotate_posts(qs, request.user)
    paginator = PostPagination()
    page = paginator.paginate_queryset(qs, request)
    ser = PostSerializer(page, many=True, context={"request": request})
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
    shelves = list(
        request.user.shelf_entries.select_related("book", "borrowed_from", "user")
    )
    pending = list(
        Shelf.objects.filter(borrowed_from=request.user, return_pending=True)
        .select_related("user", "book", "borrowed_from")
        .order_by("-added_at")
    )
    lent_book_ids = set(
        Shelf.objects.filter(borrowed_from=request.user).values_list("book_id", flat=True)
    )
    pending_by_book = {p.book_id: p.id for p in pending}
    for s in shelves:
        s.is_lent_out = (not s.borrowed_from_id) and (s.book_id in lent_book_ids)
        s.pending_return_shelf_id = (
            None if s.borrowed_from_id else pending_by_book.get(s.book_id)
        )
    return Response(
        {
            "shelves": ShelfSerializer(shelves, many=True, context={"request": request}).data,
            "pending_returns": ShelfSerializer(
                pending, many=True, context={"request": request}
            ).data,
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
    payload, err = fetch_book_by_isbn(ser.validated_data["isbn"])
    if err:
        return _error(err)
    book, _ = get_or_create_book_from_payload(payload)
    try:
        shelf = Shelf.objects.create(user=request.user, book=book)
    except IntegrityError:
        return _error("Ця книга вже є на вашій полиці.", 409)
    shelf = Shelf.objects.select_related("book", "borrowed_from", "user").get(pk=shelf.pk)
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
    try:
        shelf = Shelf.objects.create(user=request.user, book=book)
    except IntegrityError:
        return _error("Ця книга вже є на вашій полиці.", 409)
    shelf = Shelf.objects.select_related("book", "borrowed_from", "user").get(pk=shelf.pk)
    return Response(ShelfSerializer(shelf, context={"request": request}).data, status=201)


@api_view(["DELETE"])
def shelf_remove(request, shelf_id):
    shelf = Shelf.objects.filter(pk=shelf_id, user=request.user).first()
    if not shelf:
        return _error("Запис не знайдено.", 404)
    if shelf.borrowed_from_id:
        return _error("Позичену книгу не можна видалити — лише повернути власнику.")
    if is_book_lent_out(shelf.user_id, shelf.book_id):
        return _error("Книга зараз у позиці — спочатку дочекайтесь повернення.")
    shelf.delete()
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
    ok, err = request_borrow_return(shelf_id, request.user)
    if not ok:
        return _error(err or "Помилка.")
    return Response({"ok": True})


@api_view(["POST"])
def shelf_confirm_return(request, shelf_id):
    ok, err = confirm_borrow_return(shelf_id, request.user)
    if not ok:
        return _error(err or "Помилка.")
    return Response({"ok": True})


@api_view(["GET"])
def browse_shelves(request):
    others = (
        available_owned_shelves_qs(exclude_user_id=request.user.id)
        .select_related("user", "book", "borrowed_from")
        .order_by("-added_at")
    )
    mine = (
        available_owned_shelves_qs()
        .filter(user=request.user)
        .select_related("book", "user", "borrowed_from")
    )
    return Response(
        {
            "others": ShelfSerializer(others, many=True, context={"request": request}).data,
            "my_owned": ShelfSerializer(mine, many=True, context={"request": request}).data,
        }
    )


@api_view(["GET"])
def user_shelf(request, user_id):
    owner = User.objects.filter(pk=user_id).first()
    if not owner:
        return _error("Користувача не знайдено.", 404)
    shelves = owner.shelf_entries.select_related("book", "borrowed_from", "user").order_by(
        "-added_at"
    )
    return Response(
        {
            "user": UserPublicSerializer(owner, context={"request": request}).data,
            "is_own": request.user.pk == owner.pk,
            "shelves": ShelfSerializer(shelves, many=True, context={"request": request}).data,
        }
    )


@api_view(["GET"])
def book_detail(request, book_id):
    book = Book.objects.filter(pk=book_id).first()
    if not book:
        return _error("Книгу не знайдено.", 404)
    holders = Shelf.objects.filter(book=book).select_related("user", "borrowed_from", "book")
    comments_qs = Comment.objects.select_related("author").order_by("created_at")
    posts = (
        _annotate_posts(Post.objects.filter(book=book), request.user)
        .select_related("author", "book")
        .prefetch_related(Prefetch("comments", queryset=comments_qs))
        .order_by("-created_ad")
    )
    return Response(
        {
            "book": BookSerializer(book).data,
            "holders": ShelfSerializer(holders, many=True, context={"request": request}).data,
            "posts": PostSerializer(posts, many=True, context={"request": request}).data,
        }
    )


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
        if oid:
            offer = Shelf.objects.filter(pk=oid, user=request.user).first()
            if not offer:
                errors.append(f'"{target.book.title[:45]}": книгу для обміну не знайдено.')
                continue
        req, err = create_exchange_request(request.user, target, offer)
        if err:
            errors.append(f'"{target.book.title[:45]}": {err}')
        else:
            created.append(req)
    ctx = {"request": request}
    return Response(
        {
            "created": ExchangeRequestSerializer(created, many=True, context=ctx).data,
            "errors": errors,
        },
        status=201 if created else 400,
    )


def _exchange_action(request, request_id, fn):
    ok, err = fn(request_id, request.user)
    if not ok:
        return _error(err or "Помилка.")
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
    partners = get_exchange_message_partners(request.user)
    return Response(UserPublicSerializer(partners, many=True, context={"request": request}).data)


@api_view(["GET", "POST"])
def message_thread(request, partner_id):
    partners = get_exchange_message_partners(request.user)
    if partner_id not in set(partners.values_list("pk", flat=True)):
        return _error("Немає спільного запиту з цим користувачем.", 403)
    partner = User.objects.filter(pk=partner_id).first()
    if not partner:
        return _error("Користувача не знайдено.", 404)
    if request.method == "POST":
        ser = SendMessageSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        msg = send_user_message(request.user, partner, ser.validated_data["body"])
        if not msg:
            return _error("Порожній текст.")
        return Response(MessageSerializer(msg, context={"request": request}).data, status=201)
    recent = (
        PrivateMessage.objects.filter(
            Q(recipient=request.user, sender_id=partner_id)
            | Q(sender=request.user, recipient_id=partner_id)
        )
        .select_related("sender", "recipient")
        .order_by("-created_at")[:250]
    )
    timeline = list(reversed(list(recent)))
    mark_thread_read(request.user, partner_id)
    return Response(
        {
            "partner": UserPublicSerializer(partner, context={"request": request}).data,
            "messages": MessageSerializer(timeline, many=True, context={"request": request}).data,
        }
    )


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
