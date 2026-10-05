"""Client analytics: UA parse, IP geo, Accept-Language, hit recording."""
from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from django.core.cache import cache
from django.db.models import Count, F
from django.utils import timezone

logger = logging.getLogger(__name__)

GEO_CACHE_TTL = 60 * 60 * 24 * 14  # 14 days
HIT_THROTTLE_SECONDS = 300  # refresh profile at most every 5 min per user


@dataclass(frozen=True)
class ParsedUA:
    device_type: str  # mobile | tablet | desktop | bot | unknown
    device_brand: str
    os_family: str
    os_version: str
    browser_family: str


def client_ip(request) -> str:
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    if forwarded:
        return forwarded[:64]
    real = (request.META.get("HTTP_X_REAL_IP") or "").strip()
    if real:
        return real[:64]
    return (request.META.get("REMOTE_ADDR") or "")[:64]


def _is_private_ip(ip: str) -> bool:
    if not ip or ip in ("127.0.0.1", "::1", "unknown"):
        return True
    if ip.startswith("10.") or ip.startswith("192.168.") or ip.startswith("172."):
        return True
    if ip.startswith("fc") or ip.startswith("fd") or ip.startswith("fe80"):
        return True
    return False


def parse_accept_language(header: str | None) -> tuple[str, str]:
    """Return (primary_code, raw_truncated)."""
    raw = (header or "").strip()[:255]
    if not raw:
        return "", ""
    primary = raw.split(",", 1)[0].strip().split(";", 1)[0].strip().lower()
    # uk-UA → uk
    if "-" in primary:
        primary = primary.split("-", 1)[0]
    return primary[:16], raw


def parse_user_agent(ua: str | None) -> ParsedUA:
    text = ua or ""
    low = text.lower()

    if any(b in low for b in ("bot", "crawl", "spider", "slurp", "bingpreview")):
        return ParsedUA("bot", "", "Bot", "", "Bot")

    device_type = "desktop"
    if "ipad" in low or "tablet" in low or ("android" in low and "mobile" not in low):
        device_type = "tablet"
    elif any(
        x in low
        for x in (
            "mobile",
            "iphone",
            "ipod",
            "android",
            "okhttp",
            "expo",
            "reactnative",
            "cfnetwork",
        )
    ):
        device_type = "mobile"

    brand = ""
    if "iphone" in low or "ipad" in low or "ipod" in low:
        brand = "Apple"
    elif "samsung" in low:
        brand = "Samsung"
    elif "huawei" in low:
        brand = "Huawei"
    elif "xiaomi" in low or "redmi" in low or "poco" in low:
        brand = "Xiaomi"
    elif "pixel" in low:
        brand = "Google"

    os_family = "Unknown"
    os_version = ""
    if "android" in low:
        os_family = "Android"
        m = re.search(r"android[/\s]([\d.]+)", low)
        os_version = m.group(1) if m else ""
    elif "iphone" in low or "ipad" in low or "ipod" in low or "ios" in low:
        os_family = "iOS"
        m = re.search(r"(?:cpu iphone os|cpu os|iphone os)[/\s_]*([\d_]+)", low)
        if m:
            os_version = m.group(1).replace("_", ".")
    elif "windows phone" in low:
        os_family = "Windows Phone"
    elif "windows" in low:
        os_family = "Windows"
        if "windows nt 10" in low:
            os_version = "10/11"
        elif "windows nt 6.3" in low:
            os_version = "8.1"
        elif "windows nt 6.1" in low:
            os_version = "7"
    elif "mac os x" in low or "macintosh" in low:
        os_family = "macOS"
        m = re.search(r"mac os x[/\s_]*([\d_]+)", low)
        if m:
            os_version = m.group(1).replace("_", ".")
    elif "cros" in low:
        os_family = "Chrome OS"
    elif "linux" in low:
        os_family = "Linux"
    elif "okhttp" in low or "dalvik" in low:
        os_family = "Android"
        device_type = "mobile"
    elif "cfnetwork" in low or "darwin" in low:
        os_family = "iOS"
        device_type = device_type if device_type != "desktop" else "mobile"

    browser = "Unknown"
    if "edg/" in low or "edge/" in low:
        browser = "Edge"
    elif "firefox/" in low or "fxios" in low:
        browser = "Firefox"
    elif "opr/" in low or "opera" in low:
        browser = "Opera"
    elif "samsungbrowser" in low:
        browser = "Samsung Internet"
    elif "chrome/" in low or "crios/" in low:
        browser = "Chrome"
    elif "safari/" in low and "chrome" not in low:
        browser = "Safari"
    elif "okhttp" in low or "expo" in low or "reactnative" in low:
        browser = "App"

    return ParsedUA(device_type, brand, os_family, os_version[:32], browser)


