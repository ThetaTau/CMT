"""
Copied from: https://gist.github.com/jamesbrobb/748c47f46b9bd224b07f
    per: http://stackoverflow.com/questions/15497693/django-can-class-based-views-accept-two-forms-at-a-time/24011448#24011448
"""

import re

from address.forms import Address
from address.models import Locality
from dal_select2.fields import Select2ListCreateChoiceField
from dal_select2.widgets import Select2Multiple, Select2WidgetMixin, WidgetMixin
from django import forms
from django.conf import settings
from django.http.response import HttpResponseForbidden, HttpResponseRedirect
from django.views.generic.base import ContextMixin, TemplateResponseMixin
from django.views.generic.edit import ProcessFormView
from tempus_dominus.widgets import DatePicker as _DatePicker

from core.address import get_or_create_address
from core.choices import (
    ADDRESS_REGION_SUGGESTIONS,
    CA_PROVINCE_CODE_TO_NAME,
    CA_PROVINCE_NAME_TO_CODE,
    COUNTRY_CHOICES,
    UK_REGION_NAME_TO_CODE,
    US_STATE_CODE_TO_NAME,
    US_STATE_NAME_TO_CODE,
)


class DatePicker(_DatePicker):
    """Override moment_option to avoid moment.js treating ISO date strings as UTC.

    Moment.js 2.x parses bare ISO date strings (e.g. "1995-03-27") as UTC
    midnight.  In timezones behind UTC the picker then displays the previous
    day, which the user submits and saves.  Appending T12:00:00 keeps the
    value well within the same calendar day for any UTC offset.
    """

    def id_for_label(self, id_):
        # tempus_dominus rewrites "-" to "_" in the id it renders (it builds a
        # JS function name from it), so on a prefixed form the crispy <label
        # for="id_user-birth_date"> pointed at an element that did not exist.
        return id_.replace("-", "_")

    def moment_option(self, value):
        opts = super().moment_option(value)
        if "date" in opts and "T" not in opts["date"]:
            opts["date"] = opts["date"] + "T12:00:00"
        return opts


class SchoolModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.school}"


class MultiFormMixin(ContextMixin):
    form_classes = {}
    prefixes = {}
    success_urls = {}
    grouped_forms = {}

    initial = {}
    prefix = None
    success_url = None

    def get_form_classes(self):
        return self.form_classes

    def get_forms(self, form_classes, form_names=None, bind_all=False):
        return dict(
            [
                (
                    key,
                    self._create_form(key, klass, (form_names and key in form_names) or bind_all),
                )
                for key, klass in form_classes.items()
            ]
        )

    def _get_form_kwargs(self, form_name, bind_form=False):
        kwargs = {}
        kwargs.update({"initial": self._get_initial(form_name)})
        kwargs.update({"prefix": self._get_prefix(form_name)})
        kwargs_method = "get_%s_kwargs" % form_name
        if hasattr(self, kwargs_method):
            kwargs.update(getattr(self, kwargs_method)())

        if bind_form:
            kwargs.update(self._bind_form_data())

        return kwargs

    def forms_valid(self, forms, form_name):
        form_valid_method = "%s_form_valid" % form_name
        if hasattr(self, form_valid_method):
            return getattr(self, form_valid_method)(forms[form_name])
        else:
            return HttpResponseRedirect(self._get_success_url(form_name))

    def forms_invalid(self, forms):
        return self.render_to_response(self.get_context_data(forms=forms))

    def _get_initial(self, form_name):
        initial_method = "get_%s_initial" % form_name
        if hasattr(self, initial_method):
            return getattr(self, initial_method)()
        else:
            return self.initial.copy()

    def _get_prefix(self, form_name):
        return self.prefixes.get(form_name, self.prefix)

    def _get_success_url(self, form_name=None):
        return self.success_urls.get(form_name, self.success_url)

    def _create_form(self, form_name, klass, bind_form):
        form_kwargs = self._get_form_kwargs(form_name, bind_form)
        form_create_method = "create_%s_form" % form_name
        if hasattr(self, form_create_method):
            form = getattr(self, form_create_method)(**form_kwargs)
        else:
            form = klass(**form_kwargs)
        return form

    def _bind_form_data(self):
        if self.request.method in ("POST", "PUT"):
            return {
                "data": self.request.POST,
                "files": self.request.FILES,
            }
        return {}


