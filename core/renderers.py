"""Custom form renderer.

Uses django.forms.renderers.TemplatesSetting so widget templates resolve via the
project's TEMPLATES setting (filesystem loader wins over app_directories),
which lets us override third-party widget templates from thetatauCMT/templates/.
Keeps the Django 5.0 div-based form/formset rendering that DjangoDivFormRenderer
provided.
"""

from django.forms.renderers import TemplatesSetting


class DivTemplatesSetting(TemplatesSetting):
    form_template_name = "django/forms/div.html"
    formset_template_name = "django/forms/formsets/div.html"
