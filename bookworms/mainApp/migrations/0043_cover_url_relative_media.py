"""Store local covers as /media/... paths; rewrite existing absolute MEDIA URLs."""

from __future__ import annotations

import re

from django.db import migrations, models

_MEDIA_RE = re.compile(r"(https?://[^/\s]+)?(/media/[^\s?#]*)", re.I)


def _to_relative(url: str) -> str | None:
    u = (url or "").strip()
    if not u:
        return ""
    if u.startswith("/media/"):
        return u.split("?", 1)[0][:500]
    m = _MEDIA_RE.search(u)
    if m:
        return m.group(2).split("?", 1)[0][:500]
    idx = u.find("/media/")
    if idx >= 0:
        return u[idx:].split("?", 1)[0][:500]
    return None


def rewrite_cover_urls(apps, schema_editor):
    Book = apps.get_model("mainApp", "Book")
    updated = 0
    for book in Book.objects.exclude(cover_url="").iterator():
        new = _to_relative(book.cover_url)
        if new is None:
            continue
        if new != (book.cover_url or "").strip():
            book.cover_url = new
            book.save(update_fields=["cover_url"])
            updated += 1
    if updated:
        print(f"  rewritten {updated} Book.cover_url → /media/…")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0042_book_isbndb_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="book",
            name="cover_url",
            field=models.CharField(
                blank=True, max_length=500, verbose_name="Обкладинка (URL)"
            ),
        ),
        migrations.RunPython(rewrite_cover_urls, noop_reverse),
    ]
