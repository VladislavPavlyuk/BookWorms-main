"""
Сервіс обміну та позик книг (чиста логіка без HTTP).

Навіщо окремий файл: щоб правила "хто кому що може" були в одному місці,
а views лише викликали ці функції й показували повідомлення користувачу.
"""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef, QuerySet
from django.utils import timezone

from . import message_service
from . import ops_log
from .copy_events import log_copy_event
from .models import (
    Book,
    BookCopy,
    BookExchangeRequest,
    CopyEvent,
    CustomUser,
    LoanHandoff,
    Shelf,
)


def _loan_due_date():
    days = int(getattr(settings, "DEFAULT_LOAN_DAYS", 14))
    return timezone.now().date() + timedelta(days=days)


def active_handoff_for_copy(copy_id: int | None) -> LoanHandoff | None:
    if not copy_id:
        return None
    try:
        return (
            LoanHandoff.objects.filter(
                copy_id=copy_id,
                status__in=(
                    LoanHandoff.Status.AWAITING_GIVE,
                    LoanHandoff.Status.AWAITING_RECEIVE,
                ),
            )
            .select_related("owner", "from_user", "to_user", "copy__book", "exchange_request")
            .first()
        )
    except Exception:
        # Таблиця ще не заmigрена / тимчасова помилка БД — не валимо confirm/accept.
        return None


def handoffs_involving(*user_ids: int) -> list[LoanHandoff]:
    """
    Активні handoff для панелі в чаті.
    Якщо передано ≥2 id — лише ті, де *всі* ці юзери серед owner/from/to.
    """
    from django.db.models import Q

    ids = [i for i in user_ids if i]
    if not ids:
        return []
    try:
        qs = (
            LoanHandoff.objects.filter(
                status__in=(
                    LoanHandoff.Status.AWAITING_GIVE,
                    LoanHandoff.Status.AWAITING_RECEIVE,
                )
            )
            .filter(Q(owner_id__in=ids) | Q(from_user_id__in=ids) | Q(to_user_id__in=ids))
            .select_related(
                "owner",
                "from_user",
                "to_user",
                "copy__book",
                "exchange_request",
                "from_shelf",
            )
            .order_by("-created_at")
        )
        rows = list(qs)
    except Exception:
        return []
    if len(ids) >= 2:
        need = set(ids)
        rows = [
            h
            for h in rows
            if need.issubset({h.owner_id, h.from_user_id, h.to_user_id})
        ]
    return rows


def add_owned_copy(user: CustomUser, book: Book) -> Shelf:
    """
    Новий фізичний примірник на полиці власника.
    Той самий ISBN можна додавати багато разів (окремі BookCopy).
    """
    copy = BookCopy.objects.create(book=book, owner=user)
    shelf = Shelf.objects.create(user=user, book=book, copy=copy)
    log_copy_event(
        copy,
        CopyEvent.Code.ADDED,
        actor=user,
        holder=user,
        legal_owner=user,
    )
    return shelf


def remove_owned_shelf(shelf: Shelf) -> None:
    """Прибрати власний рядок. BookCopy лишається — історія подій примірника."""
    copy = shelf.copy
    user = shelf.user
    log_copy_event(
        copy,
        CopyEvent.Code.REMOVED,
        actor=user,
        holder=user,
        legal_owner=copy.owner if copy else user,
        previous_holder=user,
    )
    shelf.delete()


def ensure_shelf_copy(shelf: Shelf) -> Shelf:
    """Якщо рядок полиці без BookCopy (старі дані) — створити примірник і прив’язати."""
    if shelf.copy_id:
        return shelf
    owner_id = shelf.borrowed_from_id or shelf.user_id
    copy = BookCopy.objects.create(book_id=shelf.book_id, owner_id=owner_id)
    Shelf.objects.filter(pk=shelf.pk).update(copy_id=copy.pk)
    shelf.copy_id = copy.pk
    shelf.copy = copy
    return shelf


def ensure_shelves_have_copies(shelves: list[Shelf]) -> list[Shelf]:
    return [ensure_shelf_copy(s) for s in shelves]


def is_copy_lent_out(copy_id: int | None) -> bool:
    """Чи є активна позика цього примірника."""
    if not copy_id:
        return False
    return Shelf.objects.filter(
        copy_id=copy_id,
        borrowed_from__isnull=False,
    ).exists()


def is_book_lent_out(owner_id: int, book_id: int) -> bool:
    """
    Legacy: чи є активна позика будь-якого примірника цієї ISBN від власника.
    Для UI «книга у від'їзді» на рівні ISBN; для блокування дій — краще is_copy_lent_out.
    """
    return Shelf.objects.filter(
        borrowed_from_id=owner_id,
        book_id=book_id,
    ).exists()


