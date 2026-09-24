from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST, require_GET
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.core.paginator import Paginator
from .models import (
    Book,
    BookCopy,
    BookExchangeRequest,
    Comment,
    CopyEvent,
    Like,
    Post,
    PrivateMessage,
    READER_AGE_MAX,
    READER_AGE_MIN,
    Shelf,
)
from django.contrib.auth.views import LoginView
from .forms import (
    AddBookManualForm,
    AddIsbnForm,
    SendExchangePartnerMessageForm,
    UserLoginForm,
    UserRegisterForm,
    UserUpdateForm,
)
from django.views.generic import CreateView
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.conf import settings
# Бізнес-правила обміну/позик винесені в exchange_service - тут лише HTTP і шаблони.
from .message_service import (
    get_exchange_message_partners,
    mark_messages_read_for_user,
    mark_thread_read,
    send_user_message,
)
from .notification_service import list_notifications, notification_payload, unread_count
from .error_handling import web_exchange
from .exceptions import ExchangeError
from .exchange_service import (
    accept_exchange_request,
    add_owned_copy,
    attach_loan_info,
    attach_request_targets,
    available_owned_shelves_qs,
    browsable_owned_shelves_qs,
    cancel_exchange_request,
    cancel_loan_handoff,
    confirm_borrow_return,
    confirm_handoff_give,
    confirm_handoff_receive,
    create_many_exchange_requests,
    filter_physically_present,
    get_or_create_book_from_payload,
    group_shelves_by_book,
    handoffs_involving,
    is_copy_lent_out,
    physical_presence_shelves_qs,
    reject_exchange_request,
    remove_owned_shelf,
    request_borrow_return,
    resolve_and_sync_book_by_isbn,
)
from .web3forms_mail import (
    Web3FormsError,
    activation_payload,
    activation_url_for,
    pop_web3forms_bridge,
    send_activation_email,
    stash_web3forms_bridge,
)
from .registration_service import (
    activation_timeout,
    is_activation_expired,
    purge_expired_unactivated_users,
)

from .tokens import account_activation_token


