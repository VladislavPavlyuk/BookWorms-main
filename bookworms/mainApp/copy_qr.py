"""Unique QR labels for BookCopy instances (generate / print / attach / resolve)."""
from __future__ import annotations

import base64
import io
import secrets
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from .copy_events import log_copy_event
from .exceptions import ExchangeForbidden, ExchangeInvalidState, ExchangeNotFound
from .models import BookCopy, CopyEvent, CustomUser, LoanHandoff, PreprintedQrToken

QR_PREFIX = "BW1."
# A4 is 210×297 mm — a literal 200×200 mm QR cannot fit 36 labels on one page.
# Sheet: 6×6 = 36 unique labels; each cell holds brand title + max square QR.
A4_COLS = 6
A4_ROWS = 6
SLOTS_PER_A4_PAGE = A4_COLS * A4_ROWS  # 36
A4_PAGE_MARGIN_MM = 5
A4_WIDTH_MM = 210
A4_HEIGHT_MM = 297
LABEL_W_MM = (A4_WIDTH_MM - 2 * A4_PAGE_MARGIN_MM) / A4_COLS  # ≈ 33.33 mm
LABEL_H_MM = (A4_HEIGHT_MM - 3 * A4_PAGE_MARGIN_MM) / A4_ROWS  # ≈ 47.83 mm
# Title + padding leave ~28 mm for the QR square inside the label.
QR_PRINT_MM = 28
QR_BRAND_TITLE = "www.datedueslip.com"


def make_qr_token() -> str:
    return secrets.token_urlsafe(16)


def qr_payload_for_token(token: str) -> str:
    return f"{QR_PREFIX}{token}"


def parse_qr_payload(raw: str | None) -> str:
    """Extract token from scanned payload (BW1.<token> or bare token)."""
    text = (raw or "").strip()
    if not text:
        raise ExchangeInvalidState("Порожній QR-код.")
    if "qr=" in text:
        text = text.split("qr=", 1)[1].split("&", 1)[0]
    if "/q/" in text:
        text = text.rsplit("/q/", 1)[-1].split("?", 1)[0].strip("/")
    if text.upper().startswith(QR_PREFIX.upper()):
        text = text[len(QR_PREFIX) :]
    token = text.strip()
    if len(token) < 8 or len(token) > 64:
        raise ExchangeInvalidState("Невідомий формат QR примірника.")
    return token


def _token_exists(token: str) -> bool:
    return (
        BookCopy.objects.filter(qr_token=token).exists()
        or PreprintedQrToken.objects.filter(token=token).exists()
    )


def _mint_unique_token() -> str:
    for _ in range(12):
        token = make_qr_token()
        if not _token_exists(token):
            return token
    raise ExchangeInvalidState("Не вдалося згенерувати унікальний QR.")


def _assign_new_token(copy: BookCopy) -> BookCopy:
    copy.qr_token = _mint_unique_token()
    copy.qr_attached_at = None
    copy.save(update_fields=["qr_token", "qr_attached_at"])
    return copy


def ensure_copy_qr(copy: BookCopy, acting_user: CustomUser) -> BookCopy:
    if copy.owner_id != acting_user.id:
        raise ExchangeForbidden("QR може згенерувати лише власник примірника.")
    if copy.qr_token:
        return copy
    return _assign_new_token(copy)


@transaction.atomic
def rotate_copy_qr(copy_id: int, acting_user: CustomUser) -> BookCopy:
    """Replace QR token (lost / unreadable label). Old sticker stops working."""
    try:
        copy = (
            BookCopy.objects.select_for_update(of=("self",))
            .select_related("book", "owner")
            .get(pk=copy_id)
        )
    except BookCopy.DoesNotExist as exc:
        raise ExchangeNotFound("Примірник не знайдено.") from exc
    if copy.owner_id != acting_user.id:
        raise ExchangeForbidden("Оновити QR може лише власник.")
    if not copy.qr_token:
        raise ExchangeInvalidState("Спочатку створіть QR (Скан QR).")
    return _assign_new_token(copy)


