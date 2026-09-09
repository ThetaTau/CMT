from django.contrib import admin
from django.utils.safestring import mark_safe

from .models import Config

# Per-key template variable help. Each entry lists the Django template
# variables that the corresponding sender will inject into ``value`` at
# render time. Shown as help text on the change form so authors know which
# ``{{ ... }}`` tokens they can use in the config value.
KEY_TEMPLATE_VARS = {
    "GradAnniversary": [
        ("user", "graduating User (e.g. user.name, user.first_name, user.get_full_name, user.email)"),
        ("chapter", "user's chapter (e.g. chapter.school, chapter.name)"),
        ("graduation_date", "graduation date"),
        ("graduation_year", "graduation year"),
        ("years", "years since graduation (e.g. 5)"),
    ],
    "ChapterFoundingDay": [
        ("user", "member User instance (e.g. user.name, user.first_name, user.get_full_name, user.email)"),
        ("chapter", "member's chapter (e.g. chapter.name, chapter.school)"),
        ("founding_date", "the chapter's founding date"),
        ("years", "years since the chapter was chartered (e.g. 42)"),
    ],
}


def _render_key_vars_help():
    rows = []
    for key, vars_ in KEY_TEMPLATE_VARS.items():
        rows.append(f"<strong>{key}</strong><ul>")
        for name, desc in vars_:
            rows.append(f"<li><code>{{{{ {name} }}}}</code> &mdash; {desc}</li>")
        rows.append("</ul>")
    return mark_safe(
        "<p>Any single-brace <code>{ALL_CAPS_KEY}</code> placeholder in a "
        "<em>value</em> is replaced at send time by looking up a Config row "
        "with that exact key (e.g. <code>{EC_CONTACT}</code> pulls from the "
        "<code>EC_CONTACT</code> Config row). Missing keys are left in place "
        "so the omission is visible in the sent email.</p>"
        "<p>For the keys below, the <em>value</em> field is additionally "
        "rendered as a Django template with these per-recipient variables "
        "available:</p>" + "".join(rows)
    )


@admin.register(Config)
class ConfigAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "description", "created", "modified")
    list_filter = ["created", "modified"]
    search_fields = ["key", "value"]
    ordering = [
        "-created",
    ]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "value" in form.base_fields:
            form.base_fields["value"].help_text = _render_key_vars_help()
        return form