def available_owned_shelves_qs(exclude_user_id: int | None = None) -> QuerySet[Shelf]:
    """
    Полиці для *обміну* (своя книга в пропозиції) або «вільні» для миттєвої позики:
    власні (не borrowed), і цей примірник зараз не в позиці.
    """
    active_loan = Shelf.objects.filter(
        copy_id=OuterRef("copy_id"),
        borrowed_from__isnull=False,
    ).exclude(copy_id__isnull=True)
    qs = Shelf.objects.filter(borrowed_from__isnull=True).exclude(Exists(active_loan))
    if exclude_user_id is not None:
        qs = qs.exclude(user_id=exclude_user_id)
    return qs


def physical_presence_shelves_qs(exclude_user_id: int | None = None) -> QuerySet[Shelf]:
    """
    Полиці, де примірник *фізично* зараз:
    - власний рядок, якщо копія не в позиці;
    - рядок позичальника, якщо копія видана.

    Власний рядок під час активної позики сюди НЕ входить — книга на полиці позичальника.
    """
    active_loan = Shelf.objects.filter(
        copy_id=OuterRef("copy_id"),
        borrowed_from__isnull=False,
    ).exclude(copy_id__isnull=True)
    at_owner = Shelf.objects.filter(borrowed_from__isnull=True).exclude(Exists(active_loan))
    at_borrower = Shelf.objects.filter(borrowed_from__isnull=False)
    qs = (at_owner | at_borrower).distinct()
    if exclude_user_id is not None:
        qs = qs.exclude(user_id=exclude_user_id)
    return qs


def attach_loan_info(shelves: list[Shelf]) -> list[Shelf]:
    """Проставляє is_lent_out + loan_row на власні рядки (для внутрішньої логіки / pending)."""
    copy_ids = [s.copy_id for s in shelves if s.copy_id and not s.borrowed_from_id]
    loan_by_copy: dict[int, Shelf] = {}
    if copy_ids:
        for row in (
            Shelf.objects.filter(copy_id__in=copy_ids, borrowed_from__isnull=False)
            .select_related("user", "book", "copy", "borrowed_from")
        ):
            loan_by_copy[row.copy_id] = row
    today = timezone.now().date()
    for s in shelves:
        if s.borrowed_from_id:
            s.is_lent_out = False
            s.loan_row = None
            s.request_shelf_id = None  # потрібен рядок власника — див. attach_request_targets
            if s.due_date:
                s.is_overdue = s.due_date < today
                s.days_left = (s.due_date - today).days
            else:
                s.is_overdue = False
                s.days_left = None
            continue
        loan = loan_by_copy.get(s.copy_id) if s.copy_id else None
        s.loan_row = loan
        s.is_lent_out = loan is not None
        s.request_shelf_id = s.pk
        if loan and loan.due_date:
            s._loan_due = loan.due_date
            s._loan_overdue = loan.due_date < today
            s._loan_days_left = (loan.due_date - today).days
        else:
            s._loan_due = None
            s._loan_overdue = False
            s._loan_days_left = None
    return shelves


def attach_request_targets(shelves: list[Shelf]) -> list[Shelf]:
    """
    Для рядків позичальника — id полиці власника (куди слати запит на передачу).
    Для вільних власних — сам рядок.
    """
    need = [s.copy_id for s in shelves if s.borrowed_from_id and s.copy_id]
    owner_by_copy: dict[int, int] = {}
    if need:
        for row in Shelf.objects.filter(
            copy_id__in=need, borrowed_from__isnull=True
        ).only("id", "copy_id"):
            if row.copy_id:
                owner_by_copy[row.copy_id] = row.id
    for s in shelves:
        if s.borrowed_from_id:
            s.request_shelf_id = owner_by_copy.get(s.copy_id)
        else:
            s.request_shelf_id = s.pk
    return shelves


def filter_physically_present(shelves: list[Shelf]) -> list[Shelf]:
    """Прибрати з відображення власні рядки, чиї примірники зараз у когось у позиці."""
    shelves = attach_loan_info(shelves)
    return [s for s in shelves if not getattr(s, "is_lent_out", False)]


# Back-compat alias (каталог тепер = фізична наявність)
def browsable_owned_shelves_qs(exclude_user_id: int | None = None) -> QuerySet[Shelf]:
    return physical_presence_shelves_qs(exclude_user_id=exclude_user_id)


def group_shelves_by_book(shelves) -> list[dict]:
    """
    Один ISBN → одна картка: book + унікальні owners + усі доступні shelf-рядки (примірники).
    Порядок = перша поява книги в queryset.
    """
    groups: dict[int, dict] = {}
    order: list[int] = []
    for s in shelves:
        bid = s.book_id
        if bid not in groups:
            groups[bid] = {
                "book": s.book,
                "shelves": [],
                "owners": [],
                "_owner_ids": set(),
            }
            order.append(bid)
        g = groups[bid]
        g["shelves"].append(s)
        legal = s.borrowed_from if s.borrowed_from_id else s.user
        if legal.id not in g["_owner_ids"]:
            g["_owner_ids"].add(legal.id)
            g["owners"].append(legal)
    out = []
    for bid in order:
        g = groups[bid]
        out.append(
            {
                "book": g["book"],
                "shelves": g["shelves"],
                "owners": g["owners"],
            }
        )
    return out


