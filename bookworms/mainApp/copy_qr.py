"""Unique QR labels for BookCopy — late binding (print unbound, bind on scan)."""
from __future__ import annotations

import base64
import io
import logging
import re
import secrets
from dataclasses import dataclass
from urllib.parse import unquote

from django.db import transaction
from django.utils import timezone

from .copy_events import log_copy_event
from .exceptions import ExchangeForbidden, ExchangeInvalidState, ExchangeNotFound
from .models import BookCopy, CopyEvent, CustomUser, LoanHandoff, PreprintedQrToken

logger = logging.getLogger(__name__)

QR_PREFIX = "BW1."
# A4 sheet: 6×6 = 36 unbound unique labels; bind only when owner scans after gluing.
A4_COLS = 6
A4_ROWS = 6
SLOTS_PER_A4_PAGE = A4_COLS * A4_ROWS  # 36
A4_PAGE_MARGIN_MM = 5
A4_WIDTH_MM = 210
A4_HEIGHT_MM = 297
LABEL_W_MM = (A4_WIDTH_MM - 2 * A4_PAGE_MARGIN_MM) / A4_COLS  # ≈ 33.33 mm
LABEL_H_MM = (A4_HEIGHT_MM - 3 * A4_PAGE_MARGIN_MM) / A4_ROWS  # ≈ 47.83 mm
QR_PRINT_MM = 30
QR_BRAND_TITLE = "www.datedueslip.com"
# token_urlsafe alphabet (+ legacy early-bind leftovers).
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def make_qr_token() -> str:
    return secrets.token_urlsafe(16)


def qr_payload_for_token(token: str) -> str:
    return f"{QR_PREFIX}{token}"


def parse_qr_payload(raw: str | None) -> str:
    """Extract token from scanned payload (BW1.<token>, URL, or bare token)."""
    text = unquote((raw or "").strip()).strip().strip("\"'")
    if not text:
        raise ExchangeInvalidState("Порожній QR-код.")
    # Drop accidental camera / keyboard noise around the payload.
    if "BW1." in text.upper() or "bw1." in text:
        # Prefer the BW1. segment even if wrapped in a URL or extra text.
        for part in re.split(r"[\s<>\"']+", text):
            if part.upper().startswith(QR_PREFIX.upper()):
                text = part
                break
    if "qr=" in text:
        text = text.split("qr=", 1)[1].split("&", 1)[0]
        text = unquote(text)
    if "/q/" in text:
        text = text.rsplit("/q/", 1)[-1].split("?", 1)[0].strip("/")
        text = unquote(text)
    if text.upper().startswith(QR_PREFIX.upper()):
        text = text[len(QR_PREFIX) :]
    token = text.strip()
    if not _TOKEN_RE.match(token):
        logger.warning("copy_qr parse reject raw=%r token=%r", raw, token)
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


@transaction.atomic
def ensure_spare_qr_tokens(owner: CustomUser, count: int) -> list[PreprintedQrToken]:
    """Create/reuse `count` unassigned preprint tokens (never bound to a copy)."""
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


def _burn_token(token: str | None) -> None:
    """Invalidate a sticker so it can no longer be claimed or resolved."""
    if not token:
        return
    PreprintedQrToken.objects.filter(token=token).delete()


@transaction.atomic
def rotate_copy_qr(copy_id: int, acting_user: CustomUser) -> BookCopy:
    """
    Unbind lost/unreadable label (late binding).
    Does NOT assign a new token to the copy — print a new sheet, then Скан QR.
    """
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
    if not copy.qr_token and not copy.qr_attached_at:
        raise ExchangeInvalidState("QR ще не прив’язано — спочатку Скан QR.")
    old = copy.qr_token
    copy.qr_token = None
    copy.qr_attached_at = None
    copy.save(update_fields=["qr_token", "qr_attached_at"])
    _burn_token(old)
    return copy


