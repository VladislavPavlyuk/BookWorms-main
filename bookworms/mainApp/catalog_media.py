"""Persist catalog cover images into local MEDIA (no hot-linking after ingest)."""
from __future__ import annotations

import logging
import mimetypes
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from .models import Book

logger = logging.getLogger("mainApp.catalog_media")

_MAX_BYTES = 8 * 1024 * 1024
# OL often returns a ~43-byte blank GIF for missing covers — never store those.
_MIN_BYTES = 2048
_UA = "BookWormsCatalogMirror/1"


def is_remote_http_url(url: str | None) -> bool:
    u = (url or "").strip().lower()
    return u.startswith("http://") or u.startswith("https://")


def is_local_media_url(url: str | None) -> bool:
    u = (url or "").strip()
    if not u:
        return False
    if u.startswith("/media/"):
        return True
    if "/media/" in u:
        return True
    media = (getattr(settings, "MEDIA_URL", "") or "").rstrip("/")
    if media and media in u:
        return True
    return False


def to_relative_media_url(url: str | None) -> str | None:
    """
    If url points at local MEDIA, return path-only ``/media/...``.
    Otherwise return None (caller keeps original — e.g. external hot-link).
    """
    u = (url or "").strip()
    if not u:
        return ""
    if u.startswith("/media/"):
        return u.split("?", 1)[0][:500]
    # http(s)://host/media/... or accidental host-less media/...
    idx = u.find("/media/")
    if idx >= 0:
        return u[idx:].split("?", 1)[0][:500]
    media = (getattr(settings, "MEDIA_URL", "") or "").strip()
    if media and not media.startswith("/") and media in u:
        # unusual
        pass
    return None


def media_url_for_request(url: str | None, request=None) -> str:
    """Expand relative /media/... for API/RN; leave external URLs alone."""
    u = (url or "").strip()
    if not u:
        return ""
    rel = to_relative_media_url(u)
    if rel is None:
        return u[:500]
    if request is not None:
        try:
            return request.build_absolute_uri(rel)[:500]
        except Exception:
            pass
    base = (getattr(settings, "PUBLIC_BASE_URL", "") or "").rstrip("/")
    if base:
        return f"{base}{rel}"[:500]
    return rel[:500]


def _media_store_url(storage_path: str) -> str:
    """Path-only URL stored on Book.cover_url (Safari-safe on HTTPS pages)."""
    rel = default_storage.url(storage_path)
    if rel.startswith("http://") or rel.startswith("https://"):
        converted = to_relative_media_url(rel)
        return (converted or rel)[:500]
    if not rel.startswith("/"):
        rel = "/" + rel
    return rel[:500]


def _ext_from_content_type(ct: str | None, url: str) -> str:
    ct = (ct or "").split(";")[0].strip().lower()
    map_ct = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/gif": "gif",
    }
    if ct in map_ct:
        return map_ct[ct]
    guess, _ = mimetypes.guess_type(url)
    if guess in map_ct:
        return map_ct[guess]
    path = url.split("?", 1)[0]
    m = re.search(r"\.(jpe?g|png|webp|gif)$", path, re.I)
    if m:
        ext = m.group(1).lower()
        return "jpg" if ext == "jpeg" else ext
    return "jpg"


def _catalog_cover_path(book: Book, ext: str) -> str:
    isbn = re.sub(r"[^0-9Xx]", "", (book.isbn or "")) or f"id{book.pk}"
    return f"catalog_covers/{isbn}.{ext}"


def _download(url: str) -> tuple[bytes, str]:
    req = Request(url, headers={"User-Agent": _UA, "Accept": "image/*,*/*"})
    with urlopen(req, timeout=20) as resp:
        ct = resp.headers.get("Content-Type")
        data = resp.read(_MAX_BYTES + 1)
    if len(data) > _MAX_BYTES:
        raise ValueError("cover too large")
    if not data:
        raise ValueError("empty cover")
    if len(data) < _MIN_BYTES:
        # Classic OL missing-cover placeholder is a 43-byte GIF.
        raise ValueError(f"cover too small ({len(data)} bytes) — likely placeholder")
    # Reject non-image bodies (HTML error pages, JSON, …)
    head = data[:32]
    if head.lstrip().startswith((b"<", b"{", b"[")):
        raise ValueError(f"not an image (content-type={ct!r})")
    ct0 = (ct or "").split(";")[0].strip().lower()
    if ct0 and not ct0.startswith("image/") and ct0 not in ("application/octet-stream",):
        raise ValueError(f"not an image (content-type={ct!r})")
    return data, _ext_from_content_type(ct, url)


def _cover_quality(url: str) -> int:
    """
    Higher = better download candidate.
    Demote ISBNdb-style temporary «original» URLs — they expire ~2h and were
    winning the sort, then failing → covers wiped on refresh.
    """
    u = (url or "").strip().lower()
    if not u:
        return -1
    score = 0
    if u.startswith("https://"):
        score += 10
    # Prefer large/stable catalog CDN sizes over ephemeral «original» links.
    if "-l.jpg" in u or "/large/" in u:
        score += 50
    elif "-m.jpg" in u or "/medium/" in u:
        score += 25
    elif "-s.jpg" in u or "/small/" in u:
        score += 5
    if "original" in u:
        # Try later as a high-res bonus only after stable URLs fail.
        score -= 20
    # OL /b/isbn/… often 404s into a tiny blank GIF — prefer /b/id/ or ISBNdb.
    if "covers.openlibrary.org/b/isbn/" in u:
        score -= 40
    if "images.isbndb.com" in u:
        score += 15
    score += min(len(u), 200) // 40
    return score


