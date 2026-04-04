from django.contrib import messages
from django.contrib.auth import login, get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
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
from .exchange_service import (
    accept_exchange_request,
    cancel_exchange_request,
    create_exchange_request,
    get_or_create_book_from_payload,
    reject_exchange_request,
    return_borrowed_book,
)
from django.core.mail import send_mail

from .tokens import account_activation_token


def home(request):
    posts = Post.objects.all().order_by('-created_ad')
    return render(request, 'mainApp/index.html', {'posts': posts})


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
        subject = "Подтверждение регистрации BookWorms"
        message = f"Здравствуйте, {user.username}!\nДля активации аккаунта перейдите по ссылке: {activation_url}"

        html_message = f"""
            <div style="font-family: Arial, sans-serif; border: 1px solid #ddd; padding: 20px;">
                <h2 style="color: #2c3e50;">Добро пожаловать в BookWorms!</h2>
                <p>Вы успешно зарегистрировались. Остался последний шаг — подтвердить почту.</p>
                <a href="{activation_url}" 
                   style="display: inline-block; padding: 10px 20px; background-color: #4CAF50; color: white; text-decoration: none; border-radius: 5px;">
                   Активировать мой аккаунт
                </a>
                <p style="margin-top: 20px; font-size: 12px; color: #777;">
                    Если вы не регистрировались на нашем сайте, просто проигнорируйте это письмо.
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
                fail_silently=False,  # Важно: увидим ошибку, если SMTP не настроен
            )
        except Exception as e:
            # Если почта не ушла (например, неверный пароль в Mailtrap)
            user.delete()  # Удаляем "зависшего" юзера
            form.add_error(None, f"Ошибка отправки письма: {e}. Проверьте настройки SMTP.")
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
        # Чтобы токен не "протух" при первом же входе,
        # сначала сохраняем активацию, а потом логиним
        user.save()
        login(request, user)
        return render(request, 'mainApp/activation_success.html')
    else:
        # Если не прошел проверку, загляни в админку.
        # Если юзер уже Active=True, значит ты просто нажал ссылку второй раз.
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
    return render(
        request,
        "mainApp/library.html",
        {"form": form, "shelves": shelves},
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
    ok, err = return_borrowed_book(shelf_id, request.user)
    if ok:
        messages.success(request, "Книгу повернуто власнику.")
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
    """Приймає POST з форми на сторінці browse: id чужої полиці + опційно id своєї для обміну."""
    if request.method != "POST":
        return redirect("browse_shelves")
    try:
        target_id = int(request.POST.get("target_shelf_id", ""))
    except (TypeError, ValueError):
        messages.error(request, "Некоректний запит.")
        return redirect("browse_shelves")

    target_shelf = get_object_or_404(Shelf, pk=target_id)
    offer_shelf = None
    raw_offer = request.POST.get("offer_shelf_id") or ""
    if raw_offer.strip():
        try:
            oid = int(raw_offer)
            offer_shelf = get_object_or_404(Shelf, pk=oid, user=request.user)
        except (TypeError, ValueError):
            messages.error(request, "Некоректна книга для обміну.")
            return redirect("browse_shelves")

    req, err = create_exchange_request(request.user, target_shelf, offer_shelf)
    if err:
        messages.error(request, err)
    else:
        messages.success(request, "Запит надіслано.")
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