def _activation_minutes() -> int:
    return int(activation_timeout().total_seconds() // 60)


def home(request):
    filter_type = request.GET.get("filter")

    from .feed_resume import feed_position, feed_queryset
    from .feed_search import (
        advanced_active,
        apply_book_search,
        search_active,
    )

    searching = search_active(request.GET)
    books_page = None
    if searching:
        books_qs = apply_book_search(Book.objects.all(), request.GET)
        book_paginator = Paginator(books_qs, 12)
        books_page = book_paginator.get_page(request.GET.get("bpage") or request.GET.get("page"))

    filter_my = filter_type == "my" and request.user.is_authenticated
    posts_list = feed_queryset(filter_my=filter_my, user=request.user)

    WEB_PAGE_SIZE = 5
    scroll_post_id = None

    # Resume: без явного ?page= відкриваємо сторінку останнього переглянутого поста
    if (
        request.user.is_authenticated
        and not searching
        and "page" not in request.GET
        and request.GET.get("no_resume") != "1"
        and request.user.last_watched_post_id
    ):
        pos = feed_position(
            request.user.last_watched_post_id,
            page_size=WEB_PAGE_SIZE,
            filter_my=filter_my,
            user=request.user,
        )
        if pos:
            scroll_post_id = pos["post_id"]
            if pos["page"] > 1:
                q = request.GET.copy()
                q["page"] = str(pos["page"])
                return redirect(f"/?{q.urlencode()}#post-{pos['post_id']}")

    post_params = request.GET.copy()
    if searching:
        post_params.pop("page", None)
    paginator = Paginator(posts_list, WEB_PAGE_SIZE)
    page_number = None if searching else request.GET.get("page")
    posts = paginator.get_page(page_number or 1)

    if (
        request.user.is_authenticated
        and not searching
        and scroll_post_id is None
        and request.user.last_watched_post_id
    ):
        # уже на потрібній сторінці (page=N або page 1)
        on_page_ids = {p.id for p in posts.object_list}
        if request.user.last_watched_post_id in on_page_ids:
            scroll_post_id = request.user.last_watched_post_id

    qs_params = request.GET.copy()
    qs_params.pop("page", None)
    qs_params.pop("bpage", None)
    search_qs = qs_params.urlencode()
    qs_core = request.GET.copy()
    qs_core.pop("page", None)
    qs_core.pop("bpage", None)
    qs_core.pop("filter", None)
    search_core = qs_core.urlencode()

    return render(
        request,
        "mainApp/index.html",
        {
            "posts": posts,
            "books": books_page,
            "searching": searching,
            "filter_type": filter_type,
            "search_qs": search_qs,
            "search_core": search_core,
            "search_active": searching,
            "advanced_open": advanced_active(request.GET) or request.GET.get("adv") == "1",
            "q": (request.GET.get("q") or "").strip(),
            "title": (request.GET.get("title") or "").strip(),
            "isbn": (request.GET.get("isbn") or "").strip(),
            "authors": (request.GET.get("authors") or "").strip(),
            "publisher": (request.GET.get("publisher") or "").strip(),
            "publish_date": (request.GET.get("publish_date") or "").strip(),
            "age_min": (request.GET.get("age_min") or "").strip(),
            "age_max": (request.GET.get("age_max") or "").strip(),
            "scroll_post_id": scroll_post_id,
            "track_watched": request.user.is_authenticated and not searching,
        },
    )


@login_required
@require_POST
def mark_post_watched(request, post_id):
    """AJAX/beacon: запам'ятати останній переглянутий пост у стрічці."""
    from .feed_resume import set_last_watched_post

    post = set_last_watched_post(request.user, post_id)
    if not post:
        return JsonResponse({"ok": False, "detail": "not found"}, status=404)
    return JsonResponse({"ok": True, "last_watched_post_id": post.id})


@login_required
def profile(request):
    return render(request, 'mainApp/profile.html')


class CustomLoginView(LoginView):
    template_name = 'mainApp/login.html'
    authentication_form = UserLoginForm

    def dispatch(self, request, *args, **kwargs):
        purge_expired_unactivated_users()
        return super().dispatch(request, *args, **kwargs)

class CustomRegisterView(CreateView):
    template_name = 'mainApp/register.html'
    form_class = UserRegisterForm
    success_url = reverse_lazy('confirm_email')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["activation_timeout_minutes"] = _activation_minutes()
        return ctx

    def form_valid(self, form):
        purge_expired_unactivated_users()
        user = form.save(commit=False)
        user.is_active = False
        user.email_confirmed = False
        user.save()

        url = activation_url_for(user, self.request)
        payload = activation_payload(user, url)
        # Для клієнтського fallback (free Web3Forms рекомендує browser-side).
        self.request.session["web3forms_activation"] = payload
        self.request.session["activation_url"] = url

        try:
            send_activation_email(user, self.request)
            self.request.session["web3forms_sent_server"] = True
        except Web3FormsError as e:
            # Не відкочуємо юзера: сторінка confirm_email дошле через JS + покаже лінк.
            self.request.session["web3forms_sent_server"] = False
            self.request.session["web3forms_server_error"] = str(e)

        return super().form_valid(form)


def activate(request, uidb64, token):
    purge_expired_unactivated_users()
    User = get_user_model()
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and is_activation_expired(user):
        user.delete()
        return render(
            request,
            "mainApp/activation_invalid.html",
            {
                "expired": True,
                "activation_timeout_minutes": _activation_minutes(),
            },
        )

    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.email_confirmed = True
        user.save()
        login(request, user)
        return render(request, 'mainApp/activation_success.html')
    return render(request, 'mainApp/activation_invalid.html')


def activation_success_view(request):
    return render(request, 'mainApp/activation_success.html')

def activation_invalid_view(request):
    return render(request, 'mainApp/activation_invalid.html')

def confirm_email_view(request):
    purge_expired_unactivated_users()
    payload = request.session.pop("web3forms_activation", None)
    sent_server = request.session.pop("web3forms_sent_server", False)
    server_error = request.session.pop("web3forms_server_error", "")
    activation_url = request.session.pop("activation_url", "") or ""
    return render(
        request,
        "mainApp/confirm_email.html",
        {
            "web3forms_payload": payload,
            "web3forms_access_key": settings.WEB3FORMS_ACCESS_KEY,
            "sent_server": sent_server,
            "server_error": server_error,
            "activation_url": activation_url,
            "activation_timeout_minutes": _activation_minutes(),
        },
    )


def web3forms_bridge_view(request, token):
    """
    HTML з браузерним Origin — єдиний спосіб free Web3Forms з мобілки
    (RN fetch блокується як server-side).
    """
    purge_expired_unactivated_users()
    data = pop_web3forms_bridge(token)
    if not data:
        return render(
            request,
            "mainApp/activation_invalid.html",
            {"expired": True, "activation_timeout_minutes": _activation_minutes()},
        )
    return render(
        request,
        "mainApp/web3forms_bridge.html",
        {
            "web3forms_payload": data.get("payload"),
            "activation_url": data.get("activation_url") or "",
            "activation_timeout_minutes": _activation_minutes(),
        },
    )

def _post_book_from_shelf(user, raw_id):
    """Книга для поста лише якщо в користувача є вона на полиці."""
    if raw_id is None or raw_id == "":
        return None
    try:
        bid = int(raw_id)
    except (TypeError, ValueError):
        return None
    if not Shelf.objects.filter(user=user, book_id=bid).exists():
        return None
    return Book.objects.filter(pk=bid).first()


def _posts_by_other_users_same_book_title_or_isbn(book):
    """
    Пости (з прив’язаною книгою) про той самий запис Book, той самий ISBN
    або ту саму назву (без урахування регістру).
    """
    if not book:
        return Post.objects.none()
    q = Q(book=book)
    isbn = (book.isbn or "").strip()
    if isbn:
        q |= Q(book__isbn=isbn)
    title = (book.title or "").strip()
    if title:
        q |= Q(book__title__iexact=title)
    return (
        Post.objects.filter(q)
        .filter(book__isnull=False)
        .select_related("author", "book")
        .order_by("-created_ad")
    )


def _confirm_separate_post_despite_similar(request):
    return (
        request.GET.get("force_new") == "1"
        or request.POST.get("confirm_new_post") == "1"
    )


@login_required
def create_post(request):
    book = None
    confirm_new = _confirm_separate_post_despite_similar(request)
    mode = (request.POST.get("mode") or request.GET.get("mode") or "").strip().lower()
    if mode not in ("event", "feedback"):
        # deep-link з полиці (?book_id=) → відгук; інакше — вибір на головній
        if request.GET.get("book_id") or request.POST.get("book_id"):
            mode = "feedback"
        else:
            mode = "event"

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        text = (request.POST.get("text") or "").strip()
        if mode == "event":
            post_book = None
        else:
            post_book = _post_book_from_shelf(request.user, request.POST.get("book_id"))
            book = post_book
            if not post_book:
                messages.error(
                    request,
                    "Оберіть книгу з вашої полиці для відгуку.",
                )
                owned = (
                    Book.objects.filter(shelf_entries__user=request.user)
                    .distinct()
                    .order_by("title")
                )
                return render(
                    request,
                    "mainApp/post_form.html",
                    {
                        "book": None,
                        "mode": "feedback",
                        "owned_books": owned,
                        "draft_title": title,
                        "draft_text": text,
                        "confirm_new_post": False,
                    },
                )

        if post_book and not confirm_new:
            related = _posts_by_other_users_same_book_title_or_isbn(post_book).exclude(
                author=request.user
            )
            if related.exists():
                ctx = {
                    "book": post_book,
                    "related_posts": related,
                    "mode": mode,
                }
                if title and text:
                    ctx["draft_title"] = title
                    ctx["draft_text"] = text
                return render(request, "mainApp/post_book_similar_warning.html", ctx)

        if not title or not text:
            messages.error(request, "Заповніть заголовок і текст поста.")
        else:
            Post.objects.create(
                author=request.user,
                title=title[:200],
                text=text,
                book=post_book,
            )
            messages.success(request, "Пост опубліковано.")
            return redirect("home")
    else:
        raw = request.GET.get("book_id")
        if raw and mode == "feedback":
            try:
                bid = int(raw)
            except (TypeError, ValueError):
                bid = None
            if bid is not None:
                b = Book.objects.filter(pk=bid).first()
                if b and Shelf.objects.filter(user=request.user, book_id=bid).exists():
                    book = b
                elif b:
                    messages.error(
                        request,
                        "Цієї книги немає на вашій полиці - додайте її, щоб писати відгук.",
                    )

        if book and not confirm_new:
            related = _posts_by_other_users_same_book_title_or_isbn(book).exclude(
                author=request.user
            )
            if related.exists():
                return render(
                    request,
                    "mainApp/post_book_similar_warning.html",
                    {
                        "book": book,
                        "related_posts": related,
                        "mode": mode,
                    },
                )

    owned_books = None
    if mode == "feedback" and not book:
        owned_books = (
            Book.objects.filter(shelf_entries__user=request.user)
            .distinct()
            .order_by("title")
        )

    return render(
        request,
        "mainApp/post_form.html",
        {
            "book": book,
            "mode": mode,
            "owned_books": owned_books,
            "confirm_new_post": confirm_new and bool(book),
        },
    )


@login_required
def delete_post(request, post_id):
    post = Post.objects.get(id=post_id)

    if post.author == request.user:
        post.delete()

    return redirect('home')

@login_required
def edit_post(request, post_id):
    post = get_object_or_404(
        Post.objects.select_related("book"),
        id=post_id,
    )

    if post.author != request.user:
        return redirect("home")

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        text = (request.POST.get("text") or "").strip()
        if title and text:
            post.title = title[:200]
            post.text = text
            post.save(update_fields=["title", "text"])
            return redirect("home")
        messages.error(request, "Заповніть заголовок і текст.")

    return render(request, "mainApp/post_form.html", {"post": post})

@login_required
def my_library(request):
    """
    Сторінка "Моя полиця": додавання книги за ISBN (Open Library), вручну або список Shelf.
    """
    form = AddIsbnForm()
    manual_form = AddBookManualForm()

    if request.method == "POST" and "add_isbn" in request.POST:
        form = AddIsbnForm(request.POST)
        if form.is_valid():
            try:
                book = resolve_and_sync_book_by_isbn(form.cleaned_data["isbn"])
            except ExchangeError as exc:
                messages.error(request, exc.message)
            else:
                add_owned_copy(request.user, book)
                messages.success(request, f"Додано: {book.title}")
                return redirect("my_library")

    elif request.method == "POST" and "add_manual" in request.POST:
        manual_form = AddBookManualForm(request.POST)
        if manual_form.is_valid():
            d = manual_form.cleaned_data
            payload = {
                "isbn": d["isbn"],
                "title": d["title"].strip(),
                "authors": (d.get("authors") or "").strip(),
                "publisher": (d.get("publisher") or "").strip(),
                "publish_date": (d.get("publish_date") or "").strip(),
                "cover_url": (d.get("cover_url") or "").strip(),
                "info_url": (d.get("info_url") or "").strip(),
            }
            book, _ = get_or_create_book_from_payload(payload)
            add_owned_copy(request.user, book)
            messages.success(request, f"Додано вручну: {book.title}")
            return redirect("my_library")

    # Полиця = фізичне місце: власні вільні + позичені вами.
    # Власні примірники, які зараз у когось у позиці, тут НЕ показуємо.
    shelves_all = list(
        request.user.shelf_entries.select_related("book", "borrowed_from", "copy").all()
    )
    pending_returns_to_confirm = list(
        Shelf.objects.filter(borrowed_from=request.user, return_pending=True)
        .select_related("user", "book", "copy")
        .order_by("-added_at")
    )
    loan_by_copy = {
        row.copy_id: row
        for row in Shelf.objects.filter(borrowed_from=request.user)
        .select_related("user", "book", "copy")
        if row.copy_id
    }
    lent_out_count = 0
    today = timezone.now().date()
    for s in shelves_all:
        s.is_lent_out = (not s.borrowed_from_id) and (s.copy_id in loan_by_copy)
        if s.is_lent_out:
            lent_out_count += 1
        s.pending_return_row = None if s.borrowed_from_id else (
            loan_by_copy[s.copy_id]
            if s.copy_id in loan_by_copy and loan_by_copy[s.copy_id].return_pending
            else None
        )
        s.loan_row = None if s.borrowed_from_id else loan_by_copy.get(s.copy_id)
        if s.borrowed_from_id and s.due_date:
            s.is_overdue = s.due_date < today
            s.days_left = (s.due_date - today).days
        else:
            s.is_overdue = False
            s.days_left = None
    shelves = [s for s in shelves_all if not s.is_lent_out]
    locked_raw = request.session.get("reader_age_locked_shelf_ids", [])
    if not isinstance(locked_raw, list):
        locked_raw = []
    reader_age_locked_shelf_ids = set(locked_raw)

    return render(
        request,
        "mainApp/library.html",
        {
            "form": form,
            "manual_form": manual_form,
            "manual_open": bool(manual_form.errors),
            "shelves": shelves,
            "lent_out_count": lent_out_count,
            "pending_returns_to_confirm": pending_returns_to_confirm,
            "reader_age_min": READER_AGE_MIN,
            "reader_age_max": READER_AGE_MAX,
            "reader_age_locked_shelf_ids": reader_age_locked_shelf_ids,
        },
    )


def _annotate_due_slip(shelf):
    """is_overdue / days_left — як у API ShelfSerializer (мобільний Реченець)."""
    today = timezone.now().date()
    if shelf.due_date and shelf.borrowed_from_id:
        shelf.days_left = (shelf.due_date - today).days
        shelf.is_overdue = shelf.days_left < 0
        shelf.days_overdue = abs(shelf.days_left) if shelf.is_overdue else 0
    else:
        shelf.is_overdue = False
        shelf.days_left = None
        shelf.days_overdue = 0
    return shelf


@login_required
def due_slips(request):
    """Date Due Slip (web): позичені мною + видані мною — аналог mobile /(tabs)/slips."""
    borrowed = [
        _annotate_due_slip(s)
        for s in request.user.shelf_entries.filter(borrowed_from__isnull=False)
        .select_related("book", "borrowed_from", "user")
        .order_by("due_date")
    ]
    lent = [
        _annotate_due_slip(s)
        for s in Shelf.objects.filter(borrowed_from=request.user)
        .select_related("book", "user", "borrowed_from")
        .order_by("due_date")
    ]
    return render(
        request,
        "mainApp/due_slips.html",
        {
            "borrowed": borrowed,
            "lent": lent,
            "loan_days": int(getattr(settings, "DEFAULT_LOAN_DAYS", 14)),
        },
    )


@login_required
def update_shelf_book_reader_age(request, shelf_id):
    """Оновлення min/max рекомендованого віку в спільному Book для рядка полиці."""
    if request.method != "POST":
        return redirect("my_library")
    shelf = get_object_or_404(
        Shelf.objects.select_related("book"),
        pk=shelf_id,
        user=request.user,
    )
    book = shelf.book
    try:
        mn = int(request.POST.get("min_readers_age", READER_AGE_MIN))
        mx = int(request.POST.get("max_readers_age", READER_AGE_MAX))
    except (TypeError, ValueError):
        messages.error(request, "Некоректні значення віку.")
        return redirect("my_library")
    mn = max(READER_AGE_MIN, min(READER_AGE_MAX, mn))
    mx = max(READER_AGE_MIN, min(READER_AGE_MAX, mx))
    # Якщо мін. > макс. у формі - міняємо значення місцями (у БД лишається коректна пара).
    if mn > mx:
        mn, mx = mx, mn
    book.min_readers_age = mn
    book.max_readers_age = mx
    try:
        book.full_clean()
    except DjangoValidationError as exc:
        messages.error(request, str(exc))
        return redirect("my_library")
    book.save(update_fields=["min_readers_age", "max_readers_age"])

    key = "reader_age_locked_shelf_ids"
    locked = request.session.get(key, [])
    if not isinstance(locked, list):
        locked = []
    if shelf_id not in locked:
        locked.append(shelf_id)
    request.session[key] = locked
    request.session.modified = True

    messages.success(request, "Діапазон рекомендованого віку збережено.")
    return redirect("my_library")


@login_required
@require_POST
def unlock_shelf_reader_age_edit(request, shelf_id):
    """Зняти режим "лише перегляд" повзунків після збереження (для цієї полиці)."""
    get_object_or_404(Shelf, pk=shelf_id, user=request.user)
    key = "reader_age_locked_shelf_ids"
    locked = request.session.get(key, [])
    if isinstance(locked, list) and shelf_id in locked:
        request.session[key] = [sid for sid in locked if sid != shelf_id]
        request.session.modified = True
    return redirect("my_library")


@login_required
def remove_shelf_entry(request, shelf_id):
    """Видалити з полиці лише власну книгу; позичену - заборонено (тільки return)."""
    if request.method != "POST":
        return redirect("my_library")
    shelf = get_object_or_404(Shelf, pk=shelf_id, user=request.user)
    if shelf.borrowed_from_id:
        messages.error(
            request,
            "Позичену книгу не можна видалити з полиці - лише повернути власнику.",
        )
        return redirect("my_library")
    if is_copy_lent_out(shelf.copy_id):
        messages.error(
            request,
            "Примірник зараз у позиці — спочатку дочекайтесь повернення.",
        )
        return redirect("my_library")
    remove_owned_shelf(shelf)
    messages.success(request, "Книгу видалено з полиці.")
    return redirect("my_library")


@login_required
def return_borrowed_shelf_book(request, shelf_id):
    if request.method != "POST":
        return redirect("my_library")
    web_exchange(
        request,
        request_borrow_return,
        shelf_id,
        request.user,
        success=(
            "Запит на повернення надіслано. Книга зникне з вашої полиці "
            "після підтвердження позикодавцем."
        ),
    )
    return redirect("my_library")


@login_required
def confirm_return_borrowed_shelf_book(request, shelf_id):
    """Позикодавець підтверджує отримання фізично повернутої книги."""
    if request.method != "POST":
        return redirect("my_library")
    web_exchange(
        request,
        confirm_borrow_return,
        shelf_id,
        request.user,
        success="Повернення підтверджено — позику знято з полиці позичальника.",
    )
    partner_id = request.POST.get("partner_id")
    if partner_id:
        try:
            return redirect("message_thread", partner_id=int(partner_id))
        except (TypeError, ValueError):
            pass
    return redirect("my_library")


@login_required
def browse_shelves(request):
    """
    Каталог: примірники там, де вони фізично зараз (вільні у власника або в позичальника).
    Запит на позичений примірник → передача з дозволу власника.
    """
    others_qs = attach_request_targets(
        attach_loan_info(
            list(
                physical_presence_shelves_qs(exclude_user_id=request.user.id)
                .select_related("user", "book", "copy", "borrowed_from")
                .order_by("-added_at")
            )
        )
    )
    others_grouped = group_shelves_by_book(others_qs)
    my_owned_shelves = available_owned_shelves_qs().filter(user=request.user).select_related(
        "book"
    )
    return render(
        request,
        "mainApp/browse_shelves.html",
        {
            "others_grouped": others_grouped,
            "my_owned_shelves": my_owned_shelves,
        },
    )


@login_required
def user_public_shelf(request, user_id):
    """Полиця користувача = лише те, що фізично у нього (власне вільне + позичене ним)."""
    User = get_user_model()
    shelf_owner = get_object_or_404(User, pk=user_id)
    if request.user.pk == shelf_owner.pk:
        return redirect("profile_app:profile")
    shelves = attach_request_targets(
        filter_physically_present(
            list(
                shelf_owner.shelf_entries.select_related("book", "borrowed_from", "copy").order_by(
                    "-added_at"
                )
            )
        )
    )
    return render(
        request,
        "mainApp/user_public_shelf.html",
        {
            "shelf_owner": shelf_owner,
            "shelves": shelves,
            "is_own": False,
        },
    )


@login_required
def book_history(request, book_id):
    """ISBN overview: список примірників (кожен зі своєю історією) + пости."""
    book = get_object_or_404(Book, pk=book_id)
    copies = list(
        BookCopy.objects.filter(book=book)
        .select_related("owner", "book")
        .order_by("-created_at")
    )
    shelf_entries = list(
        Shelf.objects.filter(book=book)
        .select_related("user", "borrowed_from", "copy")
        .order_by("added_at")
    )
    by_copy: dict[int, list] = {}
    for row in shelf_entries:
        by_copy.setdefault(row.copy_id, []).append(row)
    for c in copies:
        c.holder_rows = by_copy.get(c.pk, [])
    comments_qs = Comment.objects.select_related("author").order_by("created_at")
    posts = (
        Post.objects.filter(book=book)
        .select_related("author")
        .prefetch_related(Prefetch("comments", queryset=comments_qs))
        .order_by("-created_ad")
    )
    return render(
        request,
        "mainApp/book_history.html",
        {
            "book": book,
            "copies": copies,
            "shelf_entries": shelf_entries,
            "posts": posts,
        },
    )


@login_required
def copy_history(request, copy_id):
    """Історія подій одного фізичного примірника (BookCopy)."""
    copy = get_object_or_404(
        BookCopy.objects.select_related("book", "owner"),
        pk=copy_id,
    )
    book = copy.book
    shelf_entries = (
        Shelf.objects.filter(copy=copy)
        .select_related("user", "borrowed_from", "copy")
        .order_by("added_at")
    )
    shelf_events = list(
        CopyEvent.objects.filter(copy=copy)
        .select_related(
            "actor",
            "holder",
            "legal_owner",
            "previous_holder",
            "previous_owner",
            "counterparty",
            "exchange_request",
        )
        .order_by("-created_at")
    )
    return render(
        request,
        "mainApp/copy_history.html",
        {
            "book": book,
            "copy": copy,
            "shelf_entries": shelf_entries,
            "shelf_events": shelf_events,
        },
    )


@login_required
def create_exchange(request):
    """
    POST з browse_shelves: target_shelf_ids[] (чекбокси) + offer_shelf_id_<pk> для кожного рядка.
    Підтримує один або кілька запитів за одну відправку.
    """
    if request.method != "POST":
        return redirect("browse_shelves")

    err_cap = 12
    raw_ids = request.POST.getlist("target_shelf_ids")
    if not raw_ids:
        messages.error(request, "Оберіть хоча б одну книгу (рядок у таблиці).")
        return redirect("browse_shelves")

    seen: set[int] = set()
    lines: list[tuple[Shelf, Shelf | None]] = []
    preflight: list[str] = []
    for tid_str in raw_ids:
        try:
            tid = int(tid_str)
        except (TypeError, ValueError):
            preflight.append("Пропущено рядок з некоректним id полиці.")
            continue
        if tid in seen:
            continue
        seen.add(tid)
        target_shelf = (
            Shelf.objects.filter(pk=tid)
            .select_related("user", "book")
            .first()
        )
        if not target_shelf:
            preflight.append(f"Запис полиці #{tid} не знайдено.")
            continue

        offer_shelf = None
        raw_offer = request.POST.get(f"offer_shelf_id_{tid}", "") or ""
        # Позичений примірник / передача — лише borrow/transmit, без обміну
        if is_copy_lent_out(target_shelf.copy_id) or target_shelf.borrowed_from_id:
            raw_offer = ""
        if raw_offer.strip():
            try:
                oid = int(raw_offer)
            except (TypeError, ValueError):
                t = target_shelf.book.title
                preflight.append(f'"{t[:45]}": некоректна книга для обміну.')
                continue
            offer_shelf = (
                available_owned_shelves_qs()
                .filter(pk=oid, user=request.user)
                .first()
            )
            if not offer_shelf:
                t = target_shelf.book.title
                preflight.append(
                    f'"{t[:45]}": запропоновану книгу не знайдено серед ваших вільних.'
                )
                continue

        lines.append((target_shelf, offer_shelf))

    if not lines:
        for e in preflight[:err_cap]:
            messages.error(request, e)
        if len(preflight) > err_cap:
            messages.warning(
                request,
                f"…та ще {len(preflight) - err_cap} зауважень.",
            )
        if not preflight:
            messages.error(request, "Немає валідних рядків для відправки.")
        return redirect("browse_shelves")

    ok_count, errs = create_many_exchange_requests(request.user, lines)
    if ok_count:
        messages.success(
            request,
            f"Надіслано запитів: {ok_count}."
            if ok_count > 1
            else "Запит надіслано.",
        )
    for e in preflight[:err_cap]:
        messages.error(request, e)
    if len(preflight) > err_cap:
        messages.warning(
            request,
            f"…та ще {len(preflight) - err_cap} попередніх зауважень.",
        )
    for e in errs[:err_cap]:
        messages.error(request, e)
    if len(errs) > err_cap:
        messages.warning(
            request,
            f"…та ще {len(errs) - err_cap} повідомлень про помилки (перевірте кожен рядок).",
        )
    return redirect("exchange_requests")


@login_required
def exchange_requests(request):
    """Вхідні / вихідні запити та остання історія рішень для поточного користувача."""
    pending_in = (
        BookExchangeRequest.objects.filter(
            status=BookExchangeRequest.Status.PENDING,
            shelf_owner=request.user,
        )
        .select_related(
            "requester",
            "target_shelf__book",
            "target_shelf__copy",
            "offer_shelf__book",
            "offer_shelf__copy",
        )
    )
    pending_out = (
        BookExchangeRequest.objects.filter(
            status=BookExchangeRequest.Status.PENDING,
            requester=request.user,
        )
        .select_related(
            "target_shelf__user",
            "target_shelf__book",
            "target_shelf__copy",
            "offer_shelf__book",
            "offer_shelf__copy",
        )
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
            "requester",
            "target_shelf__user",
            "target_shelf__book",
            "target_shelf__copy",
            "offer_shelf__book",
            "offer_shelf__copy",
        )[:50]
    )
    return render(
        request,
        "mainApp/exchange_requests.html",
        {
            "pending_in": pending_in,
            "pending_out": pending_out,
            "history": history,
        },
    )


