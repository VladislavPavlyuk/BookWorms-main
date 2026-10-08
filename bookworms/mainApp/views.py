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
    ContactDevelopersForm,
    CONTACT_MAX_FILE_BYTES,
    CONTACT_MAX_SCREENSHOTS,
    CONTACT_MESSAGE_MAX,
    EditBookManualForm,
    SendExchangePartnerMessageForm,
    UserLoginForm,
    UserRegisterForm,
    UserUpdateForm,
)
from django.views.generic import CreateView
from django.urls import reverse, reverse_lazy
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.conf import settings
# Бізнес-правила обміну/позик винесені в exchange_service - тут лише HTTP і шаблони.
from .message_service import (
    mark_messages_read_for_user,
)
from .notification_service import list_notifications, notification_payload, unread_count
from .error_handling import web_exchange
from .exceptions import ExchangeError
from .exchange_service import (
    accept_exchange_request,
    add_owned_copy,
    cancel_exchange_request,
    cancel_loan_handoff,
    confirm_borrow_return,
    confirm_exchange_due_date,
    confirm_handoff_give,
    confirm_handoff_receive,
    create_many_exchange_requests,
    get_or_create_book_from_payload,
    is_copy_lent_out,
    offerable_shelves_from_requester,
    pick_offer_by_owner,
    propose_exchange_due_date,
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
            "year_from": (request.GET.get("year_from") or "").strip(),
            "year_to": (request.GET.get("year_to") or "").strip(),
            "language": (request.GET.get("language") or "").strip(),
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
        from django.http import HttpResponseRedirect

        purge_expired_unactivated_users()
        user = form.save(commit=False)
        user.is_active = False
        user.email_confirmed = False
        user.save()
        self.object = user

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

        return HttpResponseRedirect(self.get_success_url())


@require_GET
def register_check_availability(request):
    """JSON for register page live checks (AllowAny)."""
    from .registration_availability import check_registration_availability

    purge_expired_unactivated_users()
    payload = check_registration_availability(
        username=(request.GET.get("username") or "").strip(),
        email=(request.GET.get("email") or "").strip(),
    )
    return JsonResponse(payload)

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


def contact_developers_view(request):
    """Форма зв’язку з розробниками → Web3Forms (browser FormData + attachments)."""
    user = request.user if request.user.is_authenticated else None
    form = ContactDevelopersForm(user=user)
    return render(
        request,
        "mainApp/contact.html",
        {
            "form": form,
            "web3forms_access_key": (settings.WEB3FORMS_ACCESS_KEY or "").strip(),
            "max_screenshots": CONTACT_MAX_SCREENSHOTS,
            "max_file_bytes": CONTACT_MAX_FILE_BYTES,
            "max_file_mb": CONTACT_MAX_FILE_BYTES // (1024 * 1024),
            "message_max": CONTACT_MESSAGE_MAX,
            "contact_username": user.username if user else "",
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


def _annotate_library_shelf(request, shelf: Shelf) -> Shelf:
    """Attrs expected by `_library_shelf_item.html` for one shelf row."""
    import json

    from django.utils.safestring import mark_safe

    from .book_photos import is_local_isbn, user_can_edit_manual_book
    from .book_price import serialize_evaluation

    shelf.is_lent_out = False
    shelf.pending_return_row = None
    shelf.loan_row = None
    shelf.is_overdue = False
    shelf.days_left = None
    if shelf.borrowed_from_id and shelf.due_date:
        today = timezone.now().date()
        shelf.is_overdue = shelf.due_date < today
        shelf.days_left = (shelf.due_date - today).days

    shelf.can_edit_manual = (not shelf.borrowed_from_id) and user_can_edit_manual_book(
        request.user, shelf.book
    )
    if shelf.can_edit_manual:
        b = shelf.book
        payload = {
            "edit_url": reverse("update_manual_shelf_book", args=[shelf.id]),
            "isbn": "" if is_local_isbn(b.isbn) else (b.isbn or ""),
            "title": b.title or "",
            "authors": b.authors or "",
            "publisher": b.publisher or "",
            "publish_date": b.publish_date or "",
            "cover_text": b.cover_text or "",
            "photos": [{"id": p.id, "url": p.image.url} for p in b.photos.all()],
        }
        raw = json.dumps(payload, ensure_ascii=False)
        shelf.edit_payload_json = mark_safe(
            raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        )
    else:
        shelf.edit_payload_json = ""

    ev = getattr(shelf.book, "price_evaluation", None)
    pe = serialize_evaluation(ev)
    shelf.price_eval = pe
    if pe and pe.get("quotes") is not None:
        raw_q = json.dumps(pe["quotes"], ensure_ascii=False)
        shelf.price_quotes_json = mark_safe(
            raw_q.replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026")
        )
    else:
        shelf.price_quotes_json = mark_safe("[]")
    return shelf


def _render_library_shelf_item_html(request, shelf: Shelf) -> str:
    """Fresh shelf HTML from DB for soft-insert into My Library grid."""
    from django.template.loader import render_to_string

    shelf = (
        Shelf.objects.filter(pk=shelf.pk)
        .select_related("book", "copy", "borrowed_from", "user")
        .prefetch_related("book__photos", "book__price_evaluation__quotes")
        .first()
        or shelf
    )
    _annotate_library_shelf(request, shelf)
    return render_to_string(
        "mainApp/_library_shelf_item.html",
        {
            "shelf": shelf,
            "reader_age_min": READER_AGE_MIN,
            "reader_age_max": READER_AGE_MAX,
        },
        request=request,
    )


@login_required
def my_library(request):
    """
    Сторінка "Моя полиця": додавання книги за ISBN (Open Library), вручну або список Shelf.
    """
    form = AddIsbnForm()
    manual_form = AddBookManualForm()

    if request.method == "POST" and "add_isbn" in request.POST:
        form = AddIsbnForm(request.POST)
        wants_json = (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or "application/json" in (request.headers.get("Accept") or "")
        )
        if form.is_valid():
            search_log: list = []
            try:
                book = resolve_and_sync_book_by_isbn(
                    form.cleaned_data["isbn"], search_log=search_log
                )
            except ExchangeError as exc:
                if wants_json:
                    return JsonResponse(
                        {
                            "ok": False,
                            "detail": exc.message,
                            "search_log": search_log,
                        },
                        status=getattr(exc, "http_status", 404) or 404,
                    )
                messages.error(request, exc.message)
            else:
                from .library_service import (
                    IsbnConfirmNeeded,
                    LibraryAction,
                    LibraryError,
                    add_copy_for_user,
                )

                confirm = request.POST.get("confirm_extra") == "1"
                try:
                    result = add_copy_for_user(
                        request.user, book, confirm_extra=confirm
                    )
                except LibraryError as exc:
                    if wants_json:
                        return JsonResponse(
                            {
                                "ok": False,
                                "detail": exc.message,
                                "search_log": search_log,
                            },
                            status=400,
                        )
                    messages.error(request, exc.message)
                else:
                    if isinstance(result, IsbnConfirmNeeded):
                        detail = (
                            f"У бібліотеці вже є {result.existing_count} примірник(и) "
                            f"«{result.title}» (ISBN {result.isbn}). "
                            f"Підтвердіть додавання ще одного нижче."
                        )
                        request.session["library_confirm_extra"] = {
                            "isbn": result.isbn,
                            "count": result.existing_count,
                            "title": result.title,
                        }
                        if wants_json:
                            return JsonResponse(
                                {
                                    "ok": False,
                                    "needs_confirmation": True,
                                    "isbn": result.isbn,
                                    "existing_count": result.existing_count,
                                    "title": result.title,
                                    "detail": detail,
                                    "search_log": search_log,
                                    "redirect": reverse("my_library"),
                                },
                                status=409,
                            )
                        messages.warning(request, detail)
                        return redirect("my_library")
                    if isinstance(result, LibraryAction):
                        if wants_json:
                            return JsonResponse(
                                {
                                    "ok": True,
                                    "pending_approval": True,
                                    "chat_partner_id": result.library.admin_id,
                                    "detail": (
                                        "У бібліотеці вже є цей ISBN. "
                                        "Запит надіслано адміністратору в чат."
                                    ),
                                    "search_log": search_log,
                                    "redirect": reverse(
                                        "message_thread",
                                        kwargs={"partner_id": result.library.admin_id},
                                    ),
                                },
                                status=202,
                            )
                        messages.info(
                            request,
                            "У бібліотеці вже є цей ISBN. Запит надіслано адміністратору в чат.",
                        )
                        return redirect(
                            "message_thread", partner_id=result.library.admin_id
                        )
                    else:
                        hit = next(
                            (
                                s
                                for s in reversed(search_log)
                                if s.get("status") == "hit"
                            ),
                            None,
                        )
                        src = (hit or {}).get("label") or ""
                        msg = f"Додано: {book.title}"
                        if src:
                            msg = f"{msg} (знайдено в {src})"
                        if wants_json:
                            return JsonResponse(
                                {
                                    "ok": True,
                                    "title": book.title,
                                    "detail": msg,
                                    "search_log": search_log,
                                    "search_source": src or None,
                                    "shelf_id": result.id,
                                    "shelf_html": _render_library_shelf_item_html(
                                        request, result
                                    ),
                                    "redirect": reverse("my_library"),
                                },
                                status=201,
                            )
                        messages.success(request, msg)
                    return redirect("my_library")
        elif wants_json:
            err = "; ".join(
                e for errs in form.errors.values() for e in errs
            ) or "Невірний ISBN"
            return JsonResponse({"ok": False, "detail": err}, status=400)

    elif request.method == "POST" and "add_manual" in request.POST:
        manual_form = AddBookManualForm(request.POST, request.FILES)
        photos = request.FILES.getlist("photos")
        is_xhr = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        if manual_form.is_valid():
            d = manual_form.cleaned_data
            raw_isbn = (d.get("isbn") or "").strip()
            title = (d.get("title") or "").strip()
            if raw_isbn:
                from .book_lookup import normalize_isbn

                if not normalize_isbn(raw_isbn):
                    manual_form.add_error(
                        "isbn",
                        "Невірний ISBN (10 або 13). Залиште порожнім — збережемо з фото.",
                    )
                elif not title and not photos:
                    manual_form.add_error(
                        "title",
                        "Вкажіть назву або зробіть хоча б одне фото обкладинки.",
                    )
            elif not title and not photos:
                manual_form.add_error(
                    "title",
                    "Вкажіть назву або зробіть хоча б одне фото обкладинки.",
                )
            if not manual_form.errors:
                from .book_photos import create_manual_book, save_book_photos

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
                saved = save_book_photos(book, photos, request=request)
                from .library_service import (
                    IsbnConfirmNeeded,
                    LibraryAction,
                    LibraryError,
                    add_copy_for_user,
                )

                confirm = request.POST.get("confirm_extra") == "1"
                try:
                    result = add_copy_for_user(
                        request.user, book, confirm_extra=confirm
                    )
                except LibraryError as exc:
                    messages.error(request, exc.message)
                    if is_xhr:
                        return JsonResponse({"ok": False, "detail": exc.message}, status=400)
                else:
                    from django.urls import reverse

                    if isinstance(result, IsbnConfirmNeeded):
                        detail = (
                            f"У бібліотеці вже є {result.existing_count} примірник(и) "
                            f"з ISBN {result.isbn}. Додати ще один?"
                        )
                        if is_xhr:
                            return JsonResponse(
                                {
                                    "ok": False,
                                    "needs_confirmation": True,
                                    "isbn": result.isbn,
                                    "existing_count": result.existing_count,
                                    "title": result.title,
                                    "detail": detail,
                                },
                                status=409,
                            )
                        messages.warning(request, detail)
                        request.session["library_confirm_extra"] = {
                            "isbn": result.isbn,
                            "count": result.existing_count,
                            "title": result.title,
                        }
                        return redirect("my_library")
                    if isinstance(result, LibraryAction):
                        msg = (
                            "У бібліотеці вже є цей ISBN. "
                            "Запит надіслано адміністратору в чат."
                        )
                        if is_xhr:
                            return JsonResponse(
                                {
                                    "ok": True,
                                    "pending_approval": True,
                                    "detail": msg,
                                    "chat_partner_id": result.library.admin_id,
                                    "redirect": reverse(
                                        "message_thread",
                                        args=[result.library.admin_id],
                                    ),
                                }
                            )
                        messages.info(request, msg)
                        return redirect(
                            "message_thread", partner_id=result.library.admin_id
                        )
                    messages.success(request, f"Додано вручну: {book.title}")
                    if is_xhr:
                        return JsonResponse(
                            {
                                "ok": True,
                                "redirect": reverse("my_library"),
                                "title": book.title,
                                "photos_saved": len(saved),
                                "shelf_id": result.id,
                                "shelf_html": _render_library_shelf_item_html(
                                    request, result
                                ),
                            }
                        )
                    return redirect("my_library")
        if is_xhr:
            errs = []
            for field, flist in manual_form.errors.items():
                for e in flist:
                    errs.append(f"{field}: {e}" if field != "__all__" else str(e))
            return JsonResponse(
                {
                    "ok": False,
                    "detail": "; ".join(errs) or "Форма невалідна.",
                    "errors": manual_form.errors.get_json_data(),
                    "photos_received": len(photos),
                },
                status=400,
            )

    # Полиця = спільна бібліотека учасників + позичені вами.
    # Власні примірники, які зараз у когось у позиці, тут НЕ показуємо.
    from .library_service import (
        ensure_personal_library,
        library_active_loans_by_copy,
        list_my_library_shelves,
    )

    shelves_all = list_my_library_shelves(request.user)
    lib = ensure_personal_library(request.user)
    shared_member_count = lib.memberships.count()
    is_shared_library = shared_member_count >= 2
    pending_returns_to_confirm = list(
        Shelf.objects.filter(borrowed_from=request.user, return_pending=True)
        .select_related("user", "book", "copy")
        .order_by("-added_at")
    )
    loan_by_copy = library_active_loans_by_copy(lib)
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
    from .book_photos import is_local_isbn, user_can_edit_manual_book
    import json
    from django.urls import reverse
    from django.utils.safestring import mark_safe

    for s in shelves:
        s.can_edit_manual = (not s.borrowed_from_id) and user_can_edit_manual_book(
            request.user, s.book
        )
        if s.can_edit_manual:
            b = s.book
            payload = {
                "edit_url": reverse("update_manual_shelf_book", args=[s.id]),
                "isbn": "" if is_local_isbn(b.isbn) else (b.isbn or ""),
                "title": b.title or "",
                "authors": b.authors or "",
                "publisher": b.publisher or "",
                "publish_date": b.publish_date or "",
                "cover_text": b.cover_text or "",
                "photos": [
                    {"id": p.id, "url": p.image.url} for p in b.photos.all()
                ],
            }
            # Safe for <script type="application/json"> (avoid </script> breakout)
            raw = json.dumps(payload, ensure_ascii=False)
            s.edit_payload_json = mark_safe(
                raw.replace("<", "\\u003c")
                .replace(">", "\\u003e")
                .replace("&", "\\u0026")
            )
        else:
            s.edit_payload_json = ""

    from .book_price import library_price_total_uah, serialize_evaluation
    from .copy_listing import LISTING_CHECKBOX_FLAGS, SALE_GIFT_RADIO
    from .models import BookPriceEvaluation

    evals_for_total = []
    for s in shelves:
        ev = getattr(s.book, "price_evaluation", None)
        pe = serialize_evaluation(ev)
        s.price_eval = pe
        if pe and pe.get("quotes") is not None:
            raw_q = json.dumps(pe["quotes"], ensure_ascii=False)
            s.price_quotes_json = mark_safe(
                raw_q.replace("<", "\\u003c")
                .replace(">", "\\u003e")
                .replace("&", "\\u0026")
            )
        else:
            s.price_quotes_json = mark_safe("[]")
        if ev and ev.status == BookPriceEvaluation.Status.READY:
            evals_for_total.append(ev)
    library_price_total = library_price_total_uah(evals_for_total)

    locked_raw = request.session.get("reader_age_locked_shelf_ids", [])
    if not isinstance(locked_raw, list):
        locked_raw = []
    # Legacy session key no longer used for lock UI; keep cleared.
    if locked_raw:
        request.session["reader_age_locked_shelf_ids"] = []
        request.session.modified = True

    confirm_extra = request.session.pop("library_confirm_extra", None)
    if confirm_extra:
        request.session.modified = True

    from .book_lookup import provider_labels

    isbn_providers = provider_labels()

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
            "library_price_total": library_price_total,
            "listing_checkbox_flags": LISTING_CHECKBOX_FLAGS,
            "sale_gift_radio": SALE_GIFT_RADIO,
            "confirm_extra": confirm_extra,
            "is_shared_library": is_shared_library,
            "shared_member_count": shared_member_count,
            "shared_library_name": lib.display_name,
            "i_am_library_admin": lib.admin_id == request.user.id,
            "isbn_providers": isbn_providers,
        },
    )


@login_required
def shared_library(request):
    """Спільна бібліотека: merge/split, голосування за адміна, approve дій."""
    from .library_service import (
        AwaitAdminIsbn,
        LibraryError,
        accept_invite,
        admin_confirm_merge_isbn,
        cancel_admin_election,
        cancel_invite,
        cast_admin_vote,
        finalize_admin_election,
        generate_merge_code,
        library_snapshot,
        redeem_merge_code,
        reject_invite,
        request_split_leave,
        resolve_action,
        start_admin_election,
    )

    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "generate_merge_code":
                mc = generate_merge_code(request.user)
                messages.success(
                    request,
                    f"Код об'єднання: {mc.code} (дійсний 5 хв).",
                )
            elif action == "redeem_merge_code":
                result = redeem_merge_code(
                    request.user, request.POST.get("merge_code") or ""
                )
                if isinstance(result, AwaitAdminIsbn):
                    messages.info(
                        request,
                        "Код прийнято. Адміністратор має підтвердити кількість "
                        "спільних ISBN.",
                    )
                else:
                    messages.success(
                        request,
                        "Бібліотеки об'єднано. За потреби проголосуйте за адміністратора.",
                    )
            elif action == "cancel_invite":
                cancel_invite(request.user, int(request.POST.get("invite_id")))
                messages.info(request, "Запрошення скасовано.")
            elif action == "reject_invite":
                reject_invite(request.user, int(request.POST.get("invite_id")))
                messages.info(request, "Запрошення відхилено.")
            elif action == "accept_invite":
                result = accept_invite(
                    request.user,
                    int(request.POST.get("invite_id")),
                )
                if isinstance(result, AwaitAdminIsbn):
                    messages.info(
                        request,
                        "Ви погодились. Адміністратор має підтвердити кількість "
                        "спільних ISBN.",
                    )
                else:
                    messages.success(
                        request,
                        "Бібліотеки об'єднано. За потреби проголосуйте за адміністратора.",
                    )
            elif action == "confirm_merge_isbn":
                isbn_counts = {}
                for key, val in request.POST.items():
                    if key.startswith("isbn_count_"):
                        isbn_counts[key.replace("isbn_count_", "", 1)] = int(val)
                admin_confirm_merge_isbn(
                    request.user,
                    int(request.POST.get("invite_id")),
                    isbn_counts=isbn_counts,
                )
                messages.success(
                    request,
                    "Кількість ISBN підтверджено — бібліотеки об'єднано.",
                )
            elif action == "resolve_action":
                resolve_action(
                    request.user,
                    int(request.POST.get("action_id")),
                    approve=request.POST.get("approve") == "1",
                )
                messages.success(request, "Рішення збережено.")
            elif action == "split_leave":
                ids = [
                    int(x)
                    for x in request.POST.getlist("copy_ids")
                    if str(x).isdigit()
                ]
                if not ids:
                    raw = request.POST.get("copy_ids") or ""
                    ids = [
                        int(x)
                        for x in raw.replace(",", " ").split()
                        if x.strip().isdigit()
                    ]
                request_split_leave(request.user, ids)
                messages.info(request, "Запит на вихід/поділ надіслано адміністратору.")
            elif action == "start_election":
                start_admin_election(
                    request.user,
                    reason=request.POST.get("reason") or "Зміна адміністратора",
                )
                messages.success(request, "Голосування за адміна відкрито.")
            elif action == "vote_admin":
                cast_admin_vote(
                    request.user,
                    int(request.POST.get("election_id")),
                    int(request.POST.get("candidate_id")),
                )
                messages.success(request, "Голос зараховано.")
            elif action == "finalize_election":
                finalize_admin_election(
                    request.user, int(request.POST.get("election_id"))
                )
                messages.success(request, "Адміністратора обрано.")
            elif action == "cancel_election":
                cancel_admin_election(
                    request.user, int(request.POST.get("election_id"))
                )
                messages.info(request, "Голосування скасовано.")
        except LibraryError as e:
            overlap = getattr(e, "overlap", None)
            if overlap is not None:
                snap = library_snapshot(request.user)
                return render(
                    request,
                    "mainApp/shared_library.html",
                    {
                        "snap": snap,
                        "merge_overlap": overlap,
                        "merge_invite_id": request.POST.get("invite_id"),
                    },
                )
            messages.error(request, e.message)
        return redirect("shared_library")

    return render(
        request,
        "mainApp/shared_library.html",
        {"snap": library_snapshot(request.user)},
    )


@login_required
@require_POST
def refresh_book_price_view(request, book_id):
    """User-requested re-evaluation of ISBN market price (library only)."""
    from .book_price import ensure_pending_and_schedule, serialize_evaluation
    from .models import Book, Shelf

    owns = Shelf.objects.filter(user=request.user, book_id=book_id).exists()
    if not owns:
        return JsonResponse({"detail": "Книга не на вашій полиці."}, status=403)
    book = Book.objects.filter(pk=book_id).first()
    if not book:
        return JsonResponse({"detail": "Книгу не знайдено."}, status=404)
    ev = ensure_pending_and_schedule(book, force=True)
    is_xhr = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if is_xhr:
        return JsonResponse({"ok": True, "price_eval": serialize_evaluation(ev)})
    messages.info(request, "Оновлення оцінки ціни запущено.")
    return redirect("my_library")


@login_required
@require_POST
def refresh_book_metadata_view(request, book_id):
    """Re-fetch title/authors/cover/… from ISBNdb (etc.) for a shelf book."""
    from .exchange.catalog import refresh_book_metadata_from_catalog
    from .models import Book, Shelf

    owns = Shelf.objects.filter(user=request.user, book_id=book_id).exists()
    if not owns:
        return JsonResponse({"detail": "Книга не на вашій полиці."}, status=403)
    book = (
        Book.objects.filter(pk=book_id)
        .prefetch_related("photos", "price_evaluation__quotes")
        .first()
    )
    if not book:
        return JsonResponse({"detail": "Книгу не знайдено."}, status=404)

    search_log: list = []
    is_xhr = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    try:
        book = refresh_book_metadata_from_catalog(book, search_log=search_log)
    except ExchangeError as exc:
        if is_xhr:
            return JsonResponse(
                {
                    "ok": False,
                    "detail": exc.message,
                    "search_log": search_log,
                },
                status=getattr(exc, "http_status", 404) or 404,
            )
        messages.error(request, exc.message)
        return redirect("my_library")

    hit = next((s for s in reversed(search_log) if s.get("status") == "hit"), None)
    src = (hit or {}).get("label") or ""
    msg = f"Оновлено з каталогу: {book.title}"
    if src:
        msg = f"{msg} ({src})"
    if is_xhr:
        return JsonResponse(
            {
                "ok": True,
                "detail": msg,
                "title": book.title,
                "authors": book.authors,
                "isbn": book.isbn,
                "cover_url": book.cover_url,
                "publisher": book.publisher,
                "publish_date": book.publish_date,
                "search_log": search_log,
                "search_source": src or None,
            }
        )
    messages.success(request, msg)
    return redirect("my_library")


@login_required
@require_POST
def recognize_book_cover_view(request):
    """Web: AI fill title/authors/ISBN from cover photo(s) (manual add)."""
    files = list(request.FILES.getlist("photos") or [])
    if not files:
        one = request.FILES.get("photo")
        if one:
            files = [one]
    if not files:
        return JsonResponse(
            {"detail": "Потрібне фото обкладинки (поле photo або photos)."},
            status=400,
        )
    from .book_cover_ai import CoverAIError, recognize_book_covers, vision_configured

    if not vision_configured():
        return JsonResponse(
            {"detail": "Розпізнавання не налаштовано (OCR_SPACE_API_KEY або OPENAI_API_KEY)."},
            status=503,
        )
    try:
        data = recognize_book_covers(files)
    except CoverAIError as exc:
        return JsonResponse({"detail": exc.message}, status=exc.status)
    return JsonResponse(data)


@login_required
@require_POST
def update_manual_shelf_book(request, shelf_id):
    """Web: edit sole-owned manually added book on the shelf."""
    from .book_photos import (
        delete_book_photos,
        save_book_photos,
        update_manual_book,
        user_can_edit_manual_book,
    )

    shelf = (
        request.user.shelf_entries.select_related("book", "copy")
        .prefetch_related("book__photos")
        .filter(pk=shelf_id)
        .first()
    )
    is_xhr = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if not shelf:
        if is_xhr:
            return JsonResponse({"ok": False, "detail": "Запис не знайдено."}, status=404)
        messages.error(request, "Запис не знайдено.")
        return redirect("my_library")
    if shelf.borrowed_from_id:
        msg = "Позичену книгу не можна редагувати."
        if is_xhr:
            return JsonResponse({"ok": False, "detail": msg}, status=400)
        messages.error(request, msg)
        return redirect("my_library")
    if is_copy_lent_out(shelf.copy_id):
        msg = "Примірник зараз у позиці — спочатку дочекайтесь повернення."
        if is_xhr:
            return JsonResponse({"ok": False, "detail": msg}, status=400)
        messages.error(request, msg)
        return redirect("my_library")
    if not user_can_edit_manual_book(request.user, shelf.book):
        msg = "Редагувати можна лише власні вручну додані книги."
        if is_xhr:
            return JsonResponse({"ok": False, "detail": msg}, status=403)
        messages.error(request, msg)
        return redirect("my_library")

    form = EditBookManualForm(request.POST, request.FILES)
    photos = request.FILES.getlist("photos")
    if form.is_valid():
        d = form.cleaned_data
        try:
            book = update_manual_book(
                shelf.book,
                isbn=(d.get("isbn") or "").strip(),
                title=(d.get("title") or "").strip(),
                authors=(d.get("authors") or "").strip(),
                publisher=(d.get("publisher") or "").strip(),
                publish_date=(d.get("publish_date") or "").strip(),
                cover_url=(d.get("cover_url") or "").strip()
                if "cover_url" in request.POST
                else None,
                info_url=(d.get("info_url") or "").strip()
                if "info_url" in request.POST
                else None,
                cover_text=(d.get("cover_text") or "").strip()
                if "cover_text" in request.POST
                else None,
            )
        except ValueError as exc:
            if is_xhr:
                return JsonResponse({"ok": False, "detail": str(exc)}, status=400)
            messages.error(request, str(exc))
            return redirect("my_library")

        delete_ids = []
        for raw in request.POST.getlist("delete_photo_ids"):
            if str(raw).isdigit():
                delete_ids.append(int(raw))
        if delete_ids:
            delete_book_photos(book, delete_ids)
        if photos:
            save_book_photos(book, photos, request=request)

        messages.success(request, f"Оновлено: {book.title}")
        if is_xhr:
            from django.urls import reverse

            return JsonResponse(
                {"ok": True, "redirect": reverse("my_library"), "title": book.title}
            )
        return redirect("my_library")

    errs = []
    for field, flist in form.errors.items():
        for e in flist:
            errs.append(f"{field}: {e}" if field != "__all__" else str(e))
    detail = "; ".join(errs) or "Форма невалідна."
    if is_xhr:
        return JsonResponse({"ok": False, "detail": detail, "errors": form.errors.get_json_data()}, status=400)
    messages.error(request, detail)
    return redirect("my_library")


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
@require_POST
def update_shelf_book_reader_age(request, shelf_id):
    """Оновлення min/max рекомендованого віку (autosave з полиці)."""
    shelf = get_object_or_404(
        Shelf.objects.select_related("book"),
        pk=shelf_id,
        user=request.user,
    )
    book = shelf.book
    accept = (request.headers.get("Accept") or "").lower()
    wants_json = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in accept
        or request.POST.get("ajax") == "1"
    )

    def _json(payload, status=200):
        return JsonResponse(payload, status=status)

    try:
        mn = int(request.POST.get("min_readers_age", READER_AGE_MIN))
        mx = int(request.POST.get("max_readers_age", READER_AGE_MAX))
    except (TypeError, ValueError):
        if wants_json:
            return _json({"ok": False, "detail": "Некоректні значення віку."}, 400)
        messages.error(request, "Некоректні значення віку.")
        return redirect("my_library")
    mn = max(READER_AGE_MIN, min(READER_AGE_MAX, mn))
    mx = max(READER_AGE_MIN, min(READER_AGE_MAX, mx))
    if mn > mx:
        mn, mx = mx, mn
    book.min_readers_age = mn
    book.max_readers_age = mx
    try:
        book.full_clean()
    except DjangoValidationError as exc:
        detail = "; ".join(
            str(m)
            for msgs in (
                exc.message_dict.values()
                if hasattr(exc, "message_dict")
                else [getattr(exc, "messages", [str(exc)])]
            )
            for m in (msgs if isinstance(msgs, (list, tuple)) else [msgs])
        ) or str(exc)
        if wants_json:
            return _json({"ok": False, "detail": detail}, 400)
        messages.error(request, detail)
        return redirect("my_library")
    book.save(update_fields=["min_readers_age", "max_readers_age"])
    if wants_json:
        return _json(
            {
                "ok": True,
                "min_readers_age": book.min_readers_age,
                "max_readers_age": book.max_readers_age,
                "reader_age_summary": book.reader_age_summary,
            }
        )
    return redirect("my_library")


