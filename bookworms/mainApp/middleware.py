"""Purge непідтверджених акаунтів на будь-який HTTP-запит (з throttle)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class PurgeUnactivatedMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            from mainApp.registration_service import maybe_purge_throttled

            maybe_purge_throttled(15.0)
        except Exception:
            logger.exception("PurgeUnactivatedMiddleware failed")
        return self.get_response(request)
