"""
Спільні бібліотеки: особиста → merge/split, підтвердження адміна, ISBN quantity.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from .exceptions import ExchangeError
from .models import (
    Book,
    BookCopy,
    CustomUser,
    Library,
    LibraryAction,
    LibraryAdminElection,
    LibraryAdminVote,
    LibraryInvite,
    LibraryMembership,
    PrivateMessage,
    Shelf,
)


class LibraryError(ExchangeError):
    """Помилка спільної бібліотеки."""


@dataclass
class IsbnConfirmNeeded:
    """Сигнал: ISBN уже є — потрібне підтвердження ще одного примірника."""

    isbn: str
    existing_count: int
    title: str


def ensure_personal_library(user: CustomUser) -> Library:
    """Особиста бібліотека: admin=user, єдиний учасник."""
    from .library_repo import get_library_repository

    repo = get_library_repository()
    mem = repo.find_membership_for_user(user.id)
    if mem:
        return mem.library
    return repo.create_personal_library(user)


def user_library(user: CustomUser) -> Library:
    return ensure_personal_library(user)


def is_library_admin(user: CustomUser, library: Library | None = None) -> bool:
    lib = library or user_library(user)
    return lib.admin_id == user.id


def library_isbn_counts(library: Library) -> dict[str, dict[str, Any]]:
    """isbn → {count, title, book_id} для примірників бібліотеки (не в чужій позиці? усі owned)."""
    from .library_repo import get_library_repository

    rows = get_library_repository().find_isbn_count_rows(library.id)
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        isbn = r["book__isbn"] or ""
        out[isbn] = {
            "isbn": isbn,
            "title": r["book__title"],
            "book_id": r["book_id"],
            "count": r["n"],
        }
    return out


def count_isbn_in_library(library: Library, book: Book) -> int:
    from .library_repo import get_library_repository

    return get_library_repository().count_isbn(library.id, book.id)

def merge_overlap_preview(target: Library, source: Library) -> list[dict[str, Any]]:
    """ISBN, що є в обох бібліотеках — треба вказати реальну кількість фізичних томів."""
    from .book_photos import is_local_isbn

    t = library_isbn_counts(target)
    s = library_isbn_counts(source)
    overlap = []
    for isbn, td in t.items():
        if not isbn or is_local_isbn(isbn):
            continue
        if isbn not in s:
            continue
        overlap.append(
            {
                "isbn": isbn,
                "title": td["title"],
                "book_id": td["book_id"],
                "target_count": td["count"],
                "source_count": s[isbn]["count"],
                "combined": td["count"] + s[isbn]["count"],
            }
        )
    return overlap


def list_my_library_shelves(user: CustomUser) -> list[Shelf]:
    """
    «Моя бібліотека» після merge: усі власні примірники спільної бібліотеки
    (Shelf будь-якого учасника з copy.library = lib) + позичені цим користувачем.

    Dedup by copy_id — якщо є рядок поточного user, беремо його.
    """
    lib = ensure_personal_library(user)
    ensure_library_copy_shelves(lib)

    related = (
        "book",
        "borrowed_from",
        "user",
        "copy",
        "book__price_evaluation",
    )
    prefetched = ("book__photos", "book__price_evaluation__quotes")

    owned_rows = list(
        Shelf.objects.filter(
            borrowed_from__isnull=True,
            copy__library=lib,
        )
        .select_related(*related)
        .prefetch_related(*prefetched)
        .order_by("-added_at")
    )
    by_copy: dict[int, Shelf] = {}
    orphan_mine: list[Shelf] = []
    for s in owned_rows:
        if not s.copy_id:
            if s.user_id == user.id:
                orphan_mine.append(s)
            continue
        prev = by_copy.get(s.copy_id)
        if prev is None or (s.user_id == user.id and prev.user_id != user.id):
            by_copy[s.copy_id] = s

    # Copies present in library but somehow without an owned shelf row
    missing_copy_ids = set(
        BookCopy.objects.filter(library=lib).values_list("id", flat=True)
    ) - set(by_copy.keys())
    if missing_copy_ids:
        ensure_library_copy_shelves(lib)
        for s in (
            Shelf.objects.filter(
                borrowed_from__isnull=True,
                copy_id__in=missing_copy_ids,
            )
            .select_related(*related)
            .prefetch_related(*prefetched)
        ):
            if s.copy_id and s.copy_id not in by_copy:
                by_copy[s.copy_id] = s

    borrowed = list(
        Shelf.objects.filter(user=user, borrowed_from__isnull=False)
        .select_related(*related)
        .prefetch_related(*prefetched)
        .order_by("-added_at")
    )
    owned = sorted(
        list(by_copy.values()) + orphan_mine,
        key=lambda x: x.added_at,
        reverse=True,
    )
    return owned + borrowed


def library_active_loans_by_copy(library: Library) -> dict[int, Shelf]:
    """copy_id → активна позика (рядок позичальника) для примірників бібліотеки."""
    from .library_repo import get_library_repository

    return get_library_repository().find_active_loans_by_copy(library.id)

def ensure_library_copy_shelves(library: Library) -> None:
    """Після merge: у кожного примірника без жодного shelf — створити owned-рядок."""
    for copy in BookCopy.objects.filter(library=library).only(
        "id", "book_id", "added_by_id"
    ):
        if Shelf.objects.filter(copy_id=copy.id).exists():
            continue
        holder_id = copy.added_by_id or library.admin_id
        Shelf.objects.create(
            user_id=holder_id,
            book_id=copy.book_id,
            copy_id=copy.id,
        )


def _notify(
    recipient: CustomUser,
    body: str,
    actor: CustomUser | None = None,
    *,
    library_invite: LibraryInvite | None = None,
    library_action: LibraryAction | None = None,
) -> PrivateMessage | None:
    try:
        from .message_service import _create_message

        sender = actor or recipient
        return _create_message(
            sender,
            recipient,
            body,
            is_system=True,
            library_invite=library_invite,
            library_action=library_action,
        )
    except Exception:
        return None


def merge_candidates(admin: CustomUser) -> list[dict]:
    """Користувачі, яких адмін може запросити до merge (не члени його бібліотеки)."""
    lib = user_library(admin)
    if lib.admin_id != admin.id:
        return []
    member_ids = set(
        LibraryMembership.objects.filter(library=lib).values_list("user_id", flat=True)
    )
    member_ids.add(admin.id)
    pending_to = set(
        LibraryInvite.objects.filter(
            library=lib, status=LibraryInvite.Status.PENDING
        ).values_list("to_user_id", flat=True)
    )
    out = []
    for u in (
        CustomUser.objects.exclude(pk__in=member_ids)
        .order_by("username")
        .only("id", "username")[:200]
    ):
        out.append(
            {
                "id": u.id,
                "username": u.username,
                "invite_pending": u.id in pending_to,
            }
        )
    return out


@transaction.atomic
def invite_to_library(
    admin: CustomUser,
    to_username: str,
    message: str = "",
) -> LibraryInvite:
    lib = user_library(admin)
    if lib.admin_id != admin.id:
        raise LibraryError("Лише адміністратор може запрошувати до бібліотеки.")
    to_user = CustomUser.objects.filter(username__iexact=to_username.strip()).first()
    if not to_user:
        raise LibraryError("Користувача не знайдено.")
    if to_user.id == admin.id:
        raise LibraryError("Не можна запросити себе.")
    ensure_personal_library(to_user)
    if LibraryMembership.objects.filter(user=to_user, library=lib).exists():
        raise LibraryError("Користувач уже в цій бібліотеці.")
    pending = LibraryInvite.objects.filter(
        library=lib,
        to_user=to_user,
        status=LibraryInvite.Status.PENDING,
    ).first()
    if pending:
        if not PrivateMessage.objects.filter(
            library_invite=pending, sender=admin, recipient=to_user
        ).exists():
            note = (message or pending.message or "").strip()
            body = (
                f"Запит на об'єднання бібліотек із «{lib.display_name}» "
                f"(адмін @{admin.username})."
            )
            if note:
                body = f"{body}\n\n{note}"
            body += "\n\nПідтвердіть або відхиліть у цьому чаті."
            _notify(to_user, body, actor=admin, library_invite=pending)
        return pending
    inv = LibraryInvite.objects.create(
        library=lib,
        from_user=admin,
        to_user=to_user,
        message=(message or "")[:300],
    )
    note = (message or "").strip()
    body = (
        f"Запит на об'єднання бібліотек із «{lib.display_name}» "
        f"(адмін @{admin.username})."
    )
    if note:
        body = f"{body}\n\n{note}"
    body += "\n\nПідтвердіть або відхиліть у цьому чаті."
    _notify(to_user, body, actor=admin, library_invite=inv)
    return inv


@transaction.atomic
def cancel_invite(user: CustomUser, invite_id: int) -> None:
    inv = LibraryInvite.objects.select_related("library").filter(pk=invite_id).first()
    if not inv or inv.status not in (
        LibraryInvite.Status.PENDING,
        LibraryInvite.Status.AWAITING_ISBN,
    ):
        raise LibraryError("Запрошення не знайдено.")
    if inv.from_user_id != user.id and inv.library.admin_id != user.id:
        raise LibraryError("Немає права скасувати запрошення.")
    inv.status = LibraryInvite.Status.CANCELLED
    inv.resolved_at = timezone.now()
    inv.save(update_fields=["status", "resolved_at"])
    _notify(
        inv.to_user,
        f"@{user.username} скасував(ла) запит на об'єднання бібліотек.",
        actor=user,
        library_invite=inv,
    )


@transaction.atomic
def reject_invite(user: CustomUser, invite_id: int) -> None:
    inv = LibraryInvite.objects.filter(pk=invite_id, to_user=user).first()
    if not inv or inv.status not in (
        LibraryInvite.Status.PENDING,
        LibraryInvite.Status.AWAITING_ISBN,
    ):
        raise LibraryError("Запрошення не знайдено.")
    inv.status = LibraryInvite.Status.REJECTED
    inv.resolved_at = timezone.now()
    inv.save(update_fields=["status", "resolved_at"])
    _notify(
        inv.from_user,
        f"@{user.username} відхилив(ла) запит на об'єднання бібліотек.",
        actor=user,
        library_invite=inv,
    )


def _trim_isbn_copies(library: Library, book_id: int, keep: int) -> int:
    """Залишити keep примірників ISBN у бібліотеці; зайві (без активної позики) видалити."""
    copies = list(
        BookCopy.objects.filter(library=library, book_id=book_id).order_by("id")
    )
    if keep < 1:
        keep = 1
    if len(copies) <= keep:
        return len(copies)

    from .exchange.copies import is_copy_lent_out

    removable = [c for c in copies if not is_copy_lent_out(c.id)]
    must_keep = [c for c in copies if is_copy_lent_out(c.id)]
    # Keep lent first, then oldest owned
    keep_set = set(must_keep)
    for c in copies:
        if len(keep_set) >= keep:
            break
        keep_set.add(c)
    removed = 0
    for c in removable:
        if c in keep_set:
            continue
        if len(copies) - removed <= keep:
            break
        Shelf.objects.filter(copy=c).delete()
        c.delete()
        removed += 1
    return BookCopy.objects.filter(library=library, book_id=book_id).count()


@dataclass
class AwaitAdminIsbn:
    """Invitee agreed; admin must confirm duplicate ISBN quantities."""

    invite: LibraryInvite
    overlap: list[dict[str, Any]]
    library: Library


@transaction.atomic
def accept_invite(
    user: CustomUser,
    invite_id: int,
    isbn_counts: dict[str, int] | None = None,
) -> Library | AwaitAdminIsbn:
    """
    Запрошений погоджується на merge.
    Дублі ISBN підтверджує лише адмін (статус awaiting_isbn).
    """
    inv = (
        LibraryInvite.objects.select_related("library", "library__admin", "from_user")
        .filter(pk=invite_id, to_user=user, status=LibraryInvite.Status.PENDING)
        .first()
    )
    if not inv:
        raise LibraryError("Запрошення не знайдено.")

    target = inv.library
    source = ensure_personal_library(user)
    if source.id == target.id:
        raise LibraryError("Вже в цій бібліотеці.")

    overlap = merge_overlap_preview(target, source)
    if overlap:
        inv.status = LibraryInvite.Status.AWAITING_ISBN
        inv.save(update_fields=["status"])
        _notify(
            target.admin,
            f"@{user.username} погодився(лась) на об'єднання бібліотек «{target.display_name}». "
            f"Підтвердіть реальну кількість спільних ISBN ({len(overlap)}) у «Спільна бібліотека».",
            actor=user,
            library_invite=inv,
        )
        return AwaitAdminIsbn(invite=inv, overlap=overlap, library=target)

    return _execute_library_merge(inv, target, source, isbn_counts={})


@transaction.atomic
def admin_confirm_merge_isbn(
    admin: CustomUser,
    invite_id: int,
    isbn_counts: dict[str, int] | None = None,
) -> Library:
    """Адмін підтверджує реальну кількість дубльованих ISBN і завершує merge."""
    inv = (
        LibraryInvite.objects.select_related("library", "library__admin", "to_user")
        .filter(pk=invite_id, status=LibraryInvite.Status.AWAITING_ISBN)
        .first()
    )
    if not inv:
        raise LibraryError("Немає запиту, що очікує підтвердження ISBN.")
    target = inv.library
    if target.admin_id != admin.id:
        raise LibraryError("Лише адміністратор бібліотеки підтверджує кількість ISBN.")

    joining = inv.to_user
    source = ensure_personal_library(joining)
    if source.id == target.id:
        inv.status = LibraryInvite.Status.ACCEPTED
        inv.resolved_at = timezone.now()
        inv.save(update_fields=["status", "resolved_at"])
        return target

    overlap = merge_overlap_preview(target, source)
    isbn_counts = {str(k): int(v) for k, v in (isbn_counts or {}).items()}
    if overlap:
        missing = [row for row in overlap if row["isbn"] not in isbn_counts]
        if missing or not isbn_counts:
            err = LibraryError(
                "Вкажіть реальну кількість фізичних примірників для спільних ISBN."
            )
            err.overlap = overlap  # type: ignore[attr-defined]
            err.awaiting_admin_isbn = True  # type: ignore[attr-defined]
            err.invite_id = inv.id  # type: ignore[attr-defined]
            raise err
        for row in overlap:
            isbn = row["isbn"]
            n = isbn_counts[isbn]
            if n < 1 or n > row["combined"]:
                raise LibraryError(
                    f"ISBN {isbn}: вкажіть кількість від 1 до {row['combined']} "
                    f"(зараз у базі {row['combined']} записів)."
                )
    return _execute_library_merge(inv, target, source, isbn_counts=isbn_counts)


def _execute_library_merge(
    inv: LibraryInvite,
    target: Library,
    source: Library,
    *,
    isbn_counts: dict[str, int],
) -> Library:
    user = inv.to_user
    overlap = merge_overlap_preview(target, source)

    BookCopy.objects.filter(library=source).update(
        library=target,
        owner=target.admin,
    )
    for row in overlap:
        keep = int(isbn_counts[row["isbn"]])
        _trim_isbn_copies(target, row["book_id"], keep)

    LibraryMembership.objects.filter(user=user).delete()
    LibraryMembership.objects.create(
        library=target,
        user=user,
        role=LibraryMembership.Role.MEMBER,
    )
    ensure_library_copy_shelves(target)
    if not LibraryMembership.objects.filter(library=source).exists():
        if not BookCopy.objects.filter(library=source).exists():
            Library.objects.filter(pk=source.pk).delete()

    inv.status = LibraryInvite.Status.ACCEPTED
    inv.resolved_at = timezone.now()
    inv.save(update_fields=["status", "resolved_at"])

    _notify(
        target.admin,
        f"@{user.username} приєднався(лась) до бібліотеки «{target.display_name}».",
        actor=user,
        library_invite=inv,
    )
    _notify(
        user,
        f"Бібліотеки об'єднано з «{target.display_name}». "
        f"Усі спільні книги тепер у «Моя полиця».",
        actor=target.admin,
        library_invite=inv,
    )
    member_n = LibraryMembership.objects.filter(library=target).count()
    if member_n >= 2:
        try:
            start_admin_election(
                user,
                reason="Після об'єднання бібліотек",
                library=target,
            )
        except LibraryError:
            pass
    return target


@transaction.atomic
def request_split_leave(
    user: CustomUser,
    copy_ids: list[int],
) -> LibraryAction | Library:
    """
    Учасник виходить і забирає обрані примірники.
    Адмін — виконується одразу; учасник — чекає approve.
    """
    lib = user_library(user)
    if lib.admin_id == user.id:
        # Admin cannot "leave" via split; transfer admin first (not in v1)
        raise LibraryError(
            "Адміністратор не може вийти. Спочатку передайте роль адміна "
            "(або видаліть інших учасників)."
        )

    ids = [int(x) for x in (copy_ids or [])]
    copies = list(
        BookCopy.objects.filter(library=lib, id__in=ids, added_by=user)
        | BookCopy.objects.filter(library=lib, id__in=ids)
    )
    # Allow taking any copy they currently hold OR added_by them
    allowed = []
    for c in BookCopy.objects.filter(library=lib, id__in=ids):
        holds = Shelf.objects.filter(
            copy=c, user=user, borrowed_from__isnull=True
        ).exists()
        if c.added_by_id == user.id or holds:
            allowed.append(c.id)
    if ids and not allowed:
        raise LibraryError("Немає прав на обрані примірники для поділу.")

    payload = {"copy_ids": allowed or ids}
    if is_library_admin(user, lib):
        raise LibraryError("Адмін не виходить через split.")

    action = LibraryAction.objects.create(
        library=lib,
        initiator=user,
        action_type=LibraryAction.ActionType.SPLIT_LEAVE,
        payload=payload,
    )
    _notify(
        lib.admin,
        f"@{user.username} просить вийти з бібліотеки з поділом примірників "
        f"(дія #{action.pk}). Підтвердіть у «Спільна бібліотека».",
        actor=user,
    )
    return action


@transaction.atomic
def execute_split_leave(action: LibraryAction) -> Library:
    user = action.initiator
    lib = action.library
    copy_ids = [int(x) for x in (action.payload or {}).get("copy_ids") or []]

    new_lib = Library.objects.create(
        name=f"Бібліотека {user.username}",
        admin=user,
    )
    LibraryMembership.objects.filter(user=user).delete()
    LibraryMembership.objects.create(
        library=new_lib,
        user=user,
        role=LibraryMembership.Role.ADMIN,
    )
    qs = BookCopy.objects.filter(library=lib, id__in=copy_ids)
    qs.update(library=new_lib, owner=user)
    # Ensure shelves for user
    for copy in BookCopy.objects.filter(library=new_lib):
        Shelf.objects.filter(copy=copy, borrowed_from__isnull=True).exclude(
            user=user
        ).update(user=user)

    return new_lib


def add_copy_for_user(
    user: CustomUser,
    book: Book,
    *,
    confirm_extra: bool = False,
) -> Shelf | LibraryAction | IsbnConfirmNeeded:
    """
    Додати примірник у бібліотеку користувача.

    - Новий ISBN (немає в бібліотеці) → додається одразу (і для учасника, і для адміна).
    - ISBN уже є → спочатку IsbnConfirmNeeded (повідомлення користувачу).
    - Після confirm_extra: адмін додає одразу; учасник → запит адміну в чат.
    """
    from .exchange.copies import add_owned_copy

    lib = ensure_personal_library(user)
    existing = count_isbn_in_library(lib, book)
    is_shared = LibraryMembership.objects.filter(library=lib).count() >= 2
    i_am_admin = lib.admin_id == user.id

    if existing > 0 and not confirm_extra:
        return IsbnConfirmNeeded(
            isbn=book.isbn,
            existing_count=existing,
            title=book.title,
        )

    # Новий ISBN або адмін (у т.ч. після confirm дубля) — без запиту.
    if existing == 0 or i_am_admin or not is_shared:
        return add_owned_copy(user, book, library=lib, added_by=user)

    # Учасник додає ще один примірник того ж ISBN → запит адміну в чат.
    action = LibraryAction.objects.create(
        library=lib,
        initiator=user,
        action_type=LibraryAction.ActionType.ADD_COPY,
        payload={
            "book_id": book.id,
            "isbn": book.isbn,
            "title": book.title,
            "confirm_extra": True,
            "existing_count": existing,
        },
    )
    body = (
        f"@{user.username} хоче додати ще один примірник «{book.title}» "
        f"(ISBN {book.isbn}). У бібліотеці вже є {existing} шт.\n\n"
        f"Підтвердіть або відхиліть у цьому чаті."
    )
    _notify(lib.admin, body, actor=user, library_action=action)
    return action


def _library_is_shared(lib: Library) -> bool:
    from .library_repo import get_library_repository

    return get_library_repository().count_memberships(lib.id) >= 2


def _action_needs_admin(user: CustomUser, lib: Library) -> bool:
    """Members of a merged library need admin approval; admin / personal lib do not."""
    if lib.admin_id == user.id:
        return False
    return _library_is_shared(lib)

def _items_label(items: list[dict[str, Any]], *, limit: int = 5) -> str:
    titles = [str(i.get("title") or "книга") for i in items[:limit]]
    label = ", ".join(f"«{t}»" for t in titles)
    if len(items) > limit:
        label += f" (+ще {len(items) - limit})"
    return label or f"{len(items)} примірник(ів)"


def get_removable_shelf(user: CustomUser, shelf_id: int) -> Shelf:
    """Own shelf, or any owned shelf of a copy in a library the user admins."""
    from .library_repo import get_library_repository

    shelf = get_library_repository().find_owned_shelf_by_id(shelf_id)
    if not shelf:
        raise LibraryError("Запис не знайдено.")
    if shelf.user_id == user.id:
        return shelf
    lib = ensure_personal_library(user)
    if (
        lib.admin_id == user.id
        and shelf.copy_id
        and shelf.copy.library_id == lib.id
    ):
        return shelf
    raise LibraryError("Немає права видалити цей примірник.")

def _owners_to_inform(shelf: Shelf, actor: CustomUser) -> list[CustomUser]:
    """Contributors / holders of a copy who are not the acting admin."""
    seen: set[int] = set()
    out: list[CustomUser] = []

    def add(u: CustomUser | None) -> None:
        if not u or u.id == actor.id or u.id in seen:
            return
        seen.add(u.id)
        out.append(u)

    copy = shelf.copy
    if copy:
        add(getattr(copy, "added_by", None))
        # After merge legal owner is usually the library admin — skip them.
        owner = getattr(copy, "owner", None)
        lib = getattr(copy, "library", None)
        if owner and (not lib or lib.admin_id != owner.id):
            add(owner)
    add(getattr(shelf, "user", None))
    return out


def remove_library_copy(
    actor: CustomUser,
    shelf: Shelf,
    *,
    notify_owners: bool = True,
) -> None:
    """
    Remove a physical copy from the (shared) library shelf permanently.

    Admin may remove any copy in their library without confirmation.
    Former contributors get an informal chat notice only (no Confirm/Decline).
    """
    from .exchange.copies import remove_owned_shelf
    from .library_repo import get_library_repository

    repo = get_library_repository()
    shelf = repo.find_shelf_for_removal(shelf.pk) or shelf
    copy = shelf.copy
    title = ""
    if copy and copy.book_id:
        title = copy.book.title
    elif shelf.book_id:
        title = shelf.book.title

    to_inform = _owners_to_inform(shelf, actor) if notify_owners else []

    if copy:
        owned_rows = repo.find_owned_shelves_for_copy(copy.id)
        if not owned_rows:
            owned_rows = [shelf]
        for row in owned_rows:
            remove_owned_shelf(row)
        # Detach so ensure_library_copy_shelves won't recreate the shelf.
        if copy.library_id:
            repo.detach_copy_from_library(copy.pk)
    else:
        remove_owned_shelf(shelf)

    if notify_owners and to_inform:
        body = (
            f"Адміністратор @{actor.username} видалив примірник «{title}» "
            f"зі спільної бібліотеки. Це лише повідомлення — підтвердження не потрібне."
        )
        for recipient in to_inform:
            _notify(recipient, body, actor=actor)


def request_remove_copy(user: CustomUser, shelf: Shelf) -> Shelf | LibraryAction:
    from .library_repo import get_library_repository

    lib = ensure_personal_library(user)
    copy = shelf.copy
    if not copy:
        remove_library_copy(user, shelf, notify_owners=False)
        return shelf
    if copy.library_id and copy.library_id != lib.id:
        raise LibraryError("Примірник не з вашої бібліотеки.")
    if not copy.library_id:
        remove_library_copy(user, shelf, notify_owners=False)
        return shelf

    # Admin of merged (or personal) library: delete immediately, inform owners.
    if not _action_needs_admin(user, lib):
        remove_library_copy(user, shelf, notify_owners=_library_is_shared(lib))
        return shelf

    title = copy.book.title if copy.book_id else ""
    action = get_library_repository().create_action(
        library=lib,
        initiator=user,
        action_type=LibraryAction.ActionType.REMOVE_COPY,
        payload={
            "shelf_id": shelf.id,
            "copy_id": copy.id,
            "title": title,
            "items": [{"shelf_id": shelf.id, "copy_id": copy.id, "title": title}],
            "count": 1,
        },
    )
    _notify(
        lib.admin,
        f"@{user.username} просить прибрати «{title}» зі спільної бібліотеки.\n\n"
        f"Підтвердіть або відхиліть у цьому чаті.",
        actor=user,
        library_action=action,
    )
    return action

def request_bulk_remove(
    user: CustomUser, shelf_ids: list[int]
) -> dict[str, Any]:
    """Remove shelves; members of merged lib → one admin request; admin acts now."""
    from .exchange.copies import is_copy_lent_out

    ids = [int(x) for x in shelf_ids if x]
    rows = list(
        Shelf.objects.filter(pk__in=ids, borrowed_from__isnull=True)
        .select_related("copy", "copy__book", "copy__library", "book", "user")
        .order_by("id")
    )
    if not rows:
        raise LibraryError("Не вибрано жодного власного примірника.")

    lib = ensure_personal_library(user)
    i_am_admin = lib.admin_id == user.id
    blocked = []
    eligible = []
    for s in rows:
        allowed = s.user_id == user.id or (
            i_am_admin and s.copy_id and s.copy.library_id == lib.id
        )
        if not allowed:
            blocked.append(s.id)
            continue
        if not s.copy_id:
            blocked.append(s.id)
            continue
        if s.copy.library_id and s.copy.library_id != lib.id:
            blocked.append(s.id)
            continue
        if is_copy_lent_out(s.copy_id):
            blocked.append(s.id)
            continue
        eligible.append(s)

    if not eligible:
        raise LibraryError("Немає примірників, які можна прибрати (можливо в позиці).")

    if not _action_needs_admin(user, lib):
        seen_copies: set[int] = set()
        removed = 0
        for s in eligible:
            if s.copy_id:
                if s.copy_id in seen_copies:
                    continue
                seen_copies.add(s.copy_id)
            if not Shelf.objects.filter(pk=s.pk).exists():
                continue
            remove_library_copy(
                user, s, notify_owners=_library_is_shared(lib)
            )
            removed += 1
        return {
            "pending_approval": False,
            "removed": removed,
            "blocked": blocked,
            "admin_id": lib.admin_id,
        }

    items = [
        {
            "shelf_id": s.id,
            "copy_id": s.copy_id,
            "title": (s.copy.book.title if s.copy and s.copy.book_id else s.book.title),
        }
        for s in eligible
    ]
    action = LibraryAction.objects.create(
        library=lib,
        initiator=user,
        action_type=LibraryAction.ActionType.REMOVE_COPY,
        payload={
            "items": items,
            "title": _items_label(items),
            "count": len(items),
            "shelf_id": items[0]["shelf_id"],
            "copy_id": items[0]["copy_id"],
        },
    )
    _notify(
        lib.admin,
        f"@{user.username} просить прибрати {len(items)} примірник(ів): "
        f"{_items_label(items)}.\n\nПідтвердіть або відхиліть у цьому чаті.",
        actor=user,
        library_action=action,
    )
    return {
        "pending_approval": True,
        "action_id": action.id,
        "count": len(items),
        "blocked": blocked,
        "admin_id": lib.admin_id,
        "action": action,
    }


def request_listing_change(
    user: CustomUser,
    copy: BookCopy,
    listing_payload: dict[str, Any],
) -> BookCopy | LibraryAction:
    from .copy_listing import apply_copy_listing

    lib = copy.library or ensure_personal_library(user)
    my_lib = user_library(user)
    if copy.library_id and copy.library_id != my_lib.id:
        raise LibraryError("Примірник не з вашої бібліотеки.")

    if not _action_needs_admin(user, lib):
        apply_copy_listing(copy, **listing_payload)
        return copy

    title = copy.book.title if copy.book_id else ""
    action = LibraryAction.objects.create(
        library=lib,
        initiator=user,
        action_type=LibraryAction.ActionType.LISTING,
        payload={
            "copy_id": copy.id,
            "listing": listing_payload,
            "title": title,
            "items": [{"copy_id": copy.id, "title": title}],
            "count": 1,
        },
    )
    _notify(
        lib.admin,
        f"@{user.username} просить змінити статуси оголошення для «{title}».\n\n"
        f"Підтвердіть або відхиліть у цьому чаті.",
        actor=user,
        library_action=action,
    )
    return action


def request_bulk_listing(
    user: CustomUser,
    shelf_ids: list[int],
    listing_payload: dict[str, Any],
) -> dict[str, Any]:
    from .copy_listing import apply_copy_listing

    ids = [int(x) for x in shelf_ids if x]
    shelves = list(
        Shelf.objects.filter(pk__in=ids, user=user, borrowed_from__isnull=True)
        .select_related("copy", "copy__book", "book")
        .order_by("id")
    )
    shelves = [s for s in shelves if s.copy_id]
    if not shelves:
        raise LibraryError("Не вибрано жодного власного примірника.")

    lib = ensure_personal_library(user)
    for s in shelves:
        if s.copy.library_id and s.copy.library_id != lib.id:
            raise LibraryError("Примірник не з вашої бібліотеки.")

    if not _action_needs_admin(user, lib):
        for s in shelves:
            apply_copy_listing(s.copy, **listing_payload)
        return {
            "pending_approval": False,
            "updated": len(shelves),
            "admin_id": lib.admin_id,
        }

    items = [
        {
            "shelf_id": s.id,
            "copy_id": s.copy_id,
            "title": (s.copy.book.title if s.copy and s.copy.book_id else s.book.title),
        }
        for s in shelves
    ]
    action = LibraryAction.objects.create(
        library=lib,
        initiator=user,
        action_type=LibraryAction.ActionType.LISTING,
        payload={
            "items": items,
            "listing": listing_payload,
            "title": _items_label(items),
            "count": len(items),
            "copy_id": items[0]["copy_id"],
        },
    )
    _notify(
        lib.admin,
        f"@{user.username} просить змінити статуси для {len(items)} примірник(ів): "
        f"{_items_label(items)}.\n\nПідтвердіть або відхиліть у цьому чаті.",
        actor=user,
        library_action=action,
    )
    return {
        "pending_approval": True,
        "action_id": action.id,
        "count": len(items),
        "admin_id": lib.admin_id,
        "action": action,
    }


def _resolve_remove_payload(payload: dict[str, Any], *, actor: CustomUser) -> None:
    items = payload.get("items")
    if isinstance(items, list) and items:
        for it in items:
            shelf = (
                Shelf.objects.select_related(
                    "copy",
                    "copy__book",
                    "copy__owner",
                    "copy__added_by",
                    "copy__library",
                    "book",
                    "user",
                )
                .filter(pk=it.get("shelf_id"))
                .first()
            )
            if shelf:
                # Initiator already gets the approval message from resolve_action.
                remove_library_copy(actor, shelf, notify_owners=False)
        return
    shelf = (
        Shelf.objects.select_related(
            "copy",
            "copy__book",
            "copy__owner",
            "copy__added_by",
            "copy__library",
            "book",
            "user",
        )
        .filter(pk=payload.get("shelf_id"))
        .first()
    )
    if shelf:
        remove_library_copy(actor, shelf, notify_owners=False)


def _resolve_listing_payload(payload: dict[str, Any]) -> None:
    from .copy_listing import apply_copy_listing

    listing = payload.get("listing") or {}
    items = payload.get("items")
    if isinstance(items, list) and items:
        for it in items:
            copy = BookCopy.objects.filter(pk=it.get("copy_id")).first()
            if copy:
                apply_copy_listing(copy, **listing)
        return
    copy = BookCopy.objects.filter(pk=payload.get("copy_id")).first()
    if copy:
        apply_copy_listing(copy, **listing)


@transaction.atomic
def resolve_action(
    admin: CustomUser,
    action_id: int,
    *,
    approve: bool,
) -> LibraryAction:
    action = (
        LibraryAction.objects.select_related("library", "initiator", "library__admin")
        .filter(pk=action_id, status=LibraryAction.Status.PENDING)
        .first()
    )
    if not action:
        raise LibraryError("Дію не знайдено.")
    if action.library.admin_id != admin.id:
        raise LibraryError("Лише адміністратор може підтверджувати дії.")

    action.resolved_by = admin
    action.resolved_at = timezone.now()
    payload = action.payload or {}
    title = payload.get("title") or action.get_action_type_display()
    type_label = action.get_action_type_display()

    if not approve:
        action.status = LibraryAction.Status.REJECTED
        action.save(update_fields=["status", "resolved_by", "resolved_at"])
        _notify(
            action.initiator,
            f"Адмін відхилив запит «{type_label}»: {title}.",
            actor=admin,
            library_action=action,
        )
        return action

    if action.action_type == LibraryAction.ActionType.ADD_COPY:
        from .exchange.copies import add_owned_copy

        book = Book.objects.filter(pk=payload.get("book_id")).first()
        if not book:
            raise LibraryError("Книгу не знайдено.")
        shelf = add_owned_copy(
            action.initiator,
            book,
            library=action.library,
            added_by=action.initiator,
        )
        action.result_note = f"shelf:{shelf.id}"
        ok_msg = f"Адмін схвалив додавання «{title}». Книга з’явилась у «Моя полиця»."
    elif action.action_type == LibraryAction.ActionType.REMOVE_COPY:
        _resolve_remove_payload(payload, actor=admin)
        ok_msg = f"Адмін схвалив видалення: {title}."
    elif action.action_type == LibraryAction.ActionType.LISTING:
        _resolve_listing_payload(payload)
        ok_msg = f"Адмін схвалив зміну статусів: {title}."
    elif action.action_type == LibraryAction.ActionType.SPLIT_LEAVE:
        new_lib = execute_split_leave(action)
        action.result_note = f"library:{new_lib.id}"
        ok_msg = f"Адмін схвалив вихід з поділом: {title}."
    else:
        raise LibraryError("Невідомий тип дії.")

    action.status = LibraryAction.Status.APPROVED
    action.save(
        update_fields=["status", "resolved_by", "resolved_at", "result_note"]
    )
    _notify(
        action.initiator,
        ok_msg,
        actor=admin,
        library_action=action,
    )
    return action


def _transfer_admin(library: Library, new_admin: CustomUser) -> None:
    if not LibraryMembership.objects.filter(library=library, user=new_admin).exists():
        raise LibraryError("Кандидат не є учасником бібліотеки.")
    old_admin_id = library.admin_id
    library.admin = new_admin
    library.save(update_fields=["admin"])
    LibraryMembership.objects.filter(library=library, user_id=old_admin_id).update(
        role=LibraryMembership.Role.MEMBER
    )
    LibraryMembership.objects.filter(library=library, user=new_admin).update(
        role=LibraryMembership.Role.ADMIN
    )
    BookCopy.objects.filter(library=library).update(owner=new_admin)


def _notify_library_members(library: Library, body: str, actor: CustomUser) -> None:
    for m in library.memberships.select_related("user").exclude(user_id=actor.id):
        _notify(m.user, body, actor=actor)


def election_tally(election: LibraryAdminElection) -> dict[str, Any]:
    members = list(
        LibraryMembership.objects.filter(library_id=election.library_id).select_related(
            "user"
        )
    )
    member_ids = {m.user_id for m in members}
    votes = list(
        LibraryAdminVote.objects.filter(election=election).select_related(
            "voter", "candidate"
        )
    )
    counts: dict[int, int] = {}
    for v in votes:
        counts[v.candidate_id] = counts.get(v.candidate_id, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    my_vote = None
    return {
        "election_id": election.id,
        "status": election.status,
        "reason": election.reason,
        "started_by_id": election.started_by_id,
        "member_count": len(members),
        "votes_cast": len(votes),
        "candidates": [
            {
                "user_id": m.user_id,
                "username": m.user.username,
                "votes": counts.get(m.user_id, 0),
                "is_current_admin": m.user_id == election.library.admin_id,
            }
            for m in members
        ],
        "votes": [
            {
                "voter_id": v.voter_id,
                "voter_username": v.voter.username,
                "candidate_id": v.candidate_id,
                "candidate_username": v.candidate.username,
            }
            for v in votes
        ],
        "leader_id": ranked[0][0] if ranked else None,
        "leader_votes": ranked[0][1] if ranked else 0,
        "needs_all_votes": len(votes) < len(members),
        "can_finalize": len(votes) >= len(members) and len(members) >= 2 and bool(ranked),
    }


@transaction.atomic
def start_admin_election(
    user: CustomUser,
    *,
    reason: str = "",
    library: Library | None = None,
) -> LibraryAdminElection:
    lib = library or user_library(user)
    if not LibraryMembership.objects.filter(library=lib, user=user).exists():
        raise LibraryError("Ви не учасник цієї бібліотеки.")
    member_n = LibraryMembership.objects.filter(library=lib).count()
    if member_n < 2:
        raise LibraryError("Голосування потрібне лише для спільної бібліотеки (2+ учасники).")
    open_el = LibraryAdminElection.objects.filter(
        library=lib, status=LibraryAdminElection.Status.OPEN
    ).first()
    if open_el:
        return open_el
    el = LibraryAdminElection.objects.create(
        library=lib,
        started_by=user,
        reason=(reason or "Зміна адміністратора")[:200],
    )
    _notify_library_members(
        lib,
        f"@{user.username} відкрив(ла) голосування за адміністратора бібліотеки "
        f"«{lib.display_name}». Проголосуйте в «Спільна бібліотека».",
        actor=user,
    )
    return el


@transaction.atomic
def cancel_admin_election(user: CustomUser, election_id: int) -> LibraryAdminElection:
    el = (
        LibraryAdminElection.objects.select_related("library")
        .filter(pk=election_id, status=LibraryAdminElection.Status.OPEN)
        .first()
    )
    if not el:
        raise LibraryError("Відкритих виборів не знайдено.")
    if el.started_by_id != user.id and el.library.admin_id != user.id:
        raise LibraryError("Скасувати може ініціатор або поточний адмін.")
    el.status = LibraryAdminElection.Status.CANCELLED
    el.resolved_at = timezone.now()
    el.save(update_fields=["status", "resolved_at"])
    return el


@transaction.atomic
def cast_admin_vote(
    user: CustomUser,
    election_id: int,
    candidate_id: int,
) -> LibraryAdminElection:
    el = (
        LibraryAdminElection.objects.select_related("library", "library__admin")
        .filter(pk=election_id, status=LibraryAdminElection.Status.OPEN)
        .first()
    )
    if not el:
        raise LibraryError("Вибори не знайдено або вже завершені.")
    lib = el.library
    if not LibraryMembership.objects.filter(library=lib, user=user).exists():
        raise LibraryError("Лише учасники бібліотеки можуть голосувати.")
    if not LibraryMembership.objects.filter(library=lib, user_id=candidate_id).exists():
        raise LibraryError("Кандидат має бути учасником бібліотеки.")

    LibraryAdminVote.objects.update_or_create(
        election=el,
        voter=user,
        defaults={"candidate_id": candidate_id},
    )

    tally = election_tally(el)
    if tally["can_finalize"]:
        return _finalize_election(el, tally)

    return el


def _finalize_election(
    el: LibraryAdminElection, tally: dict[str, Any] | None = None
) -> LibraryAdminElection:
    tally = tally or election_tally(el)
    if not tally["can_finalize"]:
        raise LibraryError("Ще не всі учасники проголосували.")
    winner_id = tally["leader_id"]
    # Tie-break: if top two equal, keep current admin if tied, else lowest user id already in ranked
    votes = list(
        LibraryAdminVote.objects.filter(election=el).values_list("candidate_id", flat=True)
    )
    counts: dict[int, int] = {}
    for cid in votes:
        counts[cid] = counts.get(cid, 0) + 1
    max_v = max(counts.values()) if counts else 0
    leaders = [cid for cid, n in counts.items() if n == max_v]
    if el.library.admin_id in leaders:
        winner_id = el.library.admin_id
    else:
        winner_id = min(leaders)

    winner = CustomUser.objects.get(pk=winner_id)
    old = el.library.admin
    _transfer_admin(el.library, winner)
    el.winner = winner
    el.status = LibraryAdminElection.Status.COMPLETED
    el.resolved_at = timezone.now()
    el.save(update_fields=["winner", "status", "resolved_at"])
    _notify_library_members(
        el.library,
        f"Новий адміністратор бібліотеки «{el.library.display_name}»: @{winner.username}"
        + (f" (було @{old.username})" if old.id != winner.id else "")
        + ".",
        actor=winner,
    )
    return el


@transaction.atomic
def finalize_admin_election(user: CustomUser, election_id: int) -> LibraryAdminElection:
    """Примусове завершення, коли всі голоси зібрані (будь-який учасник)."""
    el = (
        LibraryAdminElection.objects.select_related("library")
        .filter(pk=election_id, status=LibraryAdminElection.Status.OPEN)
        .first()
    )
    if not el:
        raise LibraryError("Вибори не знайдено.")
    if not LibraryMembership.objects.filter(library=el.library, user=user).exists():
        raise LibraryError("Немає доступу.")
    return _finalize_election(el)


def splittable_copies_for(user: CustomUser, library: Library | None = None) -> list[dict[str, Any]]:
    lib = library or user_library(user)
    out = []
    for c in (
        BookCopy.objects.filter(library=lib)
        .select_related("book")
        .order_by("book__title", "id")
    ):
        holds = Shelf.objects.filter(
            copy=c, user=user, borrowed_from__isnull=True
        ).exists()
        if c.added_by_id == user.id or holds:
            out.append(
                {
                    "id": c.id,
                    "book_id": c.book_id,
                    "title": c.book.title,
                    "isbn": c.book.isbn,
                    "added_by_me": c.added_by_id == user.id,
                    "held_by_me": holds,
                }
            )
    return out


def library_snapshot(user: CustomUser) -> dict[str, Any]:
    lib = ensure_personal_library(user)
    members = [
        {
            "user_id": m.user_id,
            "username": m.user.username,
            "role": m.role,
            "joined_at": m.joined_at.isoformat(),
        }
        for m in lib.memberships.select_related("user").all()
    ]
    pending_in = list(
        LibraryInvite.objects.filter(
            to_user=user, status=LibraryInvite.Status.PENDING
        ).select_related("library", "from_user")
    )
    pending_out = list(
        LibraryInvite.objects.filter(
            library=lib,
            status__in=(
                LibraryInvite.Status.PENDING,
                LibraryInvite.Status.AWAITING_ISBN,
            ),
        ).select_related("to_user")
    )
    awaiting_isbn = list(
        LibraryInvite.objects.filter(
            library=lib,
            status=LibraryInvite.Status.AWAITING_ISBN,
        ).select_related("to_user", "from_user")
        if lib.admin_id == user.id
        else []
    )
    actions = list(
        LibraryAction.objects.filter(
            library=lib, status=LibraryAction.Status.PENDING
        ).select_related("initiator")
        if lib.admin_id == user.id
        else LibraryAction.objects.filter(
            initiator=user, status=LibraryAction.Status.PENDING
        ).select_related("initiator")
    )
    open_el = (
        LibraryAdminElection.objects.filter(
            library=lib, status=LibraryAdminElection.Status.OPEN
        )
        .order_by("-created_at")
        .first()
    )
    election = None
    if open_el:
        election = election_tally(open_el)
        my = LibraryAdminVote.objects.filter(election=open_el, voter=user).first()
        election["my_candidate_id"] = my.candidate_id if my else None
        election["i_voted"] = bool(my)

    return {
        "library": {
            "id": lib.id,
            "name": lib.display_name,
            "admin_id": lib.admin_id,
            "admin_username": lib.admin.username,
            "i_am_admin": lib.admin_id == user.id,
            "member_count": len(members),
            "is_shared": len(members) >= 2,
        },
        "members": members,
        "invites_in": [
            {
                "id": i.id,
                "library_id": i.library_id,
                "library_name": i.library.display_name,
                "from_user_id": i.from_user_id,
                "from_username": i.from_user.username,
                "message": i.message,
                "overlap": merge_overlap_preview(
                    i.library, ensure_personal_library(user)
                ),
            }
            for i in pending_in
        ],
        "invites_out": [
            {
                "id": i.id,
                "to_user_id": i.to_user_id,
                "to_username": i.to_user.username,
                "message": i.message,
                "status": i.status,
            }
            for i in pending_out
        ],
        "awaiting_isbn_merges": [
            {
                "id": i.id,
                "to_user_id": i.to_user_id,
                "to_username": i.to_user.username,
                "overlap": merge_overlap_preview(
                    lib, ensure_personal_library(i.to_user)
                ),
            }
            for i in awaiting_isbn
        ],
        "pending_actions": [
            {
                "id": a.id,
                "action_type": a.action_type,
                "action_type_label": a.get_action_type_display(),
                "initiator_username": a.initiator.username,
                "payload": a.payload,
                "created_at": a.created_at.isoformat(),
            }
            for a in actions
        ],
        "election": election,
        "splittable_copies": splittable_copies_for(user, lib),
        "merge_candidates": merge_candidates(user) if lib.admin_id == user.id else [],
    }
