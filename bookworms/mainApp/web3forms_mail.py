"""
Відправка листів через Web3Forms (https://api.web3forms.com/submit).

Лист приходить на email, верифікований у кабінеті Web3Forms для access_key
(не на довільну адресу отримувача — це не SMTP). Поле email/replyto —
адреса нового користувача для відповіді; посилання активації в body.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
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


def activation_payload(user, activation_url: str) -> dict[str, Any]:
    subject = "Підтвердження реєстрації BookWorms / Date Due Slip"
    message = (
        f"Нова реєстрація: {user.username} <{user.email}>\n\n"
        f"Для активації акаунта відкрийте посилання:\n{activation_url}\n\n"
        f"Якщо реєстрацію не запитували — ігноруйте цей лист."
    )
    return {
        "access_key": settings.WEB3FORMS_ACCESS_KEY,
        "subject": subject,
        "from_name": "BookWorms",
        "email": user.email,
        "replyto": user.email,
        "name": user.username,
        "message": message,
        "activation_url": activation_url,
        "botcheck": False,
    }


def send_web3forms(payload: dict[str, Any]) -> dict[str, Any]:
    key = (payload.get("access_key") or "").strip()
    if not key:
        raise Web3FormsError("WEB3FORMS_ACCESS_KEY не задано.")

    body = json.dumps(payload).encode("utf-8")
    req = Request(
        WEB3FORMS_ENDPOINT,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "BookWorms/DateDueSlip",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            status = getattr(resp, "status", 200)
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        raise Web3FormsError(f"Web3Forms HTTP {e.code}: {raw[:300]}") from e
    except URLError as e:
        raise Web3FormsError(f"Мережа: {e.reason!s}") from e

    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        raise Web3FormsError(f"Некоректна відповідь Web3Forms: {raw[:200]}") from e

    if status >= 400 or data.get("success") is False:
        msg = data.get("message") or data.get("body", {}).get("message") or raw[:200]
        raise Web3FormsError(str(msg))
    return data


def send_activation_email(user, request=None) -> str:
    """Надсилає лист активації. Повертає activation_url."""
    url = activation_url_for(user, request)
    send_web3forms(activation_payload(user, url))
    return url
