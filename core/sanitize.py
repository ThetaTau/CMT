"""HTML sanitization for user-authored rich text (CKEditor 5).

CKEditor does **not** sanitize markup server-side, and several tables/templates
render those fields with ``|safe``. Without cleaning, a chapter officer (or any
user who can edit a rich-text field) could persist ``<script>`` / ``onerror`` /
``javascript:`` payloads that execute in a privileged viewer's browser
(stored XSS). :func:`sanitize_html` runs the value through an allow-list before
it is marked safe.

Uses `nh3 <https://nh3.readthedocs.io/>`_ (maintained Rust/ammonia binding).
``bleach`` is intentionally avoided — it has been end-of-life since 2023.
"""

import nh3

# Tags roughly matching the CKEditor 5 toolbar configured in settings
# (headings, inline formatting, lists, links, images, tables, code, quotes).
ALLOWED_TAGS = {
    "a",
    "abbr",
    "b",
    "blockquote",
    "br",
    "caption",
    "code",
    "col",
    "colgroup",
    "div",
    "em",
    "figcaption",
    "figure",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "img",
    "li",
    "mark",
    "ol",
    "p",
    "pre",
    "s",
    "small",
    "span",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
}

# ``style`` is deliberately NOT allowed anywhere (CSS injection / overlay
# clickjacking vector); CKEditor styling relies mostly on classes. ``rel`` is
# omitted from ``a`` because nh3 manages it via ``link_rel`` below.
ALLOWED_ATTRIBUTES = {
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "title", "width", "height"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
    "*": {"class"},
}

# Only safe link schemes; nh3 strips ``javascript:``/``data:`` by omission.
ALLOWED_URL_SCHEMES = {"http", "https", "mailto", "tel"}


def sanitize_html(value):
    """Return ``value`` with dangerous HTML removed via an allow-list.

    ``None``/empty is returned unchanged. The result is a plain ``str`` (callers
    that render it should mark it safe, e.g. the ``sanitize_html`` template
    filter).
    """
    if not value:
        return value
    return nh3.clean(
        str(value),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer nofollow",
    )
