"""MessagingService — IMessagingService implementation."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from ..models import CustomUser, PrivateMessage
from . import partners as partners_mod
from .exceptions import MessagingForbidden, MessagingNoPartners, MessagingNotFound
from .ports import IMessagingService
from .thread import ThreadContext, build_thread_context


class MessagingService(IMessagingService):
    def list_partners(self, user: CustomUser) -> QuerySet[CustomUser]:
        return partners_mod.list_exchange_message_partners(user)

    def can_chat(self, user: CustomUser, partner_id: int) -> bool:
        return self.list_partners(user).filter(pk=partner_id).exists()

    def open_thread(self, user: CustomUser, partner_id: int) -> ThreadContext:
        partners = self.list_partners(user)
        if not partners.exists():
            raise MessagingNoPartners(
                "Чат доступний лише після запиту на позику або обмін книги з іншим користувачем."
            )
        if partner_id not in frozenset(partners.values_list("pk", flat=True)):
            raise MessagingForbidden("Немає спільного запиту з цим користувачем.")

        partner = get_user_model().objects.filter(pk=partner_id).first()
        if not partner:
            raise MessagingNotFound("Користувача не знайдено.")

        from ..message_service import mark_thread_read

        ctx = build_thread_context(user, partner, partners)
        mark_thread_read(user, partner_id)
        return ctx

    def send(
        self, sender: CustomUser, partner_id: int, body: str
    ) -> PrivateMessage | None:
        if not self.can_chat(sender, partner_id):
            raise MessagingForbidden("Немає спільного запиту з цим користувачем.")
        partner = get_user_model().objects.filter(pk=partner_id).first()
        if not partner:
            raise MessagingNotFound("Користувача не знайдено.")

        from ..message_service import send_user_message

        return send_user_message(sender, partner, body)


_svc: IMessagingService = MessagingService()


def get_messaging_service() -> IMessagingService:
    return _svc


def set_messaging_service(svc: IMessagingService) -> None:
    global _svc
    _svc = svc
