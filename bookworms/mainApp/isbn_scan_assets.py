"""Serve ISBN scanner JS from app package (bypasses stale Docker staticfiles volume)."""
from __future__ import annotations

from pathlib import Path

from django.http import Http404, HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

_JS_DIR = Path(__file__).resolve().parent / "static" / "js"

_FILES = {
    "isbn_scan.js": "isbn_scan.js",
    "isbn_scan_worker.js": "isbn_scan_worker.js",
    "zxing-0.21.3.min.js": "zxing-0.21.3.min.js",
    "manual_book_photos.js": "manual_book_photos.js",
}


@never_cache
@require_GET
def isbn_scan_asset(request, name: str):
    filename = _FILES.get(name)
    if not filename:
        raise Http404()
    path = _JS_DIR / filename
    if not path.is_file():
        raise Http404(filename)
    data = path.read_bytes()
    resp = HttpResponse(data, content_type="application/javascript; charset=utf-8")
    resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp["Pragma"] = "no-cache"
    return resp
