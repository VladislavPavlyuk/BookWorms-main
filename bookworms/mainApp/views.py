from django.contrib import messages
from django.contrib.auth import login
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from .models import BookExchangeRequest, Post, Shelf, Comment, Like
from django.contrib.auth.views import LoginView
from .forms import UserLoginForm, UserRegisterForm, AddIsbnForm
from django.views.generic import CreateView
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.urls import reverse, reverse_lazy
from .forms import UserUpdateForm
from .openlibrary import fetch_book_by_isbn
from django.conf import settings
from django.utils.encoding import force_str
# Бізнес-правила обміну/позик винесені в exchange_service - тут лише HTTP і шаблони.
from .message_service import (
    get_exchange_message_partners,
    mark_thread_read,
    send_user_message,
)
from .exchange_service import (
    accept_exchange_request,
    cancel_exchange_request,
    confirm_borrow_return,
    create_many_exchange_requests,
    get_or_create_book_from_payload,
    reject_exchange_request,
    request_borrow_return,
)
from django.core.mail import send_mail

from .tokens import account_activation_token


def home(request):
    posts = Post.objects.all().order_by('-created_ad')
    return render(request, 'mainApp/index.html', {'posts': posts})


@login_required
def profile(request):
    return render(request, 'mainApp/profile.html')


class CustomLoginView(LoginView):
    template_name = 'mainApp/login.html'
    authentication_form = UserLoginForm

class CustomRegisterView(CreateView):
    template_name = 'mainApp/register.html'
    form_class = UserRegisterForm
    success_url = reverse_lazy('confirm_email')

    def form_valid(self, form):
        # 1. Создаем юзера, но не активируем
        user = form.save(commit=False)
        user.is_active = False
        user.save()

        # 2. Формируем данные для ссылки подтверждения
        current_site = get_current_site(self.request)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = account_activation_token.make_token(user)

        # Ссылка, по которой юзер кликнет в письме
        relative_link = reverse('activate', kwargs={'uidb64': uid, 'token': token})
        activation_url = f"http://{current_site.domain}{relative_link}"

        # 3. Контент письма
        subject = "Підтвердження реєстрації BookWorms"
        message = f"Вітаємо, {user.username}!\nДля активації аккаунта перейдіть за посиланням: {activation_url}"

        html_message = f"""
            <div style="font-family: Arial, sans-serif; border: 1px solid #ddd; padding: 20px;">
                <h2 style="color: #2c3e50;">Ласкаво просимо в BookWorms!</h2>
                <p>Вы успішно зареєструвались. Залишився останній крок — підтвердіть пошту.</p>
                <a href="{activation_url}" 
                   style="display: inline-block; padding: 10px 20px; background-color: #4CAF50; color: white; text-decoration: none; border-radius: 5px;">
                   Активувати мій акаунт
                </a>
                <p style="margin-top: 20px; font-size: 12px; color: #777;">
                    Якщо ви не реєструвались на нашому сайті, просто проігноруйте цей лист.
                </p>
            </div>
        """

        # 4. Отправка письма
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=html_message,
                fail_silently=False,
            )
        except Exception as e:

            user.delete()
            form.add_error(None, f"Помилка відправки листа: {e}. Перевірте налаштування SMTP.")
            return self.form_invalid(form)

        return super().form_valid(form)


def activate(request, uidb64, token):
    User = get_user_model()
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    # Проверяем токен
    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        return render(request, 'mainApp/activation_success.html')
    else:
        return render(request, 'mainApp/activation_invalid.html')


def activation_success_view(request):
    return render(request, 'mainApp/activation_success.html')

def activation_invalid_view(request):
    return render(request, 'mainApp/activation_invalid.html')

def confirm_email_view(request):
    return render(request, 'mainApp/confirm_email.html')