@login_required
def exchange_accept(request, request_id):
    """Перед accept дивимось, був offer чи ні - щоб показати різне повідомлення (обмін vs позика)."""
    if request.method != "POST":
        return redirect("exchange_requests")
    req = (
        BookExchangeRequest.objects.filter(
            pk=request_id, status=BookExchangeRequest.Status.PENDING
        )
        .select_related("target_shelf")
        .first()
    )
    had_offer = bool(req and req.offer_shelf_id)
    was_transmit = bool(
        req and not had_offer and is_copy_lent_out(getattr(req.target_shelf, "copy_id", None))
    )
    try:
        accept_exchange_request(request_id, request.user)
    except ExchangeError as exc:
        messages.error(request, exc.message)
    else:
        if had_offer:
            msg = "Обмін прийнято: полиці оновлено."
        elif was_transmit:
            msg = (
                "Передачу схвалено. Книга лишається у поточного позичальника, "
                "доки він і наступний читач не підтвердять фізичну передачу в чаті."
            )
        else:
            msg = "Запит прийнято: книгу видано в позику (повернення - з полиці позичальника)."
        messages.success(request, msg)
    return redirect("exchange_requests")


@login_required
def exchange_reject(request, request_id):
    """Власник відмовляє у запиті - статус запиту rejected, полиці не змінюються."""
    if request.method != "POST":
        return redirect("exchange_requests")
    web_exchange(
        request,
        reject_exchange_request,
        request_id,
        request.user,
        success="Запит відхилено.",
    )
    return redirect("exchange_requests")


