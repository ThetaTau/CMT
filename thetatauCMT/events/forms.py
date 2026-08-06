from crispy_forms.bootstrap import FormActions, InlineField, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Fieldset, Layout, Row, Submit
from dal import autocomplete, forward
from django import forms
from django.forms.utils import pretty_name

from core.forms import DatePicker
from core.models import CHAPTER_OFFICER_CHOICES, user_is_national_officer
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.regions.models import Region

from .models import CalendarFeedSubscription, Event, Picture


def task_owner_roles_field():
    """A select2 multiselect of chapter-officer roles for to-do task feeds.

    Empty selection means "every role's tasks". Shared by the tasks-only feed
    form and the custom subscription form so both use the identical control.
    """
    return forms.MultipleChoiceField(
        choices=CHAPTER_OFFICER_CHOICES,
        required=False,
        widget=autocomplete.Select2Multiple(
            attrs={
                "data-placeholder": "All tasks \u2014 or pick officer roles\u2026",
                "data-minimum-input-length": 0,
            },
        ),
    )


class EventListFormHelper(FormHelper):
    form_method = "GET"
    form_id = "event-search-form"
    form_class = "form-inline"
    field_template = "bootstrap5/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True

    def __init__(self, form=None, natoff=False):
        extra = []
        if natoff:
            extra = [
                InlineField("region"),
                InlineField("chapter"),
                InlineField("is_national"),
                InlineField("pictures"),
            ]
        self.layout = Layout(
            Fieldset(
                '<i class="fas fa-search"></i> Filter Events',
                Row(
                    InlineField("name"),
                    InlineField("date"),
                    InlineField("type"),
                    InlineField("is_public"),
                    *extra,
                    FormActions(
                        StrictButton(
                            '<i class="fa fa-search"></i> Filter',
                            type="submit",
                            css_class="btn-primary",
                        ),
                        Submit("cancel", "Clear", css_class="btn-primary"),
                    ),
                ),
            ),
        )
        super().__init__(form=form)


class PictureForm(forms.ModelForm):
    image = forms.ImageField()

    class Meta:
        model = Picture
        fields = [
            "description",
            "image",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This formset renders as a table with labels suppressed, so the only
        # accessible name each control can get is an aria-label.
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("aria-label", field.label or pretty_name(name))


class EventForm(forms.ModelForm):
    """
    This is a Model From created to add help text to the create
    event form without changing database model. The Duration field
    is the only field that is updated.
    """

    duration = forms.IntegerField(
        min_value=0,
        help_text="In Hours",
    )

    class Meta:
        model = Event
        fields = [
            "name",
            "date",
            "type",
            "description",
            "members",
            "pledges",
            "alumni",
            "guests",
            "duration",
            "stem",
            "host",
            "virtual",
            "miles",
            "raised",
            "is_public",
            "is_national",
            "parent_event",
        ]
        labels = {
            "is_public": "Open to Other Chapters",
        }
        widgets = {
            "date": DatePicker(
                options={"format": "M/DD/YYYY"},
                attrs={"autocomplete": "off"},
            ),
        }
        help_texts = {
            "is_public": (
                "Open this event to other chapters. Chapter events require National "
                "Officer approval before they become visible to other chapters."
            ),
        }

    # a clean method does not work b/c the chapter_id is not set in the form
    def __init__(self, *args, request_user=None, **kwargs):
        self.request_user = request_user
        super().__init__(*args, **kwargs)
        # Only National Officers may flag an event as national. Hide/disable the
        # field entirely for everyone else so it cannot be set from the UI.
        if not user_is_national_officer(request_user):
            self.fields.pop("is_national", None)
        # Parent event is chosen via a type-to-search autocomplete rather than a
        # long dropdown. The autocomplete view scopes the searchable options:
        # national events look up national parents; chapter events look up their
        # own chapter's events. The field queryset stays broad for validation.
        parent_field = self.fields.get("parent_event")
        if parent_field is not None:
            self_pk = self.instance.pk if (self.instance and self.instance.pk) else 0
            forward_fields = [forward.Const(self_pk, "self_pk")]
            if "is_national" in self.fields:
                forward_fields.append(forward.Field("is_national"))
            parent_field.widget = autocomplete.ModelSelect2(
                url="events:event-autocomplete",
                forward=forward_fields,
                attrs={"data-placeholder": "Type to search events…", "data-minimum-input-length": 0},
            )
            parent_field.queryset = Event.objects.all()
            parent_field.required = False
        # Once a public event has been rejected, its public request is final:
        # lock the ``is_public`` toggle so it cannot be made public again.
        if (
            self.instance
            and self.instance.pk
            and self.instance.approval_status == Event.ApprovalStatus.REJECTED
            and "is_public" in self.fields
        ):
            self.fields["is_public"].disabled = True
            self.fields["is_public"].help_text = (
                "This event's public request was rejected and cannot be made public again."
            )

    def clean(self):
        cleaned = super().clean()
        # A rejected public event's public flag is final and cannot change.
        if self.instance and self.instance.pk and self.instance.approval_status == Event.ApprovalStatus.REJECTED:
            cleaned["is_public"] = self.instance.is_public
        # National events are always public.
        if cleaned.get("is_national"):
            cleaned["is_public"] = True
        return cleaned

    def clean_is_national(self):
        is_national = self.cleaned_data.get("is_national", False)
        if is_national and not user_is_national_officer(self.request_user):
            raise forms.ValidationError("Only National Officers can create national events.")
        return is_national


class CalendarFeedSubscriptionForm(forms.ModelForm):
    """Configure a private iCal subscription — public events of chosen
    chapters/regions, national events, and optionally the member's to-dos."""

    task_owner_roles = task_owner_roles_field()

    class Meta:
        model = CalendarFeedSubscription
        fields = ["name", "include_national", "include_todos", "task_owner_roles", "regions", "chapters"]
        widgets = {
            "regions": autocomplete.ModelSelect2Multiple(
                url="events:region-feed-autocomplete",
                attrs={
                    "data-placeholder": "Type to add regions\u2026",
                    "data-minimum-input-length": 0,
                },
            ),
            "chapters": autocomplete.ModelSelect2Multiple(
                url="events:chapter-feed-autocomplete",
                attrs={
                    "data-placeholder": "Type to add chapters\u2026",
                    "data-minimum-input-length": 0,
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["regions"].queryset = Region.objects.all().order_by("name")
        self.fields["regions"].required = False
        self.fields["chapters"].queryset = Chapter.objects.filter(active=True).order_by("name")
        self.fields["chapters"].required = False
        self.fields["name"].widget.attrs.setdefault("class", "form-control")
        self.fields["include_national"].widget.attrs.setdefault("class", "form-check-input")
        self.fields["include_todos"].widget.attrs.setdefault("class", "form-check-input")


class TaskFeedForm(forms.Form):
    """Create a to-dos-only calendar feed, optionally limited to officer roles."""

    name = forms.CharField(
        max_length=100,
        initial="My Task Reminders",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    task_owner_roles = task_owner_roles_field()