def get_or_create_book_from_payload(payload: dict) -> tuple[Book, bool]:
    """
    Створює запис Book у БД з відповіді ISBN-провайдера
    (OL / ISBNdb / Google Books / LibraryThing) або повертає вже існуючий за ISBN.
    Якщо рядок уже є — sync: заповнює порожні поля з payload (не затирає
    заповнені title/authors вручну, окрім порожніх cover/info_url).
    """
    isbn = (payload.get("isbn") or "").strip()
    defaults = {
        "title": (payload.get("title") or "").strip()[:500],
        "authors": (payload.get("authors") or "").strip()[:500],
        "publisher": (payload.get("publisher") or "").strip()[:300],
        "publish_date": (payload.get("publish_date") or "").strip()[:64],
        "cover_url": (payload.get("cover_url") or "").strip()[:500],
        "info_url": (payload.get("info_url") or "").strip()[:500],
    }
    book, created = Book.objects.get_or_create(isbn=isbn, defaults=defaults)
    if not created:
        sync_book_from_payload(book, payload)
    return book, created


def sync_book_from_payload(book: Book, payload: dict) -> Book:
    """
    Оновлює існуючий Book з каталожного payload:
    - порожні текстові поля ← з payload
    - cover_url / info_url ← якщо в БД порожньо, а в payload є
    """
    changed_fields: list[str] = []
    mapping = (
        ("title", 500),
        ("authors", 500),
        ("publisher", 300),
        ("publish_date", 64),
        ("cover_url", 500),
        ("info_url", 500),
    )
    for field, maxlen in mapping:
        new = (payload.get(field) or "").strip()[:maxlen]
        if not new:
            continue
        old = (getattr(book, field) or "").strip()
        if not old:
            setattr(book, field, new)
            changed_fields.append(field)
    if changed_fields:
        book.save(update_fields=changed_fields)
    return book


def resolve_and_sync_book_by_isbn(raw_isbn: str) -> tuple[Book | None, str | None]:
    """
    1) Нормалізує ISBN.
    2) Шукає локальний Book (isbn10/13 candidates).
    3) Тягне метадані з провайдерів (ISBNdb у ланцюгу якщо є ключ).
    4) Якщо локальний є + payload — sync порожніх полів; інакше create.
    5) Якщо провайдери впали, але локальний Book є — повертає його.
    """
    from .book_lookup import fetch_book_by_isbn, isbn_candidates, normalize_isbn

    norm = normalize_isbn(raw_isbn)
    if not norm:
        return None, "Невірний ISBN: потрібно 10 символів (останній може бути X) або 13 цифр."

    candidates = isbn_candidates(norm)
    existing = Book.objects.filter(isbn__in=candidates).first()

    payload, err = fetch_book_by_isbn(norm)

    if payload:
        # якщо локальний під іншим ISBN-кандидатом — sync той рядок,
        # інакше get_or_create за preferred isbn з payload
        if existing and existing.isbn != payload.get("isbn"):
            sync_book_from_payload(existing, payload)
            return existing, None
        book, _ = get_or_create_book_from_payload(payload)
        return book, None

    if existing:
        return existing, None

    return None, err or "Книгу з таким ISBN не знайдено."