@login_required
def create_post(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        text = request.POST.get('text')

        if title and text:
            Post.objects.create(
                author=request.user,
                title=title,
                text=text
            )
            return redirect('home')

    return render(request, 'mainApp/form.html')


@login_required
def delete_post(request, post_id):
    post = Post.objects.get(id=post_id)

    if post.author == request.user:
        post.delete()

    return redirect('home')

@login_required
def edit_post(request, post_id):
    post = Post.objects.get(id=post_id)

    if post.author != request.user:
        return redirect('home')

    if request.method == 'POST':
        post.title = request.POST.get('title')
        post.text = request.POST.get('text')
        post.save()
        return redirect('home')

    return render(request, 'mainApp/form.html', {'post': post})

@login_required
def my_library(request):
    """
    Сторінка "Моя полиця": додавання книги за ISBN (Open Library) + список записів Shelf поточного користувача.
    """
    form = AddIsbnForm()
    if request.method == "POST" and "add_isbn" in request.POST:
        form = AddIsbnForm(request.POST)
        if form.is_valid():
            payload, err = fetch_book_by_isbn(form.cleaned_data["isbn"])
            if err:
                messages.error(request, err)
            else:
                # Спочатку єдиний запис Book за ISBN, потім зв’язок "я маю цю книгу" - Shelf.
                book, _ = get_or_create_book_from_payload(payload)
                try:
                    Shelf.objects.create(user=request.user, book=book)
                    messages.success(request, f"Додано: {book.title}")
                    return redirect("my_library")
                except IntegrityError:
                    # Спрацювало обмеження unique (user, book).
                    messages.warning(request, "Ця книга вже є на вашій полиці.")
                    form = AddIsbnForm()

    # borrowed_from підтягуємо одним запитом - щоб у шаблоні знати, позичена книга чи власна.
    shelves = (
        request.user.shelf_entries.select_related("book", "borrowed_from").all()
    )
    pending_returns_to_confirm = (
        Shelf.objects.filter(borrowed_from=request.user, return_pending=True)
        .select_related("user", "book")
        .order_by("-added_at")
    )
    return render(
        request,
        "mainApp/library.html",
        {
            "form": form,
            "shelves": shelves,
            "pending_returns_to_confirm": pending_returns_to_confirm,
        },
    )


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
    shelf.delete()
    messages.success(request, "Книгу видалено з полиці.")
    return redirect("my_library")


@login_required
def return_borrowed_shelf_book(request, shelf_id):
    if request.method != "POST":
        return redirect("my_library")
    ok, err = request_borrow_return(shelf_id, request.user)
    if ok:
        messages.success(
            request,
            "Запит на повернення надіслано. Книга зникне з вашої полиці після підтвердження позикодавцем.",
        )
    else:
        messages.error(request, err or "Помилка.")
    return redirect("my_library")


@login_required
def confirm_return_borrowed_shelf_book(request, shelf_id):
    """Позикодавець підтверджує отримання фізично повернутої книги."""
    if request.method != "POST":
        return redirect("my_library")
    ok, err = confirm_borrow_return(shelf_id, request.user)
    if ok:
        messages.success(request, "Повернення підтверджено - книга на вашій полиці.")
    else:
        messages.error(request, err or "Помилка.")
    return redirect("my_library")


@login_required
def browse_shelves(request):
    """
    Каталог чужих книг, доступних для запиту: не показуємо позичені у когось записи
    і даємо випадати лише власні (не позичені) книги для поля "обмін".
    """
    others = (
        Shelf.objects.exclude(user=request.user)
        .filter(borrowed_from__isnull=True)
        .select_related("user", "book")
        .order_by("-added_at")
    )
    my_owned_shelves = (
        request.user.shelf_entries.filter(borrowed_from__isnull=True)
        .select_related("book")
    )
    return render(
        request,
        "mainApp/browse_shelves.html",
        {"others": others, "my_owned_shelves": my_owned_shelves},
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
        if raw_offer.strip():
            try:
                oid = int(raw_offer)
            except (TypeError, ValueError):
                t = target_shelf.book.title
                preflight.append(f"«{t[:45]}»: некоректна книга для обміну.")
                continue
            offer_shelf = Shelf.objects.filter(pk=oid, user=request.user).first()
            if not offer_shelf:
                t = target_shelf.book.title
                preflight.append(
                    f"«{t[:45]}»: запропоновану книгу не знайдено на вашій полиці."
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
        .select_related("requester", "target_shelf__book", "offer_shelf__book")
    )
    pending_out = (
        BookExchangeRequest.objects.filter(
            status=BookExchangeRequest.Status.PENDING,
            requester=request.user,
        )
        .select_related("target_shelf__user", "target_shelf__book", "offer_shelf__book")
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
            "offer_shelf__book",
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
    req = BookExchangeRequest.objects.filter(
        pk=request_id, status=BookExchangeRequest.Status.PENDING
    ).first()
    had_offer = bool(req and req.offer_shelf_id)
    ok, err = accept_exchange_request(request_id, request.user)
    if ok:
        messages.success(
            request,
            "Обмін прийнято: полиці оновлено."
            if had_offer
            else "Запит прийнято: книгу видано в позику (повернення - з полиці позичальника).",
        )
    else:
        messages.error(request, err or "Помилка.")
    return redirect("exchange_requests")


@login_required
def exchange_reject(request, request_id):
    """Власник відмовляє у запиті - статус запиту rejected, полиці не змінюються."""
    if request.method != "POST":
        return redirect("exchange_requests")
    ok, err = reject_exchange_request(request_id, request.user)
    if ok:
        messages.success(request, "Запит відхилено.")
    else:
        messages.error(request, err or "Помилка.")
    return redirect("exchange_requests")


@login_required
def exchange_cancel(request, request_id):
    """Відправник запиту передумав - статус cancelled."""
    if request.method != "POST":
        return redirect("exchange_requests")
    ok, err = cancel_exchange_request(request_id, request.user)
    if ok:
        messages.success(request, "Запит скасовано.")
    else:
        messages.error(request, err or "Помилка.")
    return redirect("exchange_requests")


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

    return render(
        request,
        "mainApp/messages.html",
        {
            "form": form,
            "timeline": timeline,
            "partners": partners,
            "partner": partner,
        },
    )
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