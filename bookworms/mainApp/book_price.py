"""
ISBN market price evaluation from public internet sources
(Google Books regional markets + Apple Books / iTunes storefronts).

Rules:
  - min 3, max 10 quotes with prices
  - first run when a copy is added; later only on explicit user refresh
  - local 9799… ISBNs are skipped (no catalog price)
"""
from __future__ import annotations

import json
import logging
import os
import statistics
import threading
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.db import transaction
from django.utils import timezone

from .book_photos import is_local_isbn
from .models import Book, BookPriceEvaluation, BookPriceQuote

logger = logging.getLogger(__name__)

MIN_SOURCES = 3
MAX_SOURCES = 10

# Approximate FX → UAH (override via settings.BOOK_PRICE_FX if needed)
_DEFAULT_FX = {
    "UAH": Decimal("1"),
    "USD": Decimal("41.50"),
    "EUR": Decimal("45.00"),
    "GBP": Decimal("52.50"),
    "PLN": Decimal("10.40"),
    "CZK": Decimal("1.80"),
    "CAD": Decimal("30.00"),
    "AUD": Decimal("27.00"),
    "CHF": Decimal("47.00"),
    "JPY": Decimal("0.28"),
    "INR": Decimal("0.50"),
    "BRL": Decimal("7.20"),
    "SEK": Decimal("3.90"),
    "NOK": Decimal("3.80"),
    "DKK": Decimal("6.00"),
    "HUF": Decimal("0.11"),
    "RON": Decimal("9.00"),
    "TRY": Decimal("1.20"),
    "MXN": Decimal("2.10"),
}

# Google Books marketplace regions (each counts as a source when priced)
_GB_MARKETS = (
    ("US", "Google Books (US)"),
    ("GB", "Google Books (UK)"),
    ("DE", "Google Books (DE)"),
    ("FR", "Google Books (FR)"),
    ("PL", "Google Books (PL)"),
    ("UA", "Google Books (UA)"),
    ("IT", "Google Books (IT)"),
    ("ES", "Google Books (ES)"),
    ("CA", "Google Books (CA)"),
    ("AU", "Google Books (AU)"),
)

# Apple Books / iTunes storefronts (lookup by ISBN)
_APPLE_STORES = (
    ("us", "Apple Books (US)"),
    ("gb", "Apple Books (UK)"),
    ("de", "Apple Books (DE)"),
    ("fr", "Apple Books (FR)"),
    ("pl", "Apple Books (PL)"),
    ("ua", "Apple Books (UA)"),
    ("it", "Apple Books (IT)"),
    ("es", "Apple Books (ES)"),
    ("ca", "Apple Books (CA)"),
    ("au", "Apple Books (AU)"),
)

_lock_guard = threading.Lock()
_running: set[int] = set()


def _fx_table() -> dict[str, Decimal]:
    try:
        from django.conf import settings

        custom = getattr(settings, "BOOK_PRICE_FX", None) or {}
    except Exception:
        custom = {}
    out = dict(_DEFAULT_FX)
    for k, v in custom.items():
        try:
            out[str(k).upper()] = Decimal(str(v))
        except (InvalidOperation, TypeError, ValueError):
            continue
    return out


def to_uah(amount: Decimal, currency: str) -> Decimal | None:
    cur = (currency or "USD").upper().strip()
    rate = _fx_table().get(cur)
    if rate is None:
        return None
    try:
        return (amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError):
        return None


def _http_json(url: str, timeout: float = 12.0) -> Any:
    req = Request(
        url,
        headers={
            "User-Agent": "DateDueSlipBookPrice/1.0 (+library eval)",
            "Accept": "application/json",
        },
        method="GET",
    )
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def _parse_money(obj: dict | None) -> tuple[Decimal, str] | None:
    if not isinstance(obj, dict):
        return None
    amount = obj.get("amount")
    currency = (obj.get("currencyCode") or obj.get("currency") or "").upper()
    if amount is None or not currency:
        return None
    try:
        dec = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if dec <= 0:
        return None
    return dec, currency


def _quote(
    *,
    source_name: str,
    source_url: str,
    price: Decimal,
    currency: str,
) -> dict | None:
    uah = to_uah(price, currency)
    if uah is None:
        return None
    return {
        "source_name": source_name,
        "source_url": (source_url or "")[:500],
        "price": price,
        "currency": currency,
        "price_uah": uah,
    }


