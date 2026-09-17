"""Context processors для навбару."""


def notifications(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"unread_notifications_count": 0}
    from .notification_service import unread_count

    return {"unread_notifications_count": unread_count(request.user)}