def persist_catalog_cover(
    book: Book,
    remote_url: str | None = None,
    *,
    force: bool = False,
    candidates: list[str] | None = None,
    keep_local_on_fail: str | None = None,
) -> bool:
    """
    Download the best available remote cover into MEDIA and point book.cover_url
    at it. On failure during force-refresh, preserve keep_local_on_fail / current
    local cover — never leave a broken hot-link in cover_url.
    """
    urls: list[str] = []
    for u in list(candidates or []) + [
        remote_url or "",
        book.cover_url_original or "",
        book.cover_url if is_remote_http_url(book.cover_url) else "",
    ]:
        s = (u or "").strip()
        if is_remote_http_url(s) and s not in urls:
            urls.append(s)
    urls.sort(key=_cover_quality, reverse=True)

    def _usable_local(url: str) -> str:
        """Keep only local MEDIA covers that are real images (not OL blank GIF)."""
        u = (url or "").strip()
        if not is_local_media_url(u):
            return ""
        # Resolve storage path from common catalog_covers naming.
        m = re.search(r"catalog_covers/([^/?#]+)$", u)
        if m:
            rel = f"catalog_covers/{m.group(1)}"
            try:
                if default_storage.exists(rel):
                    with default_storage.open(rel, "rb") as fh:
                        if len(fh.read(_MIN_BYTES + 1)) < _MIN_BYTES:
                            return ""  # placeholder — do not preserve
            except Exception:
                pass
        return u

    preserved = _usable_local(keep_local_on_fail or "")
    current = (book.cover_url or "").strip()
    if not preserved:
        preserved = _usable_local(current)

    if not urls:
        return False

    if is_local_media_url(current) and not force:
        fields: list[str] = []
        best_remote = urls[0][:500]
        if not (book.cover_url_original or "").strip():
            book.cover_url_original = best_remote
            fields.append("cover_url_original")
        if fields:
            book.save(update_fields=fields)
        return False

    data: bytes | None = None
    ext = "jpg"
    remote = urls[0]
    last_exc: Exception | None = None
    for candidate in urls:
        try:
            data, ext = _download(candidate)
            remote = candidate
            break
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
            last_exc = exc
            logger.warning(
                "catalog_cover.mirror_try_fail book=%s url=%s err=%s",
                book.pk,
                candidate[:120],
                exc,
            )

    if data is None:
        logger.warning(
            "catalog_cover.mirror_fail book=%s tried=%s err=%s keep_local=%s",
            book.pk,
            len(urls),
            last_exc,
            bool(preserved),
        )
        fields: list[str] = []
        # Stash best remote for debugging / next attempt — do not point cover_url at it.
        fallback = urls[0][:500]
        if (book.cover_url_original or "") != fallback:
            book.cover_url_original = fallback
            fields.append("cover_url_original")
        if preserved and (book.cover_url or "") != preserved:
            book.cover_url = preserved
            fields.append("cover_url")
        elif not preserved and not is_local_media_url(book.cover_url):
            # No prior local: only then expose remote as last resort.
            if (book.cover_url or "") != fallback:
                book.cover_url = fallback
                fields.append("cover_url")
        if fields:
            book.save(update_fields=fields)
        return False

    path = _catalog_cover_path(book, ext)
    stem = re.sub(r"[^0-9Xx]", "", (book.isbn or "")) or f"id{book.pk}"
    # Refuse to replace an existing larger local cover with a worse download.
    if force and preserved:
        try:
            # local path from MEDIA url
            for old_ext in ("jpg", "jpeg", "png", "webp", "gif"):
                old = f"catalog_covers/{stem}.{old_ext}"
                if default_storage.exists(old):
                    with default_storage.open(old, "rb") as fh:
                        old_size = len(fh.read(_MAX_BYTES + 1))
                    if old_size >= _MIN_BYTES and len(data) < old_size * 0.5:
                        logger.warning(
                            "catalog_cover.skip_worse book=%s old=%s new=%s",
                            book.pk,
                            old_size,
                            len(data),
                        )
                        if (book.cover_url or "") != preserved:
                            book.cover_url = preserved
                            book.save(update_fields=["cover_url"])
                        return False
                    break
        except Exception:
            pass

    # `data` already in memory — safe to replace on-disk file now.
    try:
        if default_storage.exists(path):
            default_storage.delete(path)
        default_storage.save(path, ContentFile(data))
    except Exception as exc:
        logger.warning(
            "catalog_cover.store_fail book=%s path=%s err=%s",
            book.pk,
            path,
            exc,
        )
        if preserved and (book.cover_url or "") != preserved:
            book.cover_url = preserved
            book.save(update_fields=["cover_url"])
        return False

    for old_ext in ("jpg", "jpeg", "png", "webp", "gif"):
        old = f"catalog_covers/{stem}.{old_ext}"
        if old != path and default_storage.exists(old):
            try:
                default_storage.delete(old)
            except Exception:
                pass

    local_url = _media_store_url(path)
    fields = []
    if (book.cover_url or "") != local_url:
        book.cover_url = local_url
        fields.append("cover_url")
    if (book.cover_url_original or "") != remote[:500]:
        book.cover_url_original = remote[:500]
        fields.append("cover_url_original")
    if fields:
        book.save(update_fields=fields)
    logger.info(
        "catalog_cover.mirrored book=%s isbn=%s path=%s from=%s",
        book.pk,
        book.isbn,
        path,
        remote[:120],
    )
    return True
