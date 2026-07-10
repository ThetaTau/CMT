from crispy_forms.bootstrap import FormActions, InlineField, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Fieldset, Layout, Row, Submit
from dal import autocomplete, forward
from django import forms

from core.models import user_is_national_officer

from .models import Event, Picture


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