def create_exchange_request(
    requester: CustomUser,
    target_shelf: Shelf,
    offer_shelf: Shelf | None = None,
    *,
    from_queue: bool = False,
    join_queue_if_busy: bool = True,
) -> tuple[BookExchangeRequest | None, str | None]:
    """
    Створює запит. Помилка - (None, текст).
    Без offer_shelf: після прийняття - позика (borrowed_from = власник).
    З offer_shelf: обмін двома примірниками (повна передача, без позики).

    Якщо примірник уже в позиці і це запит на позику — створюємо запит на
    *передачу третій особі* (власник може прийняти) і ставимо в чергу.
    """
    from . import queue_service

    if target_shelf.user_id == requester.id:
        return None, "Не можна запитувати власну книгу."

    if target_shelf.borrowed_from_id:
        return None, "Неможливо запитувати позичену в іншого користувача книгу."

    lent = is_copy_lent_out(target_shelf.copy_id)

    if lent and offer_shelf is not None:
        return None, "Неможливо обміняти примірник, який зараз у позиці."

    if lent and active_handoff_for_copy(target_shelf.copy_id):
        return None, "Для цього примірника вже схвалено передачу — дочекайтесь фізичної передачі."

    if offer_shelf is not None:
        if offer_shelf.user_id != requester.id:
            return None, "Запропонована книга має бути з вашої полиці."
        if offer_shelf.borrowed_from_id:
            return None, "Неможна віддавати в обмін позичену книгу - спочатку поверніть її власнику."
        if is_copy_lent_out(offer_shelf.copy_id):
            return None, "Неможна віддавати в обмін книгу, яка зараз у когось у позиці."
        if offer_shelf.copy_id == target_shelf.copy_id:
            return None, "Немає сенсу обмінювати той самий примірник."

    pending = BookExchangeRequest.Status.PENDING
    if BookExchangeRequest.objects.filter(
        target_shelf=target_shelf,
        requester=requester,
        status=pending,
    ).exists():
        return None, "Ви вже маєте активний запит щодо цієї книги."

    # Той самий примірник уже на полиці (не блокуємо інший ISBN-клон).
    if Shelf.objects.filter(user=requester, copy_id=target_shelf.copy_id).exists():
        return None, "Цей примірник вже є у вас на полиці."

    req = BookExchangeRequest.objects.create(
        target_shelf=target_shelf,
        shelf_owner=target_shelf.user,
        requester=requester,
        offer_shelf=offer_shelf,
        status=pending,
    )

    if not from_queue:
        if lent and offer_shelf is None:
            message_service.notify_transmission_request_created(req)
        else:
            message_service.notify_exchange_request_created(req)

    if lent and offer_shelf is None:
        if join_queue_if_busy and target_shelf.copy_id:
            queue_service.join_queue(
                requester,
                target_shelf.copy,
                notify=not from_queue,
                exchange_request=req,
            )
    elif (
        join_queue_if_busy
        and offer_shelf is None
        and target_shelf.copy_id
        and not from_queue
    ):
        # Кілька охочих на вільний примірник — теж ставимо в чергу (крім першого запиту).
        other_pending = (
            BookExchangeRequest.objects.filter(
                target_shelf__copy_id=target_shelf.copy_id,
                status=pending,
                offer_shelf__isnull=True,
            )
            .exclude(pk=req.pk)
            .exists()
        )
        if other_pending:
            queue_service.join_queue(
                requester, target_shelf.copy, notify=True, exchange_request=req
            )

    return req, None


def create_many_exchange_requests(
    requester: CustomUser,
    lines: list[tuple[Shelf, Shelf | None]],
) -> tuple[int, list[str]]:
    """
    Кілька запитів за одну дію (позика або обмін на рядок).
    Та сама пропозиція (offer_shelf) не може зустрічатись двічі в одному пакеті.
    """
    ok = 0
    errs: list[str] = []

    def short_title(s: Shelf) -> str:
        t = s.book.title
        return (t[:52] + "…") if len(t) > 55 else t

    seen_offer_ids: set[int] = set()
    filtered: list[tuple[Shelf, Shelf | None]] = []
    for target_shelf, offer_shelf in lines:
        label = short_title(target_shelf)
        if offer_shelf is not None:
            oid = offer_shelf.pk
            if oid in seen_offer_ids:
                errs.append(f'"{label}": цю свою книгу вже обрано для іншого рядка в цьому пакеті.')
                continue
            seen_offer_ids.add(oid)
        filtered.append((target_shelf, offer_shelf))

    for target_shelf, offer_shelf in filtered:
        label = short_title(target_shelf)
        req, err = create_exchange_request(requester, target_shelf, offer_shelf)
        if err:
            errs.append(f"'{label}': {err}")
        else:
            ok += 1
    return ok, errs


