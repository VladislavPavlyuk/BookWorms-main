from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from .models import BookExchangeRequest, Post, PrivateMessage, Shelf
from django.contrib.auth.views import LoginView
from .forms import UserLoginForm, UserRegisterForm, AddIsbnForm, SendExchangePartnerMessageForm
from django.views.generic import CreateView
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from .forms import UserUpdateForm
from .openlibrary import fetch_book_by_isbn
# Бізнес-правила обміну/позик винесені в exchange_service - тут лише HTTP і шаблони.
from .message_service import (
    get_exchange_message_partners,
    mark_thread_read,
    send_user_message,
)
from .exchange_service import (
    accept_exchange_request,
    cancel_exchange_request,
    create_exchange_request,
    get_or_create_book_from_payload,
    reject_exchange_request,
    return_borrowed_book,
)

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
    success_url = reverse_lazy('home')

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response

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
def edit_profile(request):
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = UserUpdateForm(instance=request.user)

    return render(request, 'mainApp/profile_edit.html', {'form': form})


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