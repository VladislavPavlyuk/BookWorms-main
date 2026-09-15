"""
Очищення акаунтів, які не підтвердили email у відведений час.
"""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone


def activation_timeout() -> timedelta:
    minutes = int(getattr(settings, "ACTIVATION_TIMEOUT_MINUTES", 5))
    return timedelta(minutes=max(1, minutes))


def activation_deadline(user):
    return user.date_joined + activation_timeout()


def is_activation_expired(user) -> bool:
    if user.is_active:
        return False
    return timezone.now() >= activation_deadline(user)


def purge_expired_unactivated_users() -> int:
    """
    Видаляє користувачів з is_active=False, у яких минув строк підтвердження email.
    Superuser не чіпаємо.
    """
    User = get_user_model()
    cutoff = timezone.now() - activation_timeout()
    qs = User.objects.filter(
        is_active=False,
        is_superuser=False,
        date_joined__lt=cutoff,
    )
    count, _ = qs.delete()
    return count