class ProcessMultipleFormsView(ProcessFormView):
    def get(self, request, *args, **kwargs):
        form_classes = self.get_form_classes()
        forms = self.get_forms(form_classes)
        return self.render_to_response(self.get_context_data(forms=forms))

    def post(self, request, *args, **kwargs):
        form_classes = self.get_form_classes()
        form_name = request.POST.get("action")
        if self._individual_exists(form_name):
            return self._process_individual_form(form_name, form_classes)
        elif self._group_exists(form_name):
            return self._process_grouped_forms(form_name, form_classes)
        else:
            return self._process_all_forms(form_classes)

    def _individual_exists(self, form_name):
        return form_name in self.form_classes

    def _group_exists(self, group_name):
        return group_name in self.grouped_forms

    def _process_individual_form(self, form_name, form_classes):
        forms = self.get_forms(form_classes, (form_name,))
        form = forms.get(form_name)
        if not form:
            return HttpResponseForbidden()
        elif form.is_valid():
            return self.forms_valid(forms, form_name)
        else:
            return self.forms_invalid(forms)

    def _process_grouped_forms(self, group_name, form_classes):
        form_names = self.grouped_forms[group_name]
        forms = self.get_forms(form_classes, form_names)
        if all([forms.get(form_name).is_valid() for form_name in form_classes.keys()]):
            for form_name in form_names:
                response = self.forms_valid(forms, form_name)
            return response
        else:
            return self.forms_invalid(forms)

    def _process_all_forms(self, form_classes):
        forms = self.get_forms(form_classes, None, True)
        if all([form.is_valid() for form in forms.values()]):
            return self.forms_valid(forms)
        else:
            return self.forms_invalid(forms)


class BaseMultipleFormsView(MultiFormMixin, ProcessMultipleFormsView):
    """
    A base view for displaying several forms.
    """


class MultiFormsView(TemplateResponseMixin, BaseMultipleFormsView):
    """
    A view for displaying several forms, and rendering a template response.
    """


class ComponentAddressWidget(forms.MultiWidget):
    """Renders address as five side-by-side inputs (street / city / state /
    postal code / country).  State and country are free-text inputs backed by
    an HTML ``<datalist>`` of common US / Canadian / UK values so members
    from any of those regions get autocomplete without being forced into a
    dropdown.  When ``GOOGLE_API_KEY`` is configured, an additional Google
    Places autocomplete search box is rendered above the five fields;
    picking a suggestion fills the split fields via JS.  The autocomplete
    search input itself is not part of the form submission.

    The widget accepts either an `Address` instance, a dict of components, or
    a 5-tuple as its ``value``.
    """

    template_name = "core/component_address_widget.html"

    STATE_DATALIST_ID = "cmt-address-region-suggestions"
    COUNTRY_DATALIST_ID = "cmt-address-country-suggestions"

    def __init__(self, attrs=None):
        base = {"class": "form-control"}
        widgets = [
            forms.TextInput(attrs={**base, "placeholder": "Street address", "autocomplete": "street-address"}),
            forms.TextInput(attrs={**base, "placeholder": "City", "autocomplete": "address-level2"}),
            forms.TextInput(
                attrs={
                    **base,
                    "placeholder": "State / Province / Region",
                    "autocomplete": "address-level1",
                    "list": self.STATE_DATALIST_ID,
                }
            ),
            forms.TextInput(attrs={**base, "placeholder": "ZIP / postal code", "autocomplete": "postal-code"}),
            forms.TextInput(
                attrs={
                    **base,
                    "placeholder": "Country",
                    "autocomplete": "country-name",
                    "list": self.COUNTRY_DATALIST_ID,
                }
            ),
        ]
        super().__init__(widgets, attrs)

    def _google_api_key(self):
        key = getattr(settings, "GOOGLE_API_KEY", "")
        return key if key and key != "TESTING" else ""

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        parent_id = ctx["widget"]["attrs"].get("id") or f"id_{name}"
        ctx["widget"]["google_api_key"] = self._google_api_key()
        ctx["widget"]["autocomplete_id"] = f"{parent_id}_search"
        ctx["widget"]["autocomplete_prefix"] = parent_id
        ctx["widget"]["state_datalist_id"] = self.STATE_DATALIST_ID
        ctx["widget"]["country_datalist_id"] = self.COUNTRY_DATALIST_ID
        ctx["widget"]["state_datalist_options"] = ADDRESS_REGION_SUGGESTIONS
        ctx["widget"]["country_datalist_options"] = [name for name, _ in COUNTRY_CHOICES if name != "Other"]
        return ctx

    @property
    def media(self):
        base = super().media
        js = ["core/js/component_address_autocomplete.js"]
        key = self._google_api_key()
        if key:
            js.insert(0, f"https://maps.googleapis.com/maps/api/js?libraries=places&key={key}")
        return base + forms.Media(js=js)

    def decompress(self, value):
        if value in (None, ""):
            return ["", "", "", "", "United States"]
        # ModelForm passes an FK's PK as the field's initial value, not the
        # related instance — resolve it before decomposing.
        if isinstance(value, int):
            try:
                value = Address.objects.select_related("locality__state__country").get(pk=value)
            except Address.DoesNotExist:
                return ["", "", "", "", "United States"]
        if isinstance(value, Address):
            street = " ".join(p for p in [value.street_number, value.route] if p).strip()
            locality = value.locality
            city = locality.name if locality else ""
            postal = locality.postal_code if locality else ""
            state_obj = locality.state if locality else None
            # Prefer the full name; fall back to the code so the input always
            # shows something meaningful even when historical data only stored
            # the abbreviation.
            state = ""
            if state_obj:
                state = state_obj.name or state_obj.code or ""
            country = state_obj.country.name if state_obj and state_obj.country else "United States"
            return [street, city, state, postal, country]
        if isinstance(value, dict):
            return [
                value.get("street", ""),
                value.get("city", ""),
                value.get("state", ""),
                value.get("postal_code", ""),
                value.get("country", "United States"),
            ]
        if isinstance(value, (list, tuple)) and len(value) == 5:
            return list(value)
        return ["", "", "", "", "United States"]