@transaction.atomic
def accept_exchange_request(request_id: int, acting_user: CustomUser) -> tuple[bool, str | None]:
    """
    Власник погоджується.
    Позика: власник ЗБЕРІГАЄ свій рядок Shelf; позичальнику створюється окремий рядок
    з borrowed_from на той самий BookCopy.
    Обмін: обидва рядки міняють user_id і owner на BookCopy (повна передача).

    Якщо примірник уже в позиці — *передача третій особі*: знімаємо з поточного
    позичальника і видаємо запитувачу (лише для позики, не обміну).
    """
    from . import queue_service

    try:
        req = BookExchangeRequest.objects.select_for_update().get(
            pk=request_id,
            status=BookExchangeRequest.Status.PENDING,
        )
    except BookExchangeRequest.DoesNotExist:
        return False, "Запит не знайдено або вже оброблено."

    if req.shelf_owner_id != acting_user.id:
        return False, "Ви не власник цієї книги."

    target = (
        Shelf.objects.select_for_update(of=("self",))
        .filter(
            pk=req.target_shelf_id,
            user_id=req.shelf_owner_id,
        )
        .select_related("book", "copy")
        .first()
    )
    if not target:
        return False, "Книги вже немає на вашій полиці."
    if target.borrowed_from_id:
        return False, "Не можна віддати позичену книгу."

    requester = CustomUser.objects.select_for_update().get(pk=req.requester_id)

    offer = None
    if req.offer_shelf_id:
        offer = (
            Shelf.objects.select_for_update(of=("self",))
            .filter(pk=req.offer_shelf_id, user=requester)
            .select_related("book", "copy")
            .first()
        )
        if not offer:
            return False, "Запропонована книга більше не на полиці відправника."
        if offer.borrowed_from_id or is_copy_lent_out(offer.copy_id):
            return False, "Запропонована книга недоступна для обміну (позика)."

    if Shelf.objects.filter(user=requester, copy_id=target.copy_id).exists():
        return False, "У користувача вже є цей примірник - неможливо завершити обмін."

    # --- Передача третій особі: схвалення ≠ фізичний перенос ---
    if is_copy_lent_out(target.copy_id):
        if offer is not None:
            return False, "Неможливо обміняти примірник, який зараз у позиці."
        if active_handoff_for_copy(target.copy_id):
            return False, "Для цього примірника вже є активна фізична передача."
        ok, err = _approve_loan_handoff(req, acting_user, target, requester)
        if not ok:
            return False, err
        req.status = BookExchangeRequest.Status.ACCEPTED
        req.resolved_at = timezone.now()
        req.save(update_fields=["status", "resolved_at"])
        return True, None

    if offer:
        if (
            Shelf.objects.filter(user=acting_user, copy_id=offer.copy_id)
            .exclude(pk=offer.pk)
            .exists()
        ):
            return False, "У вас уже є запропонований до обміну примірник."
        prev_target_owner = acting_user
        prev_offer_owner = requester
        Shelf.objects.filter(pk=target.pk).update(
            user_id=requester.id,
            borrowed_from_id=None,
            due_date=None,
            return_pending=False,
        )
        Shelf.objects.filter(pk=offer.pk).update(
            user_id=acting_user.id,
            borrowed_from_id=None,
            due_date=None,
            return_pending=False,
        )
        BookCopy.objects.filter(pk=target.copy_id).update(owner_id=requester.id)
        BookCopy.objects.filter(pk=offer.copy_id).update(owner_id=acting_user.id)
        log_copy_event(
            target.copy_id,
            CopyEvent.Code.EXCHANGED,
            actor=acting_user,
            holder=requester,
            legal_owner=requester,
            previous_holder=prev_target_owner,
            previous_owner=prev_target_owner,
            counterparty=requester,
            exchange_request=req,
        )
        log_copy_event(
            offer.copy_id,
            CopyEvent.Code.EXCHANGED,
            actor=acting_user,
            holder=acting_user,
            legal_owner=acting_user,
            previous_holder=prev_offer_owner,
            previous_owner=prev_offer_owner,
            counterparty=acting_user,
            exchange_request=req,
        )
    else:
        Shelf.objects.create(
            user_id=requester.id,
            book_id=target.book_id,
            copy_id=target.copy_id,
            borrowed_from_id=acting_user.id,
            due_date=_loan_due_date(),
            return_pending=False,
        )
        log_copy_event(
            target.copy_id,
            CopyEvent.Code.LOANED,
            actor=acting_user,
            holder=requester,
            legal_owner=acting_user,
            previous_holder=acting_user,
            counterparty=requester,
            exchange_request=req,
        )
        queue_service.after_copy_loaned_or_transmitted(target.copy_id, requester.id)

    req.status = BookExchangeRequest.Status.ACCEPTED
    req.resolved_at = timezone.now()
    req.save(update_fields=["status", "resolved_at"])
    message_service.notify_exchange_request_accepted(req)
    return True, None


def _approve_loan_handoff(
    req: BookExchangeRequest,
    owner: CustomUser,
    owner_shelf: Shelf,
    requester: CustomUser,
) -> tuple[bool, str | None]:
    """
    Власник схвалив передачу: книга лишається у поточного позичальника,
    створюється LoanHandoff. Полиця переїде лише після confirm give + receive.
    """
    cid = ops_log.new_cid()
    ops_log.info(
        "handoff.approve.start",
        cid=cid,
        req_id=req.pk,
        owner_id=owner.id,
        requester_id=requester.id,
        owner_shelf_id=owner_shelf.pk,
        copy_id=owner_shelf.copy_id,
    )
    borrower_shelf = (
        Shelf.objects.select_for_update(of=("self",))
        .filter(copy_id=owner_shelf.copy_id, borrowed_from__isnull=False)
        .select_related("user", "book")
        .first()
    )
    if not borrower_shelf:
        ops_log.warning("handoff.approve.no_loan", cid=cid, copy_id=owner_shelf.copy_id)
        return False, "Активну позику не знайдено — спробуйте ще раз."

    previous_holder = borrower_shelf.user
    if previous_holder.id == requester.id:
        return False, "Цей користувач уже тримає примірник."
    if borrower_shelf.return_pending:
        return False, "Спочатку завершіть повернення від поточного позичальника."

    copy_id = owner_shelf.copy_id
    handoff = LoanHandoff.objects.create(
        copy_id=copy_id,
        owner_id=owner.id,
        from_user_id=previous_holder.id,
        to_user_id=requester.id,
        exchange_request=req,
        from_shelf=borrower_shelf,
        status=LoanHandoff.Status.AWAITING_GIVE,
    )
    log_copy_event(
        copy_id,
        CopyEvent.Code.HANDOFF_APPROVED,
        actor=owner,
        holder=previous_holder,
        legal_owner=owner,
        previous_holder=previous_holder,
        counterparty=requester,
        exchange_request=req,
    )
    message_service.notify_handoff_approved(handoff)
    ops_log.info(
        "handoff.approve.ok",
        cid=cid,
        **ops_log.handoff_snapshot(handoff),
    )
    return True, None