def lookup_geo(ip: str) -> dict:
    """Country/city via ip-api.com (cached). Empty dict for private/failed."""
    if _is_private_ip(ip):
        return {}
    cache_key = f"geoip:v1:{ip}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result: dict = {}
    try:
        url = (
            f"http://ip-api.com/json/{ip}"
            f"?fields=status,country,countryCode,regionName,city,query"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "BookWormsAnalytics/1"})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        if data.get("status") == "success":
            result = {
                "country": (data.get("country") or "")[:64],
                "country_code": (data.get("countryCode") or "")[:8],
                "region": (data.get("regionName") or "")[:64],
                "city": (data.get("city") or "")[:64],
            }
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.debug("geo lookup failed for %s: %s", ip, exc)

    cache.set(cache_key, result, GEO_CACHE_TTL)
    return result


def record_client_hit(request, user) -> None:
    """Upsert UserClientProfile for authenticated user (throttled)."""
    if not user or not getattr(user, "is_authenticated", False) or not user.is_active:
        return
    if getattr(user, "is_anonymous", False):
        return

    throttle_key = f"analytics:hit:{user.pk}"
    if cache.get(throttle_key):
        return
    cache.set(throttle_key, 1, HIT_THROTTLE_SECONDS)

    from .models import UserClientProfile

    ua = (request.META.get("HTTP_USER_AGENT") or "")[:512]
    lang_code, lang_raw = parse_accept_language(request.META.get("HTTP_ACCEPT_LANGUAGE"))
    parsed = parse_user_agent(ua)
    ip = client_ip(request)

    defaults = {
        "last_ip": ip,
        "user_agent": ua,
        "device_type": parsed.device_type,
        "device_brand": parsed.device_brand,
        "os_family": parsed.os_family,
        "os_version": parsed.os_version,
        "browser_family": parsed.browser_family,
        "language_code": lang_code,
        "accept_language": lang_raw,
        "last_seen_at": timezone.now(),
    }

    profile, created = UserClientProfile.objects.get_or_create(
        user_id=user.pk, defaults={**defaults, "first_seen_at": timezone.now(), "hit_count": 1}
    )
    if created:
        # Geo after create
        geo = lookup_geo(ip)
        if geo:
            UserClientProfile.objects.filter(pk=profile.pk).update(**geo)
        return

    update = {**defaults}
    if ip and ip != profile.last_ip:
        geo = lookup_geo(ip)
        update.update(
            {
                "country": geo.get("country", "") or profile.country,
                "country_code": geo.get("country_code", "") or profile.country_code,
                "region": geo.get("region", "") or profile.region,
                "city": geo.get("city", "") or profile.city,
            }
        )
    elif not profile.country and ip:
        geo = lookup_geo(ip)
        update.update(
            {
                "country": geo.get("country", ""),
                "country_code": geo.get("country_code", ""),
                "region": geo.get("region", ""),
                "city": geo.get("city", ""),
            }
        )

    UserClientProfile.objects.filter(pk=profile.pk).update(
        **update, hit_count=F("hit_count") + 1
    )


def analytics_summary() -> dict:
    """Aggregations for admin dashboard (unique users by latest profile)."""
    from .models import UserClientProfile

    qs = UserClientProfile.objects.all()
    total = qs.count()

    def top(field: str, limit: int = 20):
        rows = (
            qs.exclude(**{f"{field}__exact": ""})
            .values(field)
            .annotate(n=Count("id"))
            .order_by("-n")[:limit]
        )
        return [{"label": r[field] or "—", "n": r["n"]} for r in rows]

    devices = (
        qs.values("device_type")
        .annotate(n=Count("id"))
        .order_by("-n")
    )
    return {
        "total_users": total,
        "devices": [{"label": r["device_type"] or "unknown", "n": r["n"]} for r in devices],
        "os": top("os_family"),
        "browsers": top("browser_family"),
        "countries": top("country"),
        "cities": top("city"),
        "languages": top("language_code"),
        "recent": list(
            qs.select_related("user")
            .order_by("-last_seen_at")[:25]
            .values(
                "user__username",
                "device_type",
                "os_family",
                "country",
                "city",
                "language_code",
                "last_ip",
                "last_seen_at",
                "hit_count",
            )
        ),
    }
