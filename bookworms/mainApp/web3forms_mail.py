"""
Відправка листів через Web3Forms (https://api.web3forms.com/submit).

Лист приходить на email, верифікований у кабінеті Web3Forms для access_key
(не на довільну адресу отримувача — це не SMTP).
"""
from __future__ import annotations

import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import account_activation_token

logger = logging.getLogger(__name__)

WEB3FORMS_ENDPOINT = "https://api.web3forms.com/submit"


class Web3FormsError(Exception):
    pass


def public_base_url(request=None) -> str:
    base = (getattr(settings, "PUBLIC_BASE_URL", None) or "").rstrip("/")
    if base:
        return base
    if request is not None:
        return request.build_absolute_uri("/").rstrip("/")
    return "http://127.0.0.1:8000"


def activation_url_for(user, request=None) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = account_activation_token.make_token(user)
    path = reverse("activate", kwargs={"uidb64": uid, "token": token})
    return f"{public_base_url(request)}{path}"


def activation_message(user, activation_url: str) -> str:
    minutes = int(getattr(settings, "ACTIVATION_TIMEOUT_MINUTES", 5))
    return (
        f"Нова реєстрація Реченець\n\n"
        f"Логін: {user.username}\n"
        f"Email (reply): {user.email}\n\n"
        f"Активація (дійсна {minutes} хв):\n{activation_url}\n\n"
        f"Якщо не підтвердити за {minutes} хв — акаунт буде видалено."
    )


def activation_payload(user, activation_url: str) -> dict[str, Any]:
    """
    Тільки поля, які Web3Forms офіційно очікує.
    Кастомні ключі інколи ламають доставку на free-плані.
    """
    return {
        "access_key": (settings.WEB3FORMS_ACCESS_KEY or "").strip(),
        "subject": "Реченець — підтвердження реєстрації",
        "from_name": "Реченець",
        "name": user.username,
        "email": user.email,
        "message": activation_message(user, activation_url),
    }


def _post(body: bytes, content_type: str) -> dict[str, Any]:
    req = Request(
        WEB3FORMS_ENDPOINT,
        data=body,
        headers={
            "Content-Type": content_type,
            "Accept": "application/json",
            "User-Agent": "Rechenets/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            status = getattr(resp, "status", 200)
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        print(f"Web3Forms HTTPError {e.code}: {raw[:400]}", flush=True)
        raise Web3FormsError(f"Web3Forms HTTP {e.code}: {raw[:300]}") from e
    except URLError as e:
        print(f"Web3Forms URLError: {e.reason}", flush=True)
        raise Web3FormsError(f"Мережа (контейнер→api.web3forms.com): {e.reason!s}") from e

    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        raise Web3FormsError(f"Некоректна відповідь Web3Forms: {raw[:200]}") from e

    print(f"Web3Forms OK? status={status} body={raw[:400]}", flush=True)
    if status >= 400 or data.get("success") is False:
        msg = data.get("message") or raw[:200]
        raise Web3FormsError(str(msg))
    return data


def send_web3forms(payload: dict[str, Any]) -> dict[str, Any]:
    key = (payload.get("access_key") or "").strip()
    if not key:
        raise Web3FormsError("WEB3FORMS_ACCESS_KEY не задано.")

    # 1) form-urlencoded — найсумісніший варіант для Web3Forms
    try:
        return _post(
            urlencode(payload).encode("utf-8"),
            "application/x-www-form-urlencoded",
        )
    except Web3FormsError as first:
        logger.warning("Web3Forms form-urlencoded failed: %s — retry JSON", first)

    # 2) JSON fallback
    return _post(
        json.dumps(payload).encode("utf-8"),
        "application/json",
    )


def send_activation_email(user, request=None) -> str:
    """Надсилає лист активації. Повертає activation_url."""
    url = activation_url_for(user, request)
    send_web3forms(activation_payload(user, url))
    return url


def stash_web3forms_bridge(payload: dict[str, Any], activation_url: str, request=None) -> str:
    """
    Free Web3Forms блокує server-side і React Native fetch (немає browser Origin).
    Зберігаємо payload і віддаємо URL HTML-сторінки, яка шле FormData з браузера.
    """
    import secrets

    from django.core.cache import cache

    token = secrets.token_urlsafe(24)
    cache.set(
        f"w3bridge:{token}",
        {"payload": payload, "activation_url": activation_url},
        timeout=600,
    )
    return f"{public_base_url(request)}/register/send-web3forms/{token}/"


def pop_web3forms_bridge(token: str) -> dict[str, Any] | None:
    from django.core.cache import cache

    key = f"w3bridge:{token}"
    data = cache.get(key)
    # не pop одразу — дозволити reload сторінки раз; TTL 10 хв
    return data if isinstance(data, dict) else None