def _complete_loan_handoff_transfer(handoff: LoanHandoff) -> tuple[bool, str | None]:
    """Зняти позику з from_user і видати to_user (після обох підтверджень)."""
    from . import queue_service

    cid = ops_log.new_cid()
    ops_log.info("handoff.complete.start", cid=cid, **ops_log.handoff_snapshot(handoff))

    owner = handoff.owner
    requester = handoff.to_user
    previous_holder = handoff.from_user
    copy_id = handoff.copy_id
    req = handoff.exchange_request

    borrower_shelf = (
        Shelf.objects.select_for_update(of=("self",))
        .filter(copy_id=copy_id, borrowed_from__isnull=False, user_id=previous_holder.id)
        .select_related("user", "book")
        .first()
    )
    if not borrower_shelf:
        ops_log.warning(
            "handoff.complete.no_shelf",
            cid=cid,
            copy_id=copy_id,
            from_user_id=previous_holder.id,
        )
        return False, "Позику вже знято — передачу не завершено."

    book_title = borrower_shelf.book.title
    book_id = borrower_shelf.book_id
    borrower_shelf.delete()
    Shelf.objects.create(
        user_id=requester.id,
        book_id=book_id,
        copy_id=copy_id,
        borrowed_from_id=owner.id,
        due_date=_loan_due_date(),
        return_pending=False,
    )
    handoff.status = LoanHandoff.Status.COMPLETED
    handoff.resolved_at = timezone.now()
    handoff.from_shelf = None
    handoff.save(update_fields=["status", "resolved_at", "from_shelf"])
    log_copy_event(
        copy_id,
        CopyEvent.Code.TRANSMITTED,
        actor=owner,
        holder=requester,
        legal_owner=owner,
        previous_holder=previous_holder,
        counterparty=requester,
        exchange_request=req,
    )
    message_service.notify_loan_transmitted(
        owner, previous_holder, requester, book_title, exchange_request=req
    )
    try:
        queue_service.after_copy_loaned_or_transmitted(copy_id, requester.id)
    except Exception as exc:
        ops_log.exception("handoff.complete.queue_fail", exc, cid=cid, copy_id=copy_id)
    ops_log.info("handoff.complete.ok", cid=cid, **ops_log.handoff_snapshot(handoff))
    return True, None


@transaction.atomic
def confirm_handoff_give(
    handoff_id: int, acting_user: CustomUser
) -> tuple[bool, str | None]:
    """Поточний позичальник підтверджує, що фізично віддав книгу наступному."""
    cid = ops_log.new_cid()
    ops_log.info(
        "handoff.give.start",
        cid=cid,
        handoff_id=handoff_id,
        actor_id=acting_user.id,
    )
    try:
        # of=("self",) — Postgres: FOR UPDATE + LEFT JOIN на nullable FK інакше 500
        handoff = (
            LoanHandoff.objects.select_for_update(of=("self",))
            .select_related(
                "owner", "from_user", "to_user", "copy__book", "exchange_request"
            )
            .get(pk=handoff_id)
        )
    except LoanHandoff.DoesNotExist:
        ops_log.warning("handoff.give.missing", cid=cid, handoff_id=handoff_id)
        return False, "Передачу не знайдено."
    except Exception as exc:
        ops_log.exception(
            "handoff.give.lock_fail",
            exc,
            cid=cid,
            handoff_id=handoff_id,
            actor_id=acting_user.id,
        )
        return False, f"Помилка блокування передачі (cid={cid})."

    ops_log.info("handoff.give.locked", cid=cid, **ops_log.handoff_snapshot(handoff))

    if handoff.status != LoanHandoff.Status.AWAITING_GIVE:
        ops_log.warning(
            "handoff.give.bad_status",
            cid=cid,
            status=handoff.status,
            actor_id=acting_user.id,
        )
        return False, "Зараз не чекається підтвердження віддачі."
    if acting_user.id != handoff.from_user_id:
        ops_log.warning(
            "handoff.give.forbidden",
            cid=cid,
            actor_id=acting_user.id,
            from_user_id=handoff.from_user_id,
        )
        return False, "Підтвердити віддачу може лише поточний тримач книги."

    try:
        handoff.status = LoanHandoff.Status.AWAITING_RECEIVE
        handoff.giver_confirmed_at = timezone.now()
        handoff.save(update_fields=["status", "giver_confirmed_at"])
        log_copy_event(
            handoff.copy_id,
            CopyEvent.Code.HANDOFF_GIVEN,
            actor=acting_user,
            holder=acting_user,
            legal_owner=handoff.owner,
            previous_holder=acting_user,
            counterparty=handoff.to_user,
            exchange_request=handoff.exchange_request,
        )
        message_service.notify_handoff_given(handoff)
    except Exception as exc:
        ops_log.exception(
            "handoff.give.save_fail",
            exc,
            cid=cid,
            **ops_log.handoff_snapshot(handoff),
        )
        raise

    ops_log.info("handoff.give.ok", cid=cid, **ops_log.handoff_snapshot(handoff))
    return True, None


