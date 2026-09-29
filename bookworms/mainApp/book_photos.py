"""Attach user-taken photos to a Book (manual add flow) with server-side crop."""
from __future__ import annotations

import io
import random
import time
from typing import Any

from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import IntegrityError

from .models import Book, BookPhoto

MAX_BOOK_PHOTOS = 8
MAX_PHOTO_BYTES = 8 * 1024 * 1024  # 8 MiB


def allocate_local_isbn() -> str:
    """
    Unique 13-digit code for books not in global catalogs / without ISBN.
    Uses 9799xxxxxxxxx private-style range (not looked up online).
    """
    for _ in range(30):
        isbn = f"9799{random.randint(0, 10**9 - 1):09d}"
        if not Book.objects.filter(isbn=isbn).exists():
            return isbn
    return f"9799{int(time.time() * 1000) % 10**9:09d}"


def _absolute_url(request, file_field) -> str:
    url = file_field.url
    if request is not None:
        try:
            return request.build_absolute_uri(url)
        except Exception:
            pass
    base = (getattr(settings, "PUBLIC_BASE_URL", "") or "").rstrip("/")
    if base:
        return f"{base}{url}"
    return url


def _trim_pil_background(img: Any) -> Any:
    """Strip near-uniform desk margins via edge row/col bg ratio."""
    from PIL import Image

    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    if w < 32 or h < 32:
        return img

    px = img.load()

    def corner_avg(cx: int, cy: int) -> tuple[float, float, float]:
        r = g = b = n = 0
        for dy in range(8):
            for dx in range(8):
                x = min(w - 1, max(0, cx + dx))
                y = min(h - 1, max(0, cy + dy))
                pr, pg, pb = px[x, y]
                r += pr
                g += pg
                b += pb
                n += 1
        return r / n, g / n, b / n

    c1 = corner_avg(1, 1)
    c2 = corner_avg(w - 9, 1)
    c3 = corner_avg(1, h - 9)
    c4 = corner_avg(w - 9, h - 9)
    br = (c1[0] + c2[0] + c3[0] + c4[0]) / 4
    bg = (c1[1] + c2[1] + c3[1] + c4[1]) / 4
    bb = (c1[2] + c2[2] + c3[2] + c4[2]) / 4
    thresh = 48

    def is_bg(x: int, y: int) -> bool:
        r, g, b = px[x, y]
        return (
            abs(r - br) < thresh and abs(g - bg) < thresh and abs(b - bb) < thresh
        )

    def row_bg_ratio(y: int) -> float:
        n = bg_n = 0
        for x in range(0, w, 2):
            n += 1
            if is_bg(x, y):
                bg_n += 1
        return bg_n / n if n else 1.0

    def col_bg_ratio(x: int, y0: int, y1: int) -> float:
        n = bg_n = 0
        for y in range(y0, y1 + 1, 2):
            n += 1
            if is_bg(x, y):
                bg_n += 1
        return bg_n / n if n else 1.0

    max_trim = int(min(w, h) * 0.42)
    bg_row = 0.78
    top = 0
    bottom = h - 1
    left = 0
    right = w - 1
    while top < max_trim and row_bg_ratio(top) >= bg_row:
        top += 1
    while bottom > h - 1 - max_trim and row_bg_ratio(bottom) >= bg_row:
        bottom -= 1
    while left < max_trim and col_bg_ratio(left, top, bottom) >= bg_row:
        left += 1
    while right > w - 1 - max_trim and col_bg_ratio(right, top, bottom) >= bg_row:
        right -= 1

    pad = max(2, int(min(w, h) * 0.008))
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(w - 1, right + pad)
    bottom = min(h - 1, bottom + pad)
    cw, ch = right - left + 1, bottom - top + 1
    if cw < 24 or ch < 24 or (cw >= w and ch >= h):
        return img
    return img.crop((left, top, right + 1, bottom + 1))