class ComponentAddressField(forms.MultiValueField):
    """Form field backing an `AddressField` FK using typed-in components.

    On ``compress`` looks up (or creates) the underlying `Address` row via
    `get_or_create_address`.  When multiple rows already match the given
    components the oldest is returned; no merging happens here.
    """

    widget = ComponentAddressWidget

    def __init__(self, *, required=False, **kwargs):
        fields = (
            forms.CharField(max_length=200, required=False),
            forms.CharField(max_length=165, required=False),
            forms.CharField(max_length=165, required=False),
            forms.CharField(max_length=10, required=False),
            forms.CharField(max_length=100, required=False),
        )
        kwargs.setdefault("require_all_fields", False)
        super().__init__(fields=fields, required=required, **kwargs)

    def compress(self, data_list):
        if not data_list:
            return None
        street, city, state, postal_code, country = (data_list + ["", "", "", "", ""])[:5]
        state = (state or "").strip()
        country = (country or "").strip() or "United States"

        # Users can type either the 2-letter code or the full name for US
        # states and Canadian provinces; UK constituent countries only carry a
        # name.  Normalize to (full_name, code) so the persisted `State` row
        # is consistent regardless of what was typed.
        state_code = ""
        if country == "United States" and state:
            upper = state.upper()
            if upper in US_STATE_CODE_TO_NAME:
                state_code = upper
                state = US_STATE_CODE_TO_NAME[upper]
            elif state in US_STATE_NAME_TO_CODE:
                state_code = US_STATE_NAME_TO_CODE[state]
        elif country == "Canada" and state:
            upper = state.upper()
            if upper in CA_PROVINCE_CODE_TO_NAME:
                state_code = upper
                state = CA_PROVINCE_CODE_TO_NAME[upper]
            elif state in CA_PROVINCE_NAME_TO_CODE:
                state_code = CA_PROVINCE_NAME_TO_CODE[state]
        elif country == "United Kingdom" and state in UK_REGION_NAME_TO_CODE:
            state_code = UK_REGION_NAME_TO_CODE[state]

        address = get_or_create_address(
            street=street,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
            state_code=state_code,
        )
        if address is None and self.required:
            raise forms.ValidationError("Address is required.")
        return address

    def has_changed(self, initial, data):
        # `initial` is an Address instance (or None); `data` is the raw component
        # list from POST.  Compare the decomposed initial values against POST.
        widget = self.widget if isinstance(self.widget, ComponentAddressWidget) else ComponentAddressWidget()
        initial_list = widget.decompress(initial)
        data_list = list(data or [])
        while len(data_list) < 5:
            data_list.append("")
        return [str(x or "").strip() for x in initial_list[:5]] != [str(x or "").strip() for x in data_list[:5]]


class Select2ListCreateMultipleChoiceField(Select2ListCreateChoiceField, Select2Multiple):
    queryset = None

    def __init__(self, *args, **kwargs):
        self.queryset = kwargs.pop("queryset")
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if not value:
            return []
        elif not isinstance(value, list):
            return [value]
        new_values = []
        for val in value:
            try:
                val = int(val)
            except ValueError:
                if self.queryset.model == Locality:
                    val = re.search(r"\b\d{5}\b", val).group(0)
                    true_value = self.queryset.filter(postal_code=val).first()
                else:
                    true_value = self.queryset.get(name=val)
                new_values.append(true_value)
            else:
                new_values.append(val)
        return new_values

    def validate(self, value):
        # for create :
        super(forms.ChoiceField, self).validate(value)
        # otherwise you could use :
        # for v in value:
        #     super().validate(v)

    def bound_data(self, data, initial):
        if self.disabled:
            return initial
        return data


class ListSelect2Multiple(WidgetMixin, Select2WidgetMixin, forms.SelectMultiple):
    """Select widget for regular choices and Select2."""


def set_multiple_choices_initial(obj, field_name):
    field = obj.fields[field_name]
    values = getattr(obj.instance, field_name).all()
    if values:
        field.initial = [str(value) for value in values]
        field.choices = [(str(value), str(value)) for value in values.order_by("name")]