@login_required
def exchange_cancel(request, request_id):
    """Відправник запиту передумав - статус cancelled."""
    if request.method != "POST":
        return redirect("exchange_requests")
    web_exchange(
        request,
        cancel_exchange_request,
        request_id,
        request.user,
        success="Запит скасовано.",
    )
    return redirect("exchange_requests")


@login_required
@require_GET
def notifications_unread_count_view(request):
    """JSON для живого бейджа в навбарі (polling без перезавантаження сторінки)."""
    return JsonResponse({"unread_count": unread_count(request.user)})


@login_required
def notifications_inbox(request):
    """
    Скринька сповіщень (запити на книги тощо) з переходом у чат.
    """
    if request.method == "POST" and "mark_all_read" in request.POST:
        mark_messages_read_for_user(request.user)
        messages.success(request, "Усі сповіщення позначено прочитаними.")
        return redirect("notifications_inbox")

    items = [
        {
            **notification_payload(m),
            "created_at": m.created_at,
            "msg": m,
        }
        for m in list_notifications(request.user, limit=80)
    ]
    return render(
        request,
        "mainApp/notifications.html",
        {
            "items": items,
            "unread_count": unread_count(request.user),
        },
    )


@login_required
@require_POST
def notification_confirm_return(request, message_id: int):
    """Зі сповіщення про повернення — підтвердити позику і позначити лист прочитаним."""
    msg = get_object_or_404(PrivateMessage, pk=message_id, recipient=request.user)
    payload = notification_payload(msg)
    shelf_id = payload.get("confirm_return_shelf_id")
    if payload.get("kind") != "return" or not shelf_id:
        messages.error(request, "Це сповіщення не є активним запитом на повернення.")
        return redirect("notifications_inbox")
    ok, _ = web_exchange(
        request,
        confirm_borrow_return,
        shelf_id,
        request.user,
        success="Повернення підтверджено.",
    )
    if ok and msg.read_at is None:
        mark_messages_read_for_user(request.user, [msg.pk])
    return redirect("notifications_inbox")