@transaction.atomic
def confirm_handoff_receive(
    handoff_id: int, acting_user: CustomUser
) -> tuple[bool, str | None]:
    """Наступний позичальник підтверджує отримання — полиця переїздить, попередній виходить з чату."""
    cid = ops_log.new_cid()
    ops_log.info(
        "handoff.receive.start",
        cid=cid,
        handoff_id=handoff_id,
        actor_id=acting_user.id,
    )
    try:
        handoff = (
            LoanHandoff.objects.select_for_update(of=("self",))
            .select_related(
                "owner", "from_user", "to_user", "copy__book", "exchange_request"
            )
            .get(pk=handoff_id)
        )
    except LoanHandoff.DoesNotExist:
        ops_log.warning("handoff.receive.missing", cid=cid, handoff_id=handoff_id)
        return False, "Передачу не знайдено."
    except Exception as exc:
        ops_log.exception(
            "handoff.receive.lock_fail",
            exc,
            cid=cid,
            handoff_id=handoff_id,
            actor_id=acting_user.id,
        )
        return False, f"Помилка блокування передачі (cid={cid})."

    if handoff.status != LoanHandoff.Status.AWAITING_RECEIVE:
        if handoff.status == LoanHandoff.Status.AWAITING_GIVE:
            ops_log.warning("handoff.receive.need_give_first", cid=cid)
            return False, "Спочатку поточний тримач має підтвердити віддачу."
        ops_log.warning(
            "handoff.receive.bad_status", cid=cid, status=handoff.status
        )
        return False, "Зараз не чекається підтвердження отримання."
    if acting_user.id != handoff.to_user_id:
        ops_log.warning(
            "handoff.receive.forbidden",
            cid=cid,
            actor_id=acting_user.id,
            to_user_id=handoff.to_user_id,
        )
        return False, "Підтвердити отримання може лише наступний позичальник."

    try:
        handoff.receiver_confirmed_at = timezone.now()
        handoff.save(update_fields=["receiver_confirmed_at"])
        ok, err = _complete_loan_handoff_transfer(handoff)
        if not ok:
            ops_log.warning("handoff.receive.complete_fail", cid=cid, err=err)
        else:
            ops_log.info("handoff.receive.ok", cid=cid, handoff_id=handoff_id)
        return ok, err
    except Exception as exc:
        ops_log.exception(
            "handoff.receive.fail",
            exc,
            cid=cid,
            **ops_log.handoff_snapshot(handoff),
        )
        raise


@transaction.atomic
def cancel_loan_handoff(
    handoff_id: int, acting_user: CustomUser
) -> tuple[bool, str | None]:
    """Власник скасовує схвалену, але ще не завершену фізичну передачу."""
    cid = ops_log.new_cid()
    try:
        handoff = (
            LoanHandoff.objects.select_for_update(of=("self",))
            .select_related(
                "owner", "from_user", "to_user", "copy__book", "exchange_request"
            )
            .get(pk=handoff_id)
        )
    except LoanHandoff.DoesNotExist:
        return False, "Передачу не знайдено."
    except Exception as exc:
        ops_log.exception(
            "handoff.cancel.lock_fail", exc, cid=cid, handoff_id=handoff_id
        )
        return False, f"Помилка блокування передачі (cid={cid})."

    if handoff.status not in (
        LoanHandoff.Status.AWAITING_GIVE,
        LoanHandoff.Status.AWAITING_RECEIVE,
    ):
        return False, "Цю передачу вже завершено або скасовано."
    if acting_user.id != handoff.owner_id:
        return False, "Скасувати може лише власник примірника."

    handoff.status = LoanHandoff.Status.CANCELLED
    handoff.resolved_at = timezone.now()
    handoff.save(update_fields=["status", "resolved_at"])
    message_service.notify_handoff_cancelled(handoff)
    ops_log.info("handoff.cancel.ok", cid=cid, **ops_log.handoff_snapshot(handoff))
    return True, None


def _transmit_loan_to_requester(
    req: BookExchangeRequest,
    owner: CustomUser,
    owner_shelf: Shelf,
    requester: CustomUser,
) -> tuple[bool, str | None]:
    """Legacy alias — тепер схвалення створює handoff, не миттєвий перенос."""
    return _approve_loan_handoff(req, owner, owner_shelf, requester)