def _google_api_key() -> str:
    key = (os.environ.get("GOOGLE_BOOKS_API_KEY") or "").strip()
    if key:
        return key
    try:
        from django.conf import settings

        return (getattr(settings, "GOOGLE_BOOKS_API_KEY", "") or "").strip()
    except Exception:
        return ""


def fetch_google_books_market(isbn: str, country: str, label: str) -> list[dict]:
    """Google Books marketplace quotes (retail and/or list when both differ)."""
    q = quote(f"isbn:{isbn}")
    url = (
        f"https://www.googleapis.com/books/v1/volumes"
        f"?q={q}&country={quote(country)}&maxResults=1"
    )
    key = _google_api_key()
    if key:
        url += f"&key={quote(key)}"
    try:
        data = _http_json(url)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.debug("google books %s fail: %s", country, exc)
        return []
    items = data.get("items") or []
    if not items:
        return []
    vol = items[0]
    info = vol.get("volumeInfo") or {}
    sale = vol.get("saleInfo") or {}
    link = (
        info.get("infoLink")
        or sale.get("buyLink")
        or vol.get("selfLink")
        or f"https://books.google.com/books?vid=ISBN{isbn}"
    )
    out: list[dict] = []
    retail = _parse_money(sale.get("retailPrice"))
    listed = _parse_money(sale.get("listPrice"))
    if retail:
        qot = _quote(
            source_name=f"{label} retail",
            source_url=link,
            price=retail[0],
            currency=retail[1],
        )
        if qot:
            out.append(qot)
    if listed and (not retail or listed != retail):
        qot = _quote(
            source_name=f"{label} list",
            source_url=link,
            price=listed[0],
            currency=listed[1],
        )
        if qot:
            out.append(qot)
    return out


def fetch_apple_books(isbn: str, country: str, label: str) -> dict | None:
    """Apple Books / iTunes lookup price for ISBN in a storefront."""
    url = (
        f"https://itunes.apple.com/lookup"
        f"?isbn={quote(isbn)}&country={quote(country)}"
    )
    try:
        data = _http_json(url)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.debug("apple books %s fail: %s", country, exc)
        return None
    results = data.get("results") or []
    if not results:
        # fallback: search by ISBN term (ebooks)
        surl = (
            f"https://itunes.apple.com/search"
            f"?term={quote(isbn)}&country={quote(country)}"
            f"&entity=ebook&limit=5"
        )
        try:
            data = _http_json(surl)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
            return None
        results = data.get("results") or []
    for item in results:
        price = item.get("price")
        currency = (item.get("currency") or "").upper()
        if price is None or not currency:
            continue
        try:
            amount = Decimal(str(price))
        except (InvalidOperation, TypeError, ValueError):
            continue
        if amount <= 0:
            continue
        link = item.get("trackViewUrl") or item.get("collectionViewUrl") or ""
        return _quote(
            source_name=label,
            source_url=link,
            price=amount,
            currency=currency,
        )
    return None


def fetch_pangobooks(isbn: str) -> list[dict]:
    """
    PangoBooks public pricing API — retail + distinct recent marketplace sales.
    Free, no auth. Each distinct sold price counts as a separate internet source.
    """
    url = f"https://pangobooks.com/api/public/pricing?isbn={quote(isbn)}"
    try:
        data = _http_json(url)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.debug("pangobooks fail: %s", exc)
        return []
    if not isinstance(data, dict) or not data.get("success"):
        return []
    payload = data.get("data") or {}
    market = payload.get("market") or {}
    link = f"https://pangobooks.com/pricing?isbn={quote(isbn)}"
    out: list[dict] = []

    retail = market.get("retail_price_usd")
    if retail is not None:
        try:
            amount = Decimal(str(retail))
        except (InvalidOperation, TypeError, ValueError):
            amount = None
        if amount and amount > 0:
            q = _quote(
                source_name="PangoBooks retail",
                source_url=link,
                price=amount,
                currency="USD",
            )
            if q:
                out.append(q)

    median = market.get("median_price_usd")
    if median is not None:
        try:
            amount = Decimal(str(median))
        except (InvalidOperation, TypeError, ValueError):
            amount = None
        if amount and amount > 0:
            q = _quote(
                source_name="PangoBooks market median",
                source_url=link,
                price=amount,
                currency="USD",
            )
            if q:
                out.append(q)

    seen_sale: set[str] = set()
    for sale in payload.get("recent_sales") or []:
        if len(out) >= MAX_SOURCES:
            break
        price = sale.get("price_usd")
        if price is None:
            continue
        try:
            amount = Decimal(str(price))
        except (InvalidOperation, TypeError, ValueError):
            continue
        if amount <= 0:
            continue
        key = str(amount)
        if key in seen_sale:
            continue
        seen_sale.add(key)
        cond = (sale.get("condition") or "sold").strip() or "sold"
        q = _quote(
            source_name=f"PangoBooks sold ({cond})",
            source_url=link,
            price=amount,
            currency="USD",
        )
        if q:
            out.append(q)
    return out