@transaction.atomic
def ensure_owner_qr_tokens(owner: CustomUser, *, copy_ids: list[int] | None = None) -> list[BookCopy]:
    qs = BookCopy.objects.select_for_update(of=("self",)).filter(owner=owner)
    if copy_ids:
        qs = qs.filter(pk__in=copy_ids)
    copies = list(qs.select_related("book").order_by("id"))
    for c in copies:
        if not c.qr_token:
            ensure_copy_qr(c, owner)
    return list(
        BookCopy.objects.filter(pk__in=[c.pk for c in copies])
        .select_related("book")
        .order_by("id")
    )


@transaction.atomic
def ensure_spare_qr_tokens(owner: CustomUser, count: int) -> list[PreprintedQrToken]:
    """Create `count` unassigned preprint tokens for this owner (may reuse free ones)."""
    if count <= 0:
        return []
    free = list(
        PreprintedQrToken.objects.select_for_update(of=("self",))
        .filter(owner=owner, copy__isnull=True)
        .order_by("id")[:count]
    )
    created: list[PreprintedQrToken] = []
    need = count - len(free)
    for _ in range(need):
        created.append(
            PreprintedQrToken.objects.create(token=_mint_unique_token(), owner=owner)
        )
    return free + created


def _recycle_token_to_pool(owner: CustomUser, token: str | None) -> None:
    if not token:
        return
    if PreprintedQrToken.objects.filter(token=token).exists():
        return
    PreprintedQrToken.objects.create(token=token, owner=owner)


@transaction.atomic
def attach_copy_qr(copy_id: int, acting_user: CustomUser, payload: str) -> BookCopy:
    """Owner scans printed label to bind it to this instance (copy token or preprint pool)."""
    try:
        copy = (
            BookCopy.objects.select_for_update(of=("self",))
            .select_related("book", "owner")
            .get(pk=copy_id)
        )
    except BookCopy.DoesNotExist as exc:
        raise ExchangeNotFound("Примірник не знайдено.") from exc
    if copy.owner_id != acting_user.id:
        raise ExchangeForbidden("Прив’язати QR може лише власник.")

    token = parse_qr_payload(payload)

    if copy.qr_token and token == copy.qr_token:
        pass
    else:
        pool = (
            PreprintedQrToken.objects.select_for_update(of=("self",))
            .filter(token=token, owner=acting_user, copy__isnull=True)
            .first()
        )
        if not pool:
            other = BookCopy.objects.filter(qr_token=token).exclude(pk=copy.pk).first()
            if other:
                raise ExchangeInvalidState(
                    "Цей QR уже прив’язаний до іншого примірника."
                )
            raise ExchangeInvalidState(
                "Цей QR не з вашого друку. Роздрукуйте аркуш у Налаштуваннях "
                "або скануйте наклейку цього примірника."
            )
        if copy.qr_attached_at and copy.qr_token and copy.qr_token != token:
            raise ExchangeInvalidState(
                "У примірника вже є приклеєний QR. Спочатку «Оновити QR-код»."
            )
        if copy.qr_token and copy.qr_token != token and not copy.qr_attached_at:
            _recycle_token_to_pool(acting_user, copy.qr_token)
        copy.qr_token = token
        pool.copy = copy
        pool.claimed_at = timezone.now()
        pool.save(update_fields=["copy", "claimed_at"])

    if not copy.qr_attached_at:
        copy.qr_attached_at = timezone.now()
        copy.save(update_fields=["qr_token", "qr_attached_at"])
        log_copy_event(
            copy.id,
            CopyEvent.Code.QR_ATTACHED,
            actor=acting_user,
            holder=acting_user,
            legal_owner=acting_user,
        )
    elif copy.qr_token != token:
        copy.save(update_fields=["qr_token", "qr_attached_at"])
    return copy


def resolve_copy_by_qr(payload: str) -> BookCopy:
    token = parse_qr_payload(payload)
    copy = (
        BookCopy.objects.filter(qr_token=token)
        .select_related("book", "owner")
        .first()
    )
    if copy:
        return copy
    pool = (
        PreprintedQrToken.objects.filter(token=token)
        .select_related("copy__book", "copy__owner")
        .first()
    )
    if pool and pool.copy_id:
        return pool.copy
    if pool:
        raise ExchangeInvalidState(
            "Ця наклейка ще не прив’язана. Відкрийте примірник → Скан QR."
        )
    raise ExchangeNotFound("Примірник з таким QR не знайдено.")