def reject_exchange_request(request_id: int, acting_user: CustomUser) -> tuple[bool, str | None]:
    try:
        req = BookExchangeRequest.objects.get(
            pk=request_id,
            status=BookExchangeRequest.Status.PENDING,
        )
    except BookExchangeRequest.DoesNotExist:
        return False, "Запит не знайдено."

    if req.shelf_owner_id != acting_user.id:
        return False, "Ви не власник цієї книги."

    req.status = BookExchangeRequest.Status.REJECTED
    req.resolved_at = timezone.now()
    req.save(update_fields=["status", "resolved_at"])
    message_service.notify_exchange_request_rejected(req)
    return True, None


def cancel_exchange_request(request_id: int, acting_user: CustomUser) -> tuple[bool, str | None]:
    """Той, хто надсилав запит, передумав - скасування до відповіді власника."""
    from . import queue_service

    try:
        req = BookExchangeRequest.objects.get(
            pk=request_id,
            status=BookExchangeRequest.Status.PENDING,
        )
    except BookExchangeRequest.DoesNotExist:
        return False, "Запит не знайдено."

    if req.requester_id != acting_user.id:
        return False, "Скасувати може лише той, хто надіслав запит."

    copy_id = req.target_shelf.copy_id
    req.status = BookExchangeRequest.Status.CANCELLED
    req.resolved_at = timezone.now()
    req.save(update_fields=["status", "resolved_at"])
    message_service.notify_exchange_request_cancelled(req)
    if copy_id:
        queue_service.leave_queue(acting_user, copy_id)
    return True, None


@transaction.atomic
def request_borrow_return(shelf_id: int, borrower: CustomUser) -> tuple[bool, str | None]:
    """
    Позичальник повідомляє, що повертає книгу. Рядок лишається на його полиці до підтвердження позикодавцем.
    """
    shelf = (
        Shelf.objects.select_for_update(of=("self",))
        .select_related("borrowed_from", "book", "copy")
        .filter(pk=shelf_id, user=borrower)
        .first()
    )
    if not shelf:
        return False, "Запис на полиці не знайдено."
    if not shelf.borrowed_from_id:
        return False, "Ця книга не позичена - її можна просто прибрати з полиці."
    if shelf.return_pending:
        return False, "Повернення вже очікує підтвердження позикодавця."
    if active_handoff_for_copy(shelf.copy_id):
        ops_log.warning(
            "return.blocked_by_handoff",
            shelf_id=shelf_id,
            user_id=borrower.id,
            copy_id=shelf.copy_id,
        )
        return (
            False,
            "Для цього примірника схвалено передачу наступному читачу. "
            "Не «Повернути власнику», а в чаті натисніть «Я віддав книгу».",
        )

    Shelf.objects.filter(pk=shelf.pk).update(return_pending=True)
    shelf.return_pending = True
    log_copy_event(
        shelf.copy_id,
        CopyEvent.Code.RETURN_REQUESTED,
        actor=borrower,
        holder=borrower,
        legal_owner=shelf.borrowed_from,
        counterparty=shelf.borrowed_from,
    )
    message_service.notify_borrow_return_requested(shelf)
    return True, None


@transaction.atomic
def confirm_borrow_return(shelf_id: int, lender: CustomUser) -> tuple[bool, str | None]:
    """
    Позикодавець підтверджує отримання: видаляємо рядок позичальника.
    Рядок власника вже має бути на його полиці (після фіксу позики); якщо ні — відновлюємо.
    """
    shelf = (
        Shelf.objects.select_for_update(of=("self",))
        .select_related("book", "user", "copy")
        .filter(
            pk=shelf_id,
            borrowed_from=lender,
            return_pending=True,
        )
        .first()
    )
    if not shelf:
        return False, "Немає запису з очікуванням вашого підтвердження повернення."
    if active_handoff_for_copy(shelf.copy_id):
        return False, "Спочатку скасуйте активну фізичну передачу цього примірника."

    owner_id = lender.id
    copy_id = shelf.copy_id
    borrower = shelf.user
    book_title = shelf.book.title
    shelf_pk = shelf.pk

    message_service.mark_return_notifications_read(
        lender,
        shelf_id=shelf_pk,
        borrower_id=borrower.id,
        book_title=book_title,
    )

    owner_row = (
        Shelf.objects.select_for_update(of=("self",))
        .filter(user_id=owner_id, copy_id=copy_id, borrowed_from__isnull=True)
        .first()
    )
    if not owner_row:
        Shelf.objects.filter(pk=shelf.pk).update(
            user_id=owner_id,
            borrowed_from_id=None,
            return_pending=False,
            due_date=None,
        )
        if copy_id:
            BookCopy.objects.filter(pk=copy_id).update(owner_id=owner_id)
    else:
        shelf.delete()

    log_copy_event(
        copy_id,
        CopyEvent.Code.RETURNED,
        actor=lender,
        holder=lender,
        legal_owner=lender,
        previous_holder=borrower,
        counterparty=borrower,
    )
    message_service.notify_borrow_return_confirmed(lender, borrower, book_title)

    if copy_id:
        try:
            from . import queue_service

            queue_service.offer_next_after_return(copy_id, lender)
        except Exception:
            # Черга не повинна валити підтвердження повернення
            pass
    return True, None