@login_required
@require_POST
def update_shelf_copy_listing(request, shelf_id):
    """Owner / admin sets listing; shared-library members → admin chat approval."""
    from .library_service import LibraryAction, LibraryError, request_listing_change

    shelf = get_object_or_404(
        Shelf.objects.select_related("copy", "book", "copy__library", "copy__book"),
        pk=shelf_id,
        user=request.user,
    )
    if shelf.borrowed_from_id:
        messages.error(request, "Статус можна змінити лише для власного примірника.")
        return redirect("my_library")
    if not shelf.copy_id:
        messages.error(request, "Це не ваш примірник.")
        return redirect("my_library")
    listing_kwargs = dict(
        flags={
            "is_fee_sharing": request.POST.get("is_fee_sharing"),
            "is_hidden": request.POST.get("is_hidden"),
            "is_for_rent": request.POST.get("is_for_rent"),
            "is_for_exchange": request.POST.get("is_for_exchange"),
            "is_free_of_deposit": request.POST.get("is_free_of_deposit"),
        },
        sale_gift=request.POST.get("sale_gift", ""),
        sale_price=request.POST.get("sale_price"),
        rent_price_per_day=request.POST.get("rent_price_per_day"),
    )
    try:
        result = request_listing_change(request.user, shelf.copy, listing_kwargs)
    except LibraryError as exc:
        messages.error(request, exc.message)
        return redirect("my_library")
    except DjangoValidationError as exc:
        msgs = []
        if hasattr(exc, "message_dict"):
            for v in exc.message_dict.values():
                msgs.extend(v if isinstance(v, (list, tuple)) else [v])
        else:
            msgs = list(getattr(exc, "messages", [str(exc)]))
        messages.error(request, "; ".join(str(m) for m in msgs) or "Помилка збереження.")
        return redirect("my_library")
    if isinstance(result, LibraryAction):
        messages.info(
            request,
            "Запит на зміну статусів надіслано адміністратору в чат.",
        )
        return redirect("message_thread", partner_id=result.library.admin_id)
    messages.success(request, "Статус примірника збережено.")
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
    """Видалити з полиці; у спільній бібліотеці учасник — через адміна, адмін — одразу."""
    if request.method != "POST":
        return redirect("my_library")
    from .library_service import (
        LibraryAction,
        LibraryError,
        get_removable_shelf,
        request_remove_copy,
    )

    try:
        shelf = get_removable_shelf(request.user, shelf_id)
    except LibraryError as exc:
        messages.error(request, exc.message)
        return redirect("my_library")
    if is_copy_lent_out(shelf.copy_id):
        messages.error(
            request,
            "Примірник зараз у позиці — спочатку дочекайтесь повернення.",
        )
        return redirect("my_library")
    try:
        result = request_remove_copy(request.user, shelf)
    except LibraryError as exc:
        messages.error(request, exc.message)
        return redirect("my_library")
    if isinstance(result, LibraryAction):
        messages.info(
            request,
            "Запит на видалення надіслано адміністратору в чат.",
        )
        return redirect("message_thread", partner_id=result.library.admin_id)
    messages.success(request, "Книгу видалено з полиці.")
    return redirect("my_library")


