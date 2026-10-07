from django import template
from django.utils.safestring import mark_safe

from mainApp.html_sanitize import sanitize_isbn_html, truncate_sanitized_html

register = template.Library()


@register.filter(name="isbn_html")
def isbn_html(value, max_len=None):
    """Sanitize ISBN prose and mark safe for rendering (scripts/styles stripped)."""
    html = sanitize_isbn_html(value)
    if max_len not in (None, ""):
        try:
            html = truncate_sanitized_html(html, int(max_len))
        except (TypeError, ValueError):
            pass
    return mark_safe(html)