def collect_quotes(isbn: str) -> list[dict]:
    """Fetch up to MAX_SOURCES priced quotes from internet markets."""
    found: list[dict] = []
    seen_keys: set[tuple[str, str, str]] = set()

    def _add(q: dict | None) -> bool:
        if not q or len(found) >= MAX_SOURCES:
            return len(found) >= MAX_SOURCES
        key = (q["source_name"], str(q["price"]), q["currency"])
        if key in seen_keys:
            return False
        seen_keys.add(key)
        found.append(q)
        return len(found) >= MAX_SOURCES

    # 1) PangoBooks — often yields several marketplace comps quickly
    for q in fetch_pangobooks(isbn):
        if _add(q):
            return found

    # 2/3) Interleave Google + Apple for additional diversity
    n = max(len(_GB_MARKETS), len(_APPLE_STORES))
    for i in range(n):
        if len(found) >= MAX_SOURCES:
            break
        if i < len(_GB_MARKETS):
            country, label = _GB_MARKETS[i]
            for q in fetch_google_books_market(isbn, country, label):
                if _add(q):
                    return found
            time.sleep(0.25)
        if len(found) >= MAX_SOURCES:
            break
        if i < len(_APPLE_STORES):
            country, label = _APPLE_STORES[i]
            _add(fetch_apple_books(isbn, country, label))
            time.sleep(0.2)
    return found


def evaluate_book_price(book_id: int, *, force: bool = False) -> BookPriceEvaluation | None:
    """
    Run evaluation for book. If force=False and a finished eval exists, skip.
    """
    book = Book.objects.filter(pk=book_id).first()
    if not book:
        return None
    if is_local_isbn(book.isbn):
        ev, _ = BookPriceEvaluation.objects.get_or_create(book=book)
        ev.status = BookPriceEvaluation.Status.MISSING
        ev.price_avg = ev.price_min = ev.price_max = None
        ev.source_count = 0
        ev.last_error = "Локальний ISBN — немає каталожних цін."
        ev.evaluated_at = timezone.now()
        ev.save()
        BookPriceQuote.objects.filter(evaluation=ev).delete()
        return ev

    with _lock_guard:
        if book_id in _running and not force:
            return BookPriceEvaluation.objects.filter(book_id=book_id).first()
        _running.add(book_id)

    try:
        ev, _ = BookPriceEvaluation.objects.get_or_create(book=book)
        if (
            not force
            and ev.status
            in (
                BookPriceEvaluation.Status.READY,
                BookPriceEvaluation.Status.MISSING,
                BookPriceEvaluation.Status.ERROR,
            )
            and ev.evaluated_at
        ):
            return ev

        ev.status = BookPriceEvaluation.Status.PENDING
        ev.last_error = ""
        ev.save(update_fields=["status", "last_error", "updated_at"])

        try:
            quotes = collect_quotes(book.isbn)
        except Exception as exc:
            logger.exception("price eval failed book=%s", book_id)
            ev.status = BookPriceEvaluation.Status.ERROR
            ev.last_error = str(exc)[:500]
            ev.evaluated_at = timezone.now()
            ev.source_count = 0
            ev.price_avg = ev.price_min = ev.price_max = None
            ev.save()
            BookPriceQuote.objects.filter(evaluation=ev).delete()
            return ev

        with transaction.atomic():
            BookPriceQuote.objects.filter(evaluation=ev).delete()
            if len(quotes) < MIN_SOURCES:
                ev.status = BookPriceEvaluation.Status.MISSING
                ev.price_avg = ev.price_min = ev.price_max = None
                ev.source_count = len(quotes)
                ev.last_error = (
                    f"Знайдено лише {len(quotes)} джерел (потрібно ≥ {MIN_SOURCES})."
                    if quotes
                    else "Ціну за ISBN не знайдено в інтернет-джерелах."
                )
                # Still store partial quotes for transparency
                for q in quotes:
                    BookPriceQuote.objects.create(
                        evaluation=ev,
                        source_name=q["source_name"],
                        source_url=q.get("source_url") or "",
                        price=q["price"],
                        currency=q["currency"],
                        price_uah=q["price_uah"],
                    )
            else:
                uah_vals = [q["price_uah"] for q in quotes]
                med = Decimal(str(statistics.median(uah_vals))).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                ev.status = BookPriceEvaluation.Status.READY
                ev.currency = "UAH"
                ev.price_avg = med
                ev.price_min = min(uah_vals)
                ev.price_max = max(uah_vals)
                ev.source_count = len(quotes)
                ev.last_error = ""
                for q in quotes:
                    BookPriceQuote.objects.create(
                        evaluation=ev,
                        source_name=q["source_name"],
                        source_url=q.get("source_url") or "",
                        price=q["price"],
                        currency=q["currency"],
                        price_uah=q["price_uah"],
                    )
            ev.evaluated_at = timezone.now()
            ev.save()
        return ev
    finally:
        with _lock_guard:
            _running.discard(book_id)