@transaction.atomic
def attach_copy_qr(copy_id: int, acting_user: CustomUser, payload: str) -> BookCopy:
    """
    Late bind: owner scans a printed unbound label after gluing it on this copy.
    """
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

    # Already bound to this copy — idempotent confirm.
    if copy.qr_token and token == copy.qr_token:
        if not copy.qr_attached_at:
            copy.qr_attached_at = timezone.now()
            copy.save(update_fields=["qr_attached_at"])
            log_copy_event(
                copy.id,
                CopyEvent.Code.QR_ATTACHED,
                actor=acting_user,
                holder=acting_user,
                legal_owner=acting_user,
            )
        return copy

    if copy.qr_attached_at and copy.qr_token and copy.qr_token != token:
        raise ExchangeInvalidState(
            "У примірника вже є приклеєний QR. Спочатку «Оновити QR-код»."
        )

    pool = (
        PreprintedQrToken.objects.select_for_update(of=("self",))
        .filter(token=token, copy__isnull=True)
        .first()
    )
    if pool and pool.owner_id != acting_user.id:
        logger.warning(
            "copy_qr attach foreign pool token=%s copy=%s user=%s owner=%s",
            token,
            copy_id,
            acting_user.id,
            pool.owner_id,
        )
        raise ExchangeInvalidState(
            "Цей QR з друку іншого користувача."
        )

    if not pool:
        other = BookCopy.objects.filter(qr_token=token).exclude(pk=copy.pk).first()
        if other:
            raise ExchangeInvalidState(
                "Цей QR уже прив’язаний до іншого примірника."
            )
        claimed = (
            PreprintedQrToken.objects.select_for_update(of=("self",))
            .filter(token=token, copy__isnull=False)
            .first()
        )
        if claimed:
            raise ExchangeInvalidState(
                "Цей QR уже прив’язаний до іншого примірника."
            )
        # Recovery: early-bind stickers / wiped BookCopy tokens left orphans not in
        # PreprintedQrToken. Owner scanning an unused BW1 token enrolls it into pool.
        foreign = (
            PreprintedQrToken.objects.select_for_update(of=("self",))
            .filter(token=token)
            .first()
        )
        if foreign:
            logger.warning(
                "copy_qr attach unexpected pool state token=%s copy=%s user=%s",
                token,
                copy_id,
                acting_user.id,
            )
            raise ExchangeInvalidState(
                "Цей QR не з вашого друку. Роздрукуйте аркуш у Налаштуваннях, "
                "наклейте й відскануйте."
            )
        logger.info(
            "copy_qr attach enroll orphan token=%s copy=%s user=%s raw=%r",
            token,
            copy_id,
            acting_user.id,
            payload[:80],
        )
        pool = PreprintedQrToken.objects.create(token=token, owner=acting_user)

    # Drop any legacy early-bound unattached token without reclaiming it as printable.
    if copy.qr_token and copy.qr_token != token and not copy.qr_attached_at:
        _burn_token(copy.qr_token)

    copy.qr_token = token
    copy.qr_attached_at = timezone.now()
    copy.save(update_fields=["qr_token", "qr_attached_at"])
    pool.copy = copy
    pool.claimed_at = timezone.now()
    pool.save(update_fields=["copy", "claimed_at"])
    log_copy_event(
        copy.id,
        CopyEvent.Code.QR_ATTACHED,
        actor=acting_user,
        holder=acting_user,
        legal_owner=acting_user,
    )
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


def copy_has_bound_qr(copy: BookCopy | None) -> bool:
    """True after late-bind (glue + scan)."""
    return bool(copy and copy.qr_token and copy.qr_attached_at)


def require_bound_qr_scan(
    copy: BookCopy | None,
    payload: str | None,
    *,
    action: str = "підтвердження",
) -> None:
    """
    Rule: if the instance has a bound QR, the next library's receiving party
    must scan that label to confirm receive / return (and handoff give/receive).
    """
    if not copy_has_bound_qr(copy):
        if payload and copy and copy.qr_token:
            assert_qr_matches_copy(copy, payload)
        return
    if not payload:
        raise ExchangeInvalidState(
            f"Відскануйте QR-наклейку примірника для підтвердження ({action})."
        )
    assert_qr_matches_copy(copy, payload)


def require_qr_for_handoff(handoff: LoanHandoff, payload: str | None) -> None:
    """If label is attached, physical give/receive must scan that QR."""
    require_bound_qr_scan(handoff.copy, payload, action="передачі")


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
    owner: CustomUser,
    *,
    copy_ids: list[int] | None = None,
    page_count: int = 1,
) -> list[list[QrLabel]]:
    """
    Full A4 page(s) of exactly 36 unique *unbound* QR labels.
    Never writes BookCopy.qr_token — binding happens only on Скан QR (attach).
    """
    del copy_ids  # late binding: print is never per-copy
    pages_n = max(1, int(page_count or 1))
    slots = SLOTS_PER_A4_PAGE
    tokens = ensure_spare_qr_tokens(owner, slots * pages_n)
    labels = _labels_from_pool(tokens)
    return [labels[i : i + slots] for i in range(0, len(labels), slots)]


def serialize_copy_qr(copy: BookCopy) -> dict:
    """Public QR state: bound only after late-bind scan."""
    attached = bool(copy.qr_attached_at and copy.qr_token)
    return {
        "has_qr": attached,
        "qr_attached": attached,
        "qr_attached_at": (
            copy.qr_attached_at.isoformat() if attached and copy.qr_attached_at else None
        ),
        # Payload only after bind (and only to owner via serializer gate).
        "qr_payload": (
            qr_payload_for_token(copy.qr_token) if attached and copy.qr_token else None
        ),
        "requires_qr_scan": attached,
    }


# --- Compat aliases (old call sites) -----------------------------------------

def ensure_copy_qr(copy: BookCopy, acting_user: CustomUser) -> BookCopy:
    """No early bind. Kept for API compat — returns copy unchanged if owner."""
    if copy.owner_id != acting_user.id:
        raise ExchangeForbidden("QR може згенерувати лише власник примірника.")
    return copy


def ensure_owner_qr_tokens(
    owner: CustomUser, *, copy_ids: list[int] | None = None
) -> list[BookCopy]:
    """No early bind — list owner's copies without assigning tokens."""
    qs = BookCopy.objects.filter(owner=owner)
    if copy_ids:
        qs = qs.filter(pk__in=copy_ids)
    return list(qs.select_related("book").order_by("id"))


def paginate_labels_full_a4(
    labels: list[QrLabel], *, pad_partial_page: bool = True
) -> list[list[QrLabel | None]]:
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
