"""
Позиція поста у стрічці (newest first) для resume на головній.
Порядок стрічки: -created_ad, -id.
"""
from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet

from .models import Post


FEED_ORDER = ("-created_ad", "-id")


def feed_queryset(filter_my: bool = False, user=None) -> QuerySet[Post]:
    qs = Post.objects.select_related("author", "book").order_by(*FEED_ORDER)
    if filter_my and user is not None and getattr(user, "is_authenticated", False):
        qs = qs.filter(author=user)
    return qs


def set_last_watched_post(user, post_id: int) -> Post | None:
    """Зберігає last_watched_post; повертає Post або None якщо не існує."""
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    post = Post.objects.filter(pk=post_id).first()
    if not post:
        return None
    if user.last_watched_post_id != post.id:
        user.last_watched_post = post
        user.save(update_fields=["last_watched_post"])
    return post


def feed_position(
    post_id: int,
    *,
    page_size: int,
    filter_my: bool = False,
    user=None,
) -> dict[str, Any] | None:
    """
    0-based index у стрічці + 1-based page.
    None якщо поста немає (або не в filter=my).
    """
    if page_size < 1:
        page_size = 1
    qs = feed_queryset(filter_my=filter_my, user=user)
    post = qs.filter(pk=post_id).first()
    if not post:
        return None
    newer = qs.filter(
        Q(created_ad__gt=post.created_ad)
        | Q(created_ad=post.created_ad, id__gt=post.id)
    ).count()
    page = newer // page_size + 1
    return {
        "post_id": post.id,
        "index": newer,
        "page": page,
        "index_in_page": newer % page_size,
        "page_size": page_size,
    }


def qs_from_post_inclusive(qs: QuerySet[Post], post: Post) -> QuerySet[Post]:
    """Стрічка починаючи з post (включно) далі до старіших."""
    return qs.filter(
        Q(created_ad__lt=post.created_ad)
        | Q(created_ad=post.created_ad, id__lte=post.id)
    )