def schedule_book_price_evaluation(book_id: int, *, force: bool = False) -> None:
    """Fire-and-forget background evaluation (daemon thread)."""

    def _run():
        try:
            evaluate_book_price(book_id, force=force)
        except Exception:
            logger.exception("background price eval book=%s", book_id)

    # non-daemon: shell/backfill must not kill mid-fetch when the parent exits
    threading.Thread(
        target=_run, name=f"book-price-{book_id}", daemon=False
    ).start()


def ensure_pending_and_schedule(book: Book, *, force: bool = False) -> BookPriceEvaluation | None:
    """Create pending row (if needed) and schedule fetch. Skip local ISBN sync-eval."""
    if is_local_isbn(book.isbn):
        return evaluate_book_price(book.pk, force=True)

    ev, created = BookPriceEvaluation.objects.get_or_create(book=book)
    if not force and not created:
        if ev.status == BookPriceEvaluation.Status.PENDING:
            # already in progress (or stuck) — kick again if not locked
            schedule_book_price_evaluation(book.pk, force=False)
            return ev
        if ev.evaluated_at and ev.status in (
            BookPriceEvaluation.Status.READY,
            BookPriceEvaluation.Status.MISSING,
            BookPriceEvaluation.Status.ERROR,
        ):
            return ev

    ev.status = BookPriceEvaluation.Status.PENDING
    ev.last_error = ""
    ev.save(update_fields=["status", "last_error", "updated_at"])
    schedule_book_price_evaluation(book.pk, force=True)
    return ev


def serialize_evaluation(ev: BookPriceEvaluation | None) -> dict | None:
    if not ev:
        return None
    quotes = [
        {
            "source_name": q.source_name,
            "source_url": q.source_url,
            "price": str(q.price),
            "currency": q.currency,
            "price_uah": str(q.price_uah),
        }
        for q in ev.quotes.all()
    ]
    return {
        "status": ev.status,
        "currency": ev.currency,
        "price_avg": str(ev.price_avg) if ev.price_avg is not None else None,
        "price_min": str(ev.price_min) if ev.price_min is not None else None,
        "price_max": str(ev.price_max) if ev.price_max is not None else None,
        "source_count": ev.source_count,
        "evaluated_at": ev.evaluated_at.isoformat() if ev.evaluated_at else None,
        "last_error": ev.last_error or "",
        "quotes": quotes,
    }


def library_price_total_uah(evaluations: list[BookPriceEvaluation]) -> Decimal:
    total = Decimal("0.00")
    for ev in evaluations:
        if ev.status == BookPriceEvaluation.Status.READY and ev.price_avg is not None:
            total += ev.price_avg
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