def process_book_upload(uploaded) -> InMemoryUploadedFile | Any:
    """
    Normalize upload to cropped JPEG of the book cover region.
    On failure returns the original upload unchanged.
    """
    try:
        from PIL import Image

        uploaded.seek(0)
        img = Image.open(uploaded)
        img = _trim_pil_background(img)
        if img.mode != "RGB":
            img = img.convert("RGB")
        # Cap long edge for storage
        max_edge = 1600
        w, h = img.size
        if max(w, h) > max_edge:
            img.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=88, optimize=True)
        buf.seek(0)
        base = (getattr(uploaded, "name", None) or "book.jpg").rsplit(".", 1)[0]
        name = f"{base[:40]}_cover.jpg"
        return InMemoryUploadedFile(
            buf,
            field_name="image",
            name=name,
            content_type="image/jpeg",
            size=buf.getbuffer().nbytes,
            charset=None,
        )
    except Exception:
        try:
            uploaded.seek(0)
        except Exception:
            pass
        return uploaded


def save_book_photos(book: Book, uploaded_files, request=None) -> list[BookPhoto]:
    """
    Crop + save up to MAX_BOOK_PHOTOS. Always sets cover_url from first photo
    when cover is empty (so library shows the shot without catalog ISBN lookup).
    """
    if not uploaded_files:
        return []

    existing = book.photos.count()
    room = max(0, MAX_BOOK_PHOTOS - existing)
    if room <= 0:
        return []

    saved: list[BookPhoto] = []
    for f in uploaded_files:
        if len(saved) >= room:
            break
        if not f or not getattr(f, "name", None):
            continue
        size = getattr(f, "size", 0) or 0
        if size < 0 or size > MAX_PHOTO_BYTES:
            continue
        content_type = (getattr(f, "content_type", "") or "").lower()
        if content_type and not (
            content_type.startswith("image/")
            or content_type in ("application/octet-stream", "")
        ):
            continue

        processed = process_book_upload(f)
        photo = BookPhoto(book=book, sort_order=existing + len(saved))
        photo.image.save(
            getattr(processed, "name", None) or f"book_{book.pk}_{len(saved)}.jpg",
            processed,
            save=True,
        )
        saved.append(photo)

    if saved and not (book.cover_url or "").strip():
        book.cover_url = _absolute_url(request, saved[0].image)[:500]
        book.save(update_fields=["cover_url"])

    return saved


def ensure_cover_from_photos(book: Book, request=None) -> None:
    if (book.cover_url or "").strip():
        return
    first = book.photos.order_by("sort_order", "id").first()
    if not first:
        return
    book.cover_url = _absolute_url(request, first.image)[:500]
    book.save(update_fields=["cover_url"])


def book_photo_urls(book: Book, request=None) -> list[str]:
    return [_absolute_url(request, p.image) for p in book.photos.all()]


def create_manual_book(
    *,
    isbn: str | None,
    title: str,
    authors: str = "",
    publisher: str = "",
    publish_date: str = "",
    cover_url: str = "",
    info_url: str = "",
) -> Book:
    """
    Create/update catalog Book without Open Library / ISBNdb.
    Empty ISBN → allocate local 9799… code.
    """
    from .book_lookup import normalize_isbn
    from .exchange.catalog import get_or_create_book_from_payload

    raw = (isbn or "").strip()
    norm = normalize_isbn(raw) if raw else None
    if not norm:
        # retry allocate on rare collision
        for _ in range(5):
            norm = allocate_local_isbn()
            if not Book.objects.filter(isbn=norm).exists():
                break
    title_clean = (title or "").strip() or "Книга (локальний запис)"
    payload = {
        "isbn": norm,
        "title": title_clean,
        "authors": (authors or "").strip(),
        "publisher": (publisher or "").strip(),
        "publish_date": (publish_date or "").strip(),
        "cover_url": (cover_url or "").strip(),
        "info_url": (info_url or "").strip(),
    }
    try:
        book, _ = get_or_create_book_from_payload(payload)
    except IntegrityError:
        payload["isbn"] = allocate_local_isbn()
        book, _ = get_or_create_book_from_payload(payload)
    return book
