"""
Очищення акаунтів, які не підтвердили email у відведений час.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)
_purge_started = False
_last_middleware_purge = 0.0


def activation_timeout() -> timedelta:
    minutes = int(getattr(settings, "ACTIVATION_TIMEOUT_MINUTES", 5))
    return timedelta(minutes=max(1, minutes))


def activation_deadline(user):
    return user.date_joined + activation_timeout()


def is_activation_expired(user) -> bool:
    if getattr(user, "email_confirmed", False):
        return False
    return timezone.now() >= activation_deadline(user)


def pending_unactivated_qs():
    User = get_user_model()
    return User.objects.filter(email_confirmed=False, is_superuser=False)


def expired_unactivated_qs():
    cutoff = timezone.now() - activation_timeout()
    return pending_unactivated_qs().filter(date_joined__lte=cutoff)


def purge_expired_unactivated_users() -> int:
    """
    Видаляє юзерів з email_confirmed=False, старших за ACTIVATION_TIMEOUT_MINUTES.
    Не залежить від is_active (раніше SKIP=1 лишав active+«непідтверджених»).
    """
    qs = expired_unactivated_qs()
    rows = list(qs.values_list("id", "username", "date_joined")[:500])
    if not rows:
        return 0
    ids = [r[0] for r in rows]
    User = get_user_model()
    deleted, _ = User.objects.filter(id__in=ids).delete()
    n = len(ids)
    detail = ", ".join(f"{u}@{d}" for _, u, d in rows[:20])
    msg = f"purge_unactivated: deleted {n} user(s) cascade_rows={deleted} [{detail}]"
    logger.warning(msg)
    print(msg, flush=True)
    return n


def purge_status() -> dict:
    pending = pending_unactivated_qs().count()
    expired = expired_unactivated_qs().count()
    inactive = (
        get_user_model()
        .objects.filter(is_active=False, is_superuser=False)
        .count()
    )
    return {
        "pending_unconfirmed": pending,
        "expired_unconfirmed": expired,
        "inactive_users": inactive,
        "activation_timeout_minutes": int(activation_timeout().total_seconds() // 60),
        "skip_email_activation": bool(getattr(settings, "SKIP_EMAIL_ACTIVATION", False)),
    }


def maybe_purge_throttled(min_interval_sec: float = 15.0) -> int:
    """Для middleware: не частіше ніж раз на N секунд на процес."""
    global _last_middleware_purge
    now = time.monotonic()
    if now - _last_middleware_purge < min_interval_sec:
        return 0
    _last_middleware_purge = now
    return purge_expired_unactivated_users()


def start_purge_thread() -> None:
    global _purge_started
    if _purge_started:
        return
    if os.environ.get("RUN_MAIN") == "false":
        return
    if os.environ.get("PURGE_UNACTIVATED", "1").lower() not in ("1", "true", "yes"):
        return

    _purge_started = True
    interval = max(15, int(os.environ.get("PURGE_UNACTIVATED_INTERVAL", "30")))

    def loop():
        time.sleep(3)
        print(f"purge-unactivated thread running every {interval}s", flush=True)
        while True:
            try:
                st = purge_status()
                n = purge_expired_unactivated_users()
                print(
                    f"purge tick: deleted={n} pending={st['pending_unconfirmed']} "
                    f"expired={st['expired_unconfirmed']} inactive={st['inactive_users']} "
                    f"timeout={st['activation_timeout_minutes']}m "
                    f"skip={st['skip_email_activation']}",
                    flush=True,
                )
            except Exception as e:
                print(f"purge_unactivated failed: {e}", flush=True)
                logger.exception("purge_unactivated failed")
            time.sleep(interval)

    threading.Thread(target=loop, name="purge-unactivated", daemon=True).start()
    print("purge-unactivated thread started", flush=True)