@login_required
@require_POST
def notification_open_chat(request, message_id: int):
    """Позначити одне сповіщення прочитаним і відкрити чат з відправником."""
    msg = get_object_or_404(PrivateMessage, pk=message_id, recipient=request.user)
    if msg.read_at is None:
        mark_messages_read_for_user(request.user, [msg.pk])
    return redirect("message_thread", partner_id=msg.sender_id)


@login_required
def message_thread(request, partner_id: int):
    """
    Окремий чат лише з одним користувачем (спільний запит на позику/обмін).
    Загальної скриньки немає - посилання тільки з обмінів / позики.
    """
    partners = get_exchange_message_partners(request.user)
    if not partners.exists():
        messages.info(
            request,
            "Чат доступний лише після запиту на позику або обмін книги з іншим користувачем.",
        )
        return redirect("exchange_requests")
    partner_ids = frozenset(partners.values_list("pk", flat=True))
    if partner_id not in partner_ids:
        messages.error(request, "Немає спільного запиту з цим користувачем.")
        return redirect("exchange_requests")

    partner = get_user_model().objects.get(pk=partner_id)

    if request.method == "POST" and "send_message" in request.POST:
        form = SendExchangePartnerMessageForm(request.POST)
        if form.is_valid():
            msg = send_user_message(request.user, partner, form.cleaned_data["body"])
            if msg:
                messages.success(request, "Повідомлення надіслано.")
            else:
                messages.warning(request, "Порожній текст - нічого не надіслано.")
            return redirect("message_thread", partner_id=partner_id)
    else:
        form = SendExchangePartnerMessageForm()

    recent = (
        PrivateMessage.objects.filter(
            Q(recipient=request.user, sender_id=partner_id)
            | Q(sender=request.user, recipient_id=partner_id)
        )
        .select_related("sender", "recipient", "exchange_request")
        .order_by("-created_at")[:250]
    )
    timeline = list(reversed(list(recent)))
    mark_thread_read(request.user, partner_id)
    handoffs = handoffs_involving(request.user.id, partner_id)
    pending_returns = list(
        Shelf.objects.filter(
            borrowed_from=request.user,
            user_id=partner_id,
            return_pending=True,
        )
        .select_related("user", "book", "copy")
        .order_by("-added_at")
    )

    return render(
        request,
        "mainApp/messages.html",
        {
            "form": form,
            "timeline": timeline,
            "partners": partners,
            "partner": partner,
            "handoffs": handoffs,
            "pending_returns": pending_returns,
        },
    )


