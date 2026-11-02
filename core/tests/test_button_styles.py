"""Every form button in the site's Bootstrap templates must look like a button.

Bootstrap 5 only paints a button that has ``btn`` plus a variant such as
``btn-primary``. A bare ``class="btn"`` is transparent with no border, so it reads
as plain text in both themes (the Save button on "Add a submission"), and
``btn-primary`` without ``btn`` falls back to the grey browser default.
"""

import re
from pathlib import Path

from django.conf import settings

TEMPLATES = Path(settings.APPS_DIR) / "templates"
VARIANT = re.compile(r"^btn-(primary|secondary|success|danger|warning|info|light|dark|link|outline-[a-z]+)$")
# Controls that Bootstrap styles as something other than a button.
OTHER_COMPONENTS = {"accordion-button", "btn-close", "dropdown-item", "nav-link", "navbar-toggler", "page-link"}
CONTROL = re.compile(r"<(button|input|a)\b([^>]*)>", re.I | re.S)
TEMPLATE_TAG = re.compile(r"{[{%].*?[%}]}", re.S)


def _classes(attrs):
    match = re.search(r"""\bclass\s*=\s*(["'])(.*?)\1""", attrs, re.S)
    return TEMPLATE_TAG.sub(" ", match.group(2) if match else "").split()


def _control_type(tag, attrs):
    match = re.search(r"""\btype\s*=\s*["']?([\w-]+)""", attrs)
    return match.group(1).lower() if match else ("submit" if tag == "button" else "text")


def _is_materialize_page(text):
    # The /workflow/ pages extend django-material's own base, which loads
    # Materialize, where ``btn``, ``btn-flat`` and ``primary`` are real styles.
    return re.search(r"""{%\s*extends\s+["'](viewflow|material)/""", text) is not None


def _unstyled_controls():
    for path in sorted(TEMPLATES.rglob("*.html")):
        relative = path.relative_to(TEMPLATES).as_posix()
        text = path.read_text(encoding="utf-8")
        # The Django admin and the Materialize pages bring their own button styles.
        if relative.startswith(("admin/", "material/")) or _is_materialize_page(text):
            continue
        for match in CONTROL.finditer(text):
            tag, attrs = match.group(1).lower(), match.group(2)
            classes = _classes(attrs)
            if tag == "a":
                if "btn" not in classes:
                    continue
            elif _control_type(tag, attrs) not in ("submit", "button", "reset"):
                continue
            if OTHER_COMPONENTS.intersection(classes):
                continue
            if "btn" in classes and any(VARIANT.match(name) for name in classes):
                continue
            line = text.count("\n", 0, match.start()) + 1
            yield f"{relative}:{line}: {' '.join(match.group(0).split())[:120]}"


def test_every_template_button_has_a_bootstrap_style():
    assert list(_unstyled_controls()) == []
