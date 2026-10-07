"""Allowlist HTML sanitizer for ISBN catalog prose (synopsis/overview/excerpt)."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urlparse

_ALLOWED_TAGS = frozenset(
    {
        "p",
        "br",
        "div",
        "span",
        "em",
        "i",
        "strong",
        "b",
        "u",
        "s",
        "sub",
        "sup",
        "blockquote",
        "ul",
        "ol",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "a",
        "hr",
    }
)
_VOID = frozenset({"br", "hr"})
_DROP_WITH_CONTENT = frozenset(
    {
        "script",
        "style",
        "iframe",
        "object",
        "embed",
        "form",
        "input",
        "textarea",
        "button",
        "svg",
        "math",
    }
)
_ALLOWED_ATTRS = {
    "a": frozenset({"href", "title", "rel", "target"}),
    "*": frozenset({"title"}),
}
_SAFE_HREF = frozenset({"http", "https", "mailto"})
_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")


def looks_like_html(value: str) -> bool:
    return bool(_TAG_RE.search(value or ""))


def _escape_text(data: str) -> str:
    return data.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _safe_href(href: str) -> str | None:
    href = (href or "").strip()
    if not href or href.startswith("#"):
        return href or None
    if href.lower().startswith("javascript:"):
        return None
    parsed = urlparse(href)
    scheme = (parsed.scheme or "").lower()
    if scheme and scheme not in _SAFE_HREF:
        return None
    return href


def _attrs_html(tag: str, attrs: Iterable[tuple[str, str | None]]) -> tuple[str, bool]:
    """Return (attr_html_including_leading_space, has_href_for_anchor)."""
    allowed = _ALLOWED_ATTRS.get(tag, frozenset()) | _ALLOWED_ATTRS["*"]
    parts: list[str] = []
    has_href = False
    has_target_blank = False
    has_rel = False
    for name, val in attrs:
        if not name or val is None:
            continue
        key = name.lower()
        if key.startswith("on") or key in {"style", "class", "id"}:
            continue
        if key not in allowed:
            continue
        if key == "href":
            safe = _safe_href(val)
            if not safe:
                continue
            val = safe
            has_href = True
        if key == "target":
            if val not in {"_blank", "_self"}:
                continue
            if val == "_blank":
                has_target_blank = True
        if key == "rel":
            has_rel = True
        esc = _escape_text(str(val)).replace('"', "&quot;")
        parts.append(f'{key}="{esc}"')
    if tag == "a" and has_target_blank and not has_rel:
        parts.append('rel="noopener noreferrer"')
    if not parts:
        return "", has_href
    return " " + " ".join(parts), has_href


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._out: list[str] = []
        self._drop_depth = 0
        self._stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self._drop_depth:
            if tag in _DROP_WITH_CONTENT:
                self._drop_depth += 1
            return
        if tag in _DROP_WITH_CONTENT:
            self._drop_depth = 1
            return
        if tag not in _ALLOWED_TAGS:
            return
        attr_s, has_href = _attrs_html(tag, attrs)
        if tag == "a" and not has_href:
            return
        if tag in _VOID:
            self._out.append(f"<{tag}>")
            return
        self._out.append(f"<{tag}{attr_s}>")
        self._stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._drop_depth:
            if tag in _DROP_WITH_CONTENT:
                self._drop_depth = max(0, self._drop_depth - 1)
            return
        if tag not in _ALLOWED_TAGS or tag in _VOID:
            return
        if tag not in self._stack:
            return
        # close nested until tag
        while self._stack:
            top = self._stack.pop()
            self._out.append(f"</{top}>")
            if top == tag:
                break

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self._drop_depth or tag in _DROP_WITH_CONTENT:
            return
        if tag in _VOID and tag in _ALLOWED_TAGS:
            self._out.append(f"<{tag}>")
            return
        if tag in _ALLOWED_TAGS:
            self.handle_starttag(tag, attrs)
            if self._stack and self._stack[-1] == tag:
                self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self._drop_depth or not data:
            return
        self._out.append(_escape_text(data))

    def handle_entityref(self, name: str) -> None:
        if self._drop_depth:
            return
        self._out.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if self._drop_depth:
            return
        self._out.append(f"&#{name};")

    def result(self) -> str:
        while self._stack:
            self._out.append(f"</{self._stack.pop()}>")
        return "".join(self._out).strip()


def sanitize_isbn_html(value: str | None) -> str:
    """Strip dangerous tags/attrs; keep common formatting. Plain text → escaped + <br>."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if not looks_like_html(text):
        return _escape_text(text).replace("\n", "<br>\n")
    parser = _Sanitizer()
    try:
        parser.feed(text)
        parser.close()
    except Exception:
        return _escape_text(text)
    return parser.result()


class _Truncator(HTMLParser):
    def __init__(self, max_len: int) -> None:
        super().__init__(convert_charrefs=True)
        self.max_len = max_len
        self._count = 0
        self._out: list[str] = []
        self._stack: list[str] = []
        self._done = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._done:
            return
        tag = tag.lower()
        attr_s, _ = _attrs_html(tag, attrs)
        if tag in _VOID:
            self._out.append(f"<{tag}>")
            return
        self._out.append(f"<{tag}{attr_s}>")
        self._stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _VOID or tag not in self._stack:
            return
        while self._stack:
            top = self._stack.pop()
            self._out.append(f"</{top}>")
            if top == tag:
                break

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._done:
            return
        tag = tag.lower()
        if tag in _VOID:
            self._out.append(f"<{tag}>")

    def handle_data(self, data: str) -> None:
        if self._done or not data:
            return
        remain = self.max_len - self._count
        if remain <= 0:
            self._finish()
            return
        if len(data) <= remain:
            self._out.append(_escape_text(data))
            self._count += len(data)
            return
        chunk = data[:remain].rstrip()
        self._out.append(_escape_text(chunk) + "…")
        self._count = self.max_len
        self._finish()

    def _finish(self) -> None:
        self._done = True
        while self._stack:
            self._out.append(f"</{self._stack.pop()}>")

    def result(self) -> str:
        while self._stack:
            self._out.append(f"</{self._stack.pop()}>")
        return "".join(self._out)


def truncate_sanitized_html(html: str, max_len: int) -> str:
    """Truncate by visible text length; close open tags."""
    if max_len <= 0 or not html:
        return html or ""
    # rough fast path
    if len(html) <= max_len and html.count("<") < 2:
        return html
    parser = _Truncator(max_len)
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return html[:max_len]
    return parser.result()