@login_required
@require_POST
def handoff_confirm_give_view(request, handoff_id):
    web_exchange(
        request,
        confirm_handoff_give,
        handoff_id,
        request.user,
        success="Віддачу підтверджено — очікуємо підтвердження отримання.",
    )
    partner_id = request.POST.get("partner_id")
    if partner_id:
        return redirect("message_thread", partner_id=int(partner_id))
    return redirect("exchange_requests")


@login_required
@require_POST
def handoff_confirm_receive_view(request, handoff_id):
    web_exchange(
        request,
        confirm_handoff_receive,
        handoff_id,
        request.user,
        success=(
            "Отримання підтверджено — книга на вашій полиці; "
            "попередній позичальник вийшов з чату."
        ),
    )
    partner_id = request.POST.get("partner_id")
    if partner_id:
        try:
            return redirect("message_thread", partner_id=int(partner_id))
        except Exception:
            pass
    return redirect("exchange_requests")


@login_required
@require_POST
def handoff_cancel_view(request, handoff_id):
    web_exchange(
        request,
        cancel_loan_handoff,
        handoff_id,
        request.user,
        success="Фізичну передачу скасовано.",
    )
    partner_id = request.POST.get("partner_id")
    if partner_id:
        return redirect("message_thread", partner_id=int(partner_id))
    return redirect("exchange_requests")


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    if request.method == 'POST':
        text = request.POST.get('text')

        if text:
            Comment.objects.create(
                post=post,
                author=request.user,
                text=text
            )

    return redirect('home')

@login_required
def toggle_like(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    like = Like.objects.filter(post=post, user=request.user).first()

    if like:
        like.delete()
    else:
        Like.objects.create(post=post, user=request.user)

    return redirect('home')