@login_required
@require_POST
def library_bulk_action(request):
    """Bulk status change / delete for selected owned shelf rows."""
    from .library_service import LibraryError, request_bulk_listing, request_bulk_remove

    raw_ids = request.POST.getlist("shelf_ids")
    if not raw_ids and request.POST.get("shelf_ids"):
        raw_ids = str(request.POST.get("shelf_ids")).split(",")
    try:
        shelf_ids = [int(x) for x in raw_ids if str(x).strip().isdigit()]
    except (TypeError, ValueError):
        shelf_ids = []
    action = (request.POST.get("bulk_action") or "").strip()
    if not shelf_ids:
        messages.error(request, "Не вибрано жодної книги.")
        return redirect("my_library")

    try:
        if action == "delete":
            result = request_bulk_remove(request.user, shelf_ids)
        elif action == "listing":
            listing_kwargs = dict(
                flags={
                    "is_fee_sharing": request.POST.get("is_fee_sharing"),
                    "is_hidden": request.POST.get("is_hidden"),
                    "is_for_rent": request.POST.get("is_for_rent"),
                    "is_for_exchange": request.POST.get("is_for_exchange"),
                    "is_free_of_deposit": request.POST.get("is_free_of_deposit"),
                },
                sale_gift=request.POST.get("sale_gift", ""),
                sale_price=request.POST.get("sale_price"),
                rent_price_per_day=request.POST.get("rent_price_per_day"),
            )
            result = request_bulk_listing(request.user, shelf_ids, listing_kwargs)
        else:
            messages.error(request, "Невідома дія.")
            return redirect("my_library")
    except (LibraryError, DjangoValidationError) as exc:
        msg = getattr(exc, "message", None) or str(exc)
        if isinstance(exc, DjangoValidationError):
            msgs = []
            if hasattr(exc, "message_dict"):
                for v in exc.message_dict.values():
                    msgs.extend(v if isinstance(v, (list, tuple)) else [v])
            else:
                msgs = list(getattr(exc, "messages", [str(exc)]))
            msg = "; ".join(str(m) for m in msgs) or msg
        messages.error(request, msg)
        return redirect("my_library")

    if result.get("pending_approval"):
        messages.info(
            request,
            "Запит надіслано адміністратору спільної бібліотеки в чат.",
        )
        return redirect("message_thread", partner_id=result["admin_id"])
    if action == "delete":
        messages.success(
            request,
            f"Видалено примірників: {result.get('removed', 0)}.",
        )
    else:
        messages.success(
            request,
            f"Оновлено статуси для {result.get('updated', 0)} примірник(ів).",
        )
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
    from .copy_qr import copy_has_bound_qr

    shelf = (
        Shelf.objects.select_related("copy")
        .filter(pk=shelf_id, borrowed_from=request.user, return_pending=True)
        .first()
    )
    qr = request.POST.get("qr_payload") or request.POST.get("qr")
    if shelf and copy_has_bound_qr(shelf.copy) and not qr:
        from django.urls import reverse

        q = f"{reverse('copy_qr_scan')}?return_shelf_id={shelf_id}"
        partner_id = request.POST.get("partner_id")
        if partner_id:
            q += f"&partner_id={partner_id}"
        return redirect(q)
    web_exchange(
        request,
        confirm_borrow_return,
        shelf_id,
        request.user,
        success="Повернення підтверджено — позику знято з полиці позичальника.",
        qr_payload=qr,
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
    from .exchange import get_shelf_query_service

    catalog = get_shelf_query_service().load_browse_catalog(request.user)
    return render(
        request,
        "mainApp/browse_shelves.html",
        {
            "others_grouped": catalog.others_grouped,
            "my_owned_shelves": catalog.my_owned,
            "loan_days": int(getattr(settings, "DEFAULT_LOAN_DAYS", 14)),
        },
    )


@login_required
def user_public_shelf(request, user_id):
    """Полиця користувача = лише те, що фізично у нього (власне вільне + позичене ним)."""
    from .exchange import get_shelf_query_service

    User = get_user_model()
    shelf_owner = get_object_or_404(User, pk=user_id)
    if request.user.pk == shelf_owner.pk:
        return redirect("profile_app:profile")
    shelves = get_shelf_query_service().for_user_physical_shelf(
        shelf_owner, viewer=request.user
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
    # Hidden copies visible only to their owner.
    copies = [
        c
        for c in copies
        if not c.is_hidden or c.owner_id == request.user.pk
    ]
    shelf_entries = list(
        Shelf.objects.filter(book=book, copy_id__in=[c.pk for c in copies])
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
    from .copy_qr import serialize_copy_qr

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
            "qr_meta": serialize_copy_qr(copy),
        },
    )


@login_required
@require_POST
def copy_qr_ensure(request, copy_id):
    """Late binding: do not assign token here — send owner to print sheet."""
    copy = get_object_or_404(BookCopy, pk=copy_id)
    if copy.owner_id != request.user.id:
        messages.error(request, "QR може друкувати лише власник.")
        return redirect("copy_history", copy_id=copy_id)
    messages.info(
        request,
        "Роздрукуйте наклейки, наклейте на книгу, потім «Скан QR» на примірнику.",
    )
    from django.urls import reverse

    return redirect(f"{reverse('copy_qr_print')}?from=settings")


@login_required
@require_POST
def copy_qr_rotate(request, copy_id):
    """Відв’язати втрачену наклейку; новий код — лише після друку + скану."""
    from .copy_qr import rotate_copy_qr

    try:
        rotate_copy_qr(copy_id, request.user)
        messages.success(
            request,
            "Старий QR скасовано. Роздрукуйте нові наклейки й прив’яжіть «Скан QR».",
        )
    except ExchangeError as exc:
        messages.error(request, exc.message)
        return redirect("copy_history", copy_id=copy_id)
    from django.urls import reverse

    return redirect(f"{reverse('copy_qr_print')}?from=settings")


@login_required
@require_POST
def copy_qr_attach(request, copy_id):
    """Прив’язати наклеєний QR сканом (власник)."""
    from .copy_qr import attach_copy_qr

    payload = request.POST.get("qr_payload") or request.POST.get("qr") or ""
    try:
        attach_copy_qr(copy_id, request.user, payload)
        messages.success(request, "QR-наклейку прив’язано до цього примірника.")
    except ExchangeError as exc:
        messages.error(request, exc.message)
    next_url = request.POST.get("next")
    if next_url:
        return redirect(next_url)
    return redirect("copy_history", copy_id=copy_id)


@login_required
def copy_qr_print(request):
    """A4 sheet: 6×6 = 36 unique QR labels (title + QR), dotted cut grid."""
    from .copy_qr import (
        A4_COLS,
        A4_ROWS,
        LABEL_H_MM,
        LABEL_W_MM,
        QR_BRAND_TITLE,
        QR_PRINT_MM,
        SLOTS_PER_A4_PAGE,
        build_full_a4_print_pages,
    )

    pages = build_full_a4_print_pages(request.user)
    labels = [lab for page in pages for lab in page]
    back = (request.GET.get("from") or "").strip()
    if back not in ("settings", "my_library"):
        back = "settings"
    # Locale can render floats as "33,33" → invalid CSS → grid collapses to 1 column.
    return render(
        request,
        "mainApp/copy_qr_print.html",
        {
            "pages": pages,
            "labels": labels,
            "cols": A4_COLS,
            "rows": A4_ROWS,
            "qr_mm": f"{QR_PRINT_MM:g}",
            "label_w_mm": f"{LABEL_W_MM:.4f}",
            "label_h_mm": f"{LABEL_H_MM:.4f}",
            "sheet_w_mm": f"{LABEL_W_MM * A4_COLS:.4f}",
            "sheet_h_mm": f"{LABEL_H_MM * A4_ROWS:.4f}",
            "slots_per_page": SLOTS_PER_A4_PAGE,
            "brand_title": QR_BRAND_TITLE,
            "back_url_name": back,
        },
    )


@login_required
def settings_view(request):
    """Налаштування акаунта / сервіси (друк QR тощо)."""
    return render(request, "mainApp/settings.html", {})


@login_required
def copy_qr_scan(request):
    """Сканер QR: ідентифікація примірника, прив’язка, передача або повернення."""
    from .copy_qr import resolve_copy_by_qr
    from .exchange.handoff import handoffs_involving

    handoff_id = request.GET.get("handoff_id") or request.POST.get("handoff_id")
    action = (request.GET.get("action") or request.POST.get("action") or "").strip()
    attach_copy_id = request.GET.get("attach_copy_id") or request.POST.get(
        "attach_copy_id"
    )
    return_shelf_id = request.GET.get("return_shelf_id") or request.POST.get(
        "return_shelf_id"
    )
    resolved = None
    if request.method == "POST":
        payload = request.POST.get("qr_payload") or request.POST.get("qr") or ""
        if return_shelf_id and str(return_shelf_id).isdigit():
            try:
                confirm_borrow_return(
                    int(return_shelf_id), request.user, qr_payload=payload
                )
                messages.success(
                    request, "Повернення підтверджено сканом QR."
                )
                partner_id = request.POST.get("partner_id")
                if partner_id:
                    return redirect("message_thread", partner_id=int(partner_id))
                return redirect("my_library")
            except ExchangeError as exc:
                messages.error(request, exc.message)
        elif attach_copy_id and str(attach_copy_id).isdigit():
            from .copy_qr import attach_copy_qr

            try:
                copy = attach_copy_qr(int(attach_copy_id), request.user, payload)
                messages.success(
                    request, f"QR прив’язано до примірника #{copy.id}."
                )
                return redirect("copy_history", copy_id=copy.id)
            except ExchangeError as exc:
                messages.error(request, exc.message)
        elif handoff_id and str(handoff_id).isdigit() and action in (
            "give",
            "receive",
        ):
            try:
                if action == "give":
                    confirm_handoff_give(
                        int(handoff_id), request.user, qr_payload=payload
                    )
                    messages.success(
                        request,
                        "Віддачу підтверджено сканом QR.",
                    )
                else:
                    confirm_handoff_receive(
                        int(handoff_id), request.user, qr_payload=payload
                    )
                    messages.success(
                        request,
                        "Отримання підтверджено сканом QR.",
                    )
                partner_id = request.POST.get("partner_id")
                if partner_id:
                    return redirect("message_thread", partner_id=int(partner_id))
                return redirect("exchange_requests")
            except ExchangeError as exc:
                messages.error(request, exc.message)
        else:
            try:
                copy = resolve_copy_by_qr(payload)
                return redirect("copy_history", copy_id=copy.id)
            except ExchangeError as exc:
                messages.error(request, exc.message)

    active_handoffs = handoffs_involving(request.user.id)
    return render(
        request,
        "mainApp/copy_qr_scan.html",
        {
            "handoff_id": handoff_id or "",
            "action": action,
            "attach_copy_id": attach_copy_id or "",
            "return_shelf_id": return_shelf_id or "",
            "partner_id": request.GET.get("partner_id")
            or request.POST.get("partner_id")
            or "",
            "active_handoffs": active_handoffs,
            "resolved": resolved,
        },
    )


@login_required
def create_exchange(request):
    """
    POST з browse_shelves: target_shelf_ids[] (чекбокси) + offer_shelf_id_<pk> для кожного рядка.
    Підтримує один або кілька запитів за одну відправку.
    """
    from .exchange import get_shelf_query_service

    if request.method != "POST":
        return redirect("browse_shelves")

    err_cap = 12
    raw_ids = request.POST.getlist("target_shelf_ids")
    if not raw_ids:
        messages.error(request, "Оберіть хоча б одну книгу (рядок у таблиці).")
        return redirect("browse_shelves")

    seen: set[int] = set()
    lines: list[tuple[Shelf, Shelf | None, object | None, bool]] = []
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
        offer_open = False
        raw_offer = request.POST.get(f"offer_shelf_id_{tid}", "") or ""
        # Позичений примірник / передача — лише borrow/transmit, без обміну
        if is_copy_lent_out(target_shelf.copy_id) or target_shelf.borrowed_from_id:
            raw_offer = ""
        if raw_offer.strip() == "__open__":
            offer_open = True
            raw_offer = ""
        if raw_offer.strip():
            try:
                oid = int(raw_offer)
            except (TypeError, ValueError):
                t = target_shelf.book.title
                preflight.append(f'"{t[:45]}": некоректна книга для обміну.')
                continue
            offer_shelf = get_shelf_query_service().get_available_owned_offer(
                request.user, oid
            )
            if not offer_shelf:
                t = target_shelf.book.title
                preflight.append(
                    f'"{t[:45]}": запропоновану книгу не знайдено серед ваших вільних.'
                )
                continue

        proposed_due = None
        if not offer_shelf:
            raw_due = (request.POST.get(f"proposed_due_date_{tid}", "") or "").strip()
            if raw_due:
                proposed_due = raw_due

        lines.append((target_shelf, offer_shelf, proposed_due, offer_open))

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
    pending_in_list = list(pending_in)
    for r in pending_in_list:
        if r.offer_open and not r.offer_shelf_id:
            r.offerable_shelves = offerable_shelves_from_requester(r)
        else:
            r.offerable_shelves = []
    return render(
        request,
        "mainApp/exchange_requests.html",
        {
            "pending_in": pending_in_list,
            "pending_out": pending_out,
            "history": history,
        },
    )


@login_required
def exchange_pick_offer(request, request_id):
    """Власник обирає книгу з полиці запитувача (offer_open)."""
    if request.method != "POST":
        return redirect("exchange_requests")
    raw = request.POST.get("offer_shelf_id") or ""
    try:
        oid = int(raw)
    except (TypeError, ValueError):
        messages.error(request, "Оберіть книгу для обміну.")
        return redirect("exchange_requests")
    try:
        pick_offer_by_owner(request_id, request.user, oid)
        messages.success(
            request,
            "Книгу для обміну обрано. Можете прийняти обмін або ще змінити відповідь.",
        )
    except ExchangeError as exc:
        messages.error(request, exc.message)
    partner_id = request.POST.get("partner_id")
    if partner_id:
        try:
            return redirect("message_thread", partner_id=int(partner_id))
        except (TypeError, ValueError):
            pass
    return redirect("exchange_requests")


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
        accept_exchange_request(
            request_id,
            request.user,
            due_date=request.POST.get("due_date") or None,
        )
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
    partner_id = request.POST.get("partner_id")
    if partner_id:
        try:
            return redirect("message_thread", partner_id=int(partner_id))
        except (TypeError, ValueError):
            pass
    return redirect("exchange_requests")


@login_required
def exchange_propose_due(request, request_id):
    """Власник / позичальник пропонує інший термін повернення."""
    if request.method != "POST":
        return redirect("exchange_requests")
    due = request.POST.get("due_date") or request.POST.get("proposed_due_date")
    try:
        propose_exchange_due_date(request_id, request.user, due)
        messages.success(request, "Новий термін повернення надіслано іншій стороні.")
    except ExchangeError as exc:
        messages.error(request, exc.message)
    partner_id = request.POST.get("partner_id")
    if partner_id:
        try:
            return redirect("message_thread", partner_id=int(partner_id))
        except (TypeError, ValueError):
            pass
    return redirect("exchange_requests")


@login_required
def exchange_confirm_due(request, request_id):
    """Погодити запропонований термін повернення."""
    if request.method != "POST":
        return redirect("exchange_requests")
    try:
        confirm_exchange_due_date(request_id, request.user)
        messages.success(request, "Термін повернення погоджено.")
    except ExchangeError as exc:
        messages.error(request, exc.message)
    partner_id = request.POST.get("partner_id")
    if partner_id:
        try:
            return redirect("message_thread", partner_id=int(partner_id))
        except (TypeError, ValueError):
            pass
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
    partner_id = request.POST.get("partner_id")
    if partner_id:
        try:
            return redirect("message_thread", partner_id=int(partner_id))
        except (TypeError, ValueError):
            pass
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
    partner_id = request.POST.get("partner_id")
    if partner_id:
        try:
            return redirect("message_thread", partner_id=int(partner_id))
        except (TypeError, ValueError):
            pass
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
    from .copy_qr import copy_has_bound_qr

    msg = get_object_or_404(PrivateMessage, pk=message_id, recipient=request.user)
    payload = notification_payload(msg)
    shelf_id = payload.get("confirm_return_shelf_id")
    if payload.get("kind") != "return" or not shelf_id:
        messages.error(request, "Це сповіщення не є активним запитом на повернення.")
        return redirect("notifications_inbox")
    shelf = (
        Shelf.objects.select_related("copy")
        .filter(pk=shelf_id, borrowed_from=request.user, return_pending=True)
        .first()
    )
    qr = request.POST.get("qr_payload") or request.POST.get("qr")
    if shelf and copy_has_bound_qr(shelf.copy) and not qr:
        from django.urls import reverse

        return redirect(f"{reverse('copy_qr_scan')}?return_shelf_id={shelf_id}")
    ok, _ = web_exchange(
        request,
        confirm_borrow_return,
        shelf_id,
        request.user,
        success="Повернення підтверджено.",
        qr_payload=qr,
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
    Окремий чат лише з одним користувачем (спільний запит на позику/обмін / merge бібліотек).
    Загальної скриньки немає - посилання тільки з обмінів / позики / спільної бібліотеки.
    """
    from .library_service import LibraryError, accept_invite, cancel_invite, reject_invite
    from .messaging import (
        MessagingForbidden,
        MessagingNoPartners,
        MessagingNotFound,
        get_messaging_service,
    )

    chat = get_messaging_service()

    if request.method == "POST" and "library_invite_accept" in request.POST:
        from .library_service import AwaitAdminIsbn

        try:
            result = accept_invite(
                request.user,
                int(request.POST.get("invite_id")),
            )
            if isinstance(result, AwaitAdminIsbn):
                messages.info(
                    request,
                    "Ви погодились. Адміністратор підтвердить кількість спільних ISBN.",
                )
            else:
                messages.success(
                    request,
                    "Бібліотеки об'єднано. За потреби проголосуйте за адміністратора.",
                )
        except LibraryError as exc:
            messages.error(request, exc.message)
        return redirect("message_thread", partner_id=partner_id)

    if request.method == "POST" and "library_invite_reject" in request.POST:
        try:
            reject_invite(request.user, int(request.POST.get("invite_id")))
            messages.info(request, "Запит на об'єднання відхилено.")
        except LibraryError as exc:
            messages.error(request, exc.message)
        return redirect("message_thread", partner_id=partner_id)

    if request.method == "POST" and "library_invite_cancel" in request.POST:
        try:
            cancel_invite(request.user, int(request.POST.get("invite_id")))
            messages.info(request, "Запит на об'єднання скасовано.")
        except LibraryError as exc:
            messages.error(request, exc.message)
        return redirect("message_thread", partner_id=partner_id)

    if request.method == "POST" and "library_action_resolve" in request.POST:
        from .library_service import resolve_action

        try:
            resolve_action(
                request.user,
                int(request.POST.get("action_id")),
                approve=request.POST.get("approve") == "1",
            )
            messages.success(request, "Рішення збережено.")
        except LibraryError as exc:
            messages.error(request, exc.message)
        return redirect("message_thread", partner_id=partner_id)

    if request.method == "POST" and "send_message" in request.POST:
        form = SendExchangePartnerMessageForm(request.POST)
        if form.is_valid():
            try:
                msg = chat.send(request.user, partner_id, form.cleaned_data["body"])
            except (MessagingForbidden, MessagingNotFound) as exc:
                messages.error(request, exc.message)
                return redirect("exchange_requests")
            if msg:
                messages.success(request, "Повідомлення надіслано.")
            else:
                messages.warning(request, "Порожній текст - нічого не надіслано.")
            return redirect("message_thread", partner_id=partner_id)
    else:
        form = SendExchangePartnerMessageForm()

    try:
        ctx = chat.open_thread(request.user, partner_id)
    except MessagingNoPartners as exc:
        messages.info(request, exc.message)
        return redirect("exchange_requests")
    except MessagingForbidden as exc:
        messages.error(request, exc.message)
        return redirect("exchange_requests")
    except MessagingNotFound as exc:
        messages.error(request, exc.message)
        return redirect("exchange_requests")

    return render(
        request,
        "mainApp/messages.html",
        {"form": form, **ctx.as_web_dict()},
    )


@login_required
@require_POST
def handoff_confirm_give_view(request, handoff_id):
    qr = request.POST.get("qr_payload") or request.POST.get("qr")
    try:
        confirm_handoff_give(handoff_id, request.user, qr_payload=qr)
        messages.success(
            request,
            "Віддачу підтверджено — очікуємо підтвердження отримання.",
        )
    except ExchangeError as exc:
        messages.error(request, exc.message)
    partner_id = request.POST.get("partner_id")
    if partner_id:
        return redirect("message_thread", partner_id=int(partner_id))
    return redirect("exchange_requests")


@login_required
@require_POST
def handoff_confirm_receive_view(request, handoff_id):
    qr = request.POST.get("qr_payload") or request.POST.get("qr")
    try:
        confirm_handoff_receive(handoff_id, request.user, qr_payload=qr)
        messages.success(
            request,
            "Отримання підтверджено — книга на вашій полиці; "
            "попередній позичальник вийшов з чату.",
        )
    except ExchangeError as exc:
        messages.error(request, exc.message)
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