def assert_qr_matches_copy(copy: BookCopy, payload: str | None) -> None:
    if not copy.qr_token:
        raise ExchangeInvalidState("У цього примірника ще немає QR.")
    token = parse_qr_payload(payload)
    if token != copy.qr_token:
        raise ExchangeInvalidState("QR не відповідає цьому примірнику.")


def require_qr_for_handoff(handoff: LoanHandoff, payload: str | None) -> None:
    """If label is attached, physical give/receive must scan that QR."""
    copy = handoff.copy
    if copy.qr_attached_at:
        if not payload:
            raise ExchangeInvalidState(
                "Відскануйте QR-наклейку примірника для підтвердження."
            )
        assert_qr_matches_copy(copy, payload)
    elif payload:
        if copy.qr_token:
            assert_qr_matches_copy(copy, payload)


def qr_png_data_uri(payload: str, *, box_size: int = 8, border: int = 1) -> str:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


@dataclass
class QrLabel:
    copy_id: int | None
    title: str
    payload: str
    data_uri: str
    attached: bool


def build_print_labels(copies: list[BookCopy]) -> list[QrLabel]:
    labels: list[QrLabel] = []
    for c in copies:
        if not c.qr_token:
            continue
        payload = qr_payload_for_token(c.qr_token)
        labels.append(
            QrLabel(
                copy_id=c.id,
                title=(c.book.title or "")[:40],
                payload=payload,
                data_uri=qr_png_data_uri(payload),
                attached=bool(c.qr_attached_at),
            )
        )
    return labels


def _labels_from_pool(tokens: list[PreprintedQrToken]) -> list[QrLabel]:
    out: list[QrLabel] = []
    for t in tokens:
        payload = qr_payload_for_token(t.token)
        out.append(
            QrLabel(
                copy_id=None,
                title="",
                payload=payload,
                data_uri=qr_png_data_uri(payload),
                attached=False,
            )
        )
    return out


@transaction.atomic
def build_full_a4_print_pages(
    owner: CustomUser, *, copy_ids: list[int] | None = None
) -> list[list[QrLabel]]:
    """
    Full A4 pages of exactly 36 unique QR labels each.
    Owner copies first; remaining cells filled from preprint pool (created as needed).
    Always returns at least one full page.
    """
    copies = ensure_owner_qr_tokens(owner, copy_ids=copy_ids)
    labels = build_print_labels(copies)
    slots = SLOTS_PER_A4_PAGE
    if not labels:
        need = slots
    else:
        rem = len(labels) % slots
        need = 0 if rem == 0 else slots - rem
    if need:
        labels.extend(_labels_from_pool(ensure_spare_qr_tokens(owner, need)))
    pages: list[list[QrLabel]] = []
    for start in range(0, len(labels), slots):
        chunk = labels[start : start + slots]
        # Safety: never leave holes on a page.
        if len(chunk) < slots:
            chunk = chunk + _labels_from_pool(
                ensure_spare_qr_tokens(owner, slots - len(chunk))
            )
        pages.append(chunk)
    return pages


def paginate_labels_full_a4(
    labels: list[QrLabel], *, pad_partial_page: bool = True
) -> list[list[QrLabel | None]]:
    """Legacy helper — prefer build_full_a4_print_pages for print."""
    slots = SLOTS_PER_A4_PAGE
    if not labels:
        return []
    pages: list[list[QrLabel | None]] = []
    for start in range(0, len(labels), slots):
        chunk: list[QrLabel | None] = list(labels[start : start + slots])
        if pad_partial_page:
            while len(chunk) < slots:
                chunk.append(None)
        pages.append(chunk)
    return pages


def serialize_copy_qr(copy: BookCopy) -> dict:
    return {
        "has_qr": bool(copy.qr_token),
        "qr_attached": bool(copy.qr_attached_at),
        "qr_attached_at": (
            copy.qr_attached_at.isoformat() if copy.qr_attached_at else None
        ),
        "qr_payload": (
            qr_payload_for_token(copy.qr_token) if copy.qr_token else None
        ),
        "requires_qr_scan": bool(copy.qr_attached_at),
    }
