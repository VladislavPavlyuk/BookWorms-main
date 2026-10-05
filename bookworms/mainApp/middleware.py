"""Request middleware: purge + client analytics capture."""

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


class ClientAnalyticsMiddleware:
    """
    Record device / OS / geo / Accept-Language for authenticated users.
    Also peeks JWT so React Native API traffic is counted.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            path = request.path or ""
            if path.startswith(("/static/", "/media/", "/favicon")):
                return response
            user = getattr(request, "user", None)
            if not user or not getattr(user, "is_authenticated", False):
                user = self._jwt_user(request)
            if user and getattr(user, "is_authenticated", False):
                from mainApp.analytics import record_client_hit

                record_client_hit(request, user)
        except Exception:
            logger.exception("ClientAnalyticsMiddleware failed")
        return response

    @staticmethod
    def _jwt_user(request):
        auth = request.META.get("HTTP_AUTHORIZATION") or ""
        if not auth.lower().startswith("bearer "):
            return None
        try:
            from rest_framework_simplejwt.authentication import JWTAuthentication

            result = JWTAuthentication().authenticate(request)
            if result:
                return result[0]
        except Exception:
            return None
        return None
