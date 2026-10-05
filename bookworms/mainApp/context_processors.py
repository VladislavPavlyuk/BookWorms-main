"""Context processors для навбару."""

from .models import READER_AGE_MAX, READER_AGE_MIN


def notifications(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"unread_notifications_count": 0}
    from .notification_service import unread_count

    return {"unread_notifications_count": unread_count(request.user)}


def reader_age_scale(request):
    return {
        "reader_age_min": READER_AGE_MIN,
        "reader_age_max": READER_AGE_MAX,
    }
