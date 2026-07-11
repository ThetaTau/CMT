"""Forms for the attendance module."""

from dal import autocomplete, forward
from django import forms
from django.db.models import Q

from thetatauCMT.events.models import Event

from .models import AttendanceRecord

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


class NationalAttendanceUploadForm(forms.Form):
    """National Officer bulk-attendance CSV upload for a national event (WI-7)."""

    event = forms.ModelChoiceField(
        queryset=Event.objects.none(),
        widget=autocomplete.ModelSelect2(
            url="events:event-autocomplete",
            forward=[forward.Const(True, "is_national")],
            attrs={
                "data-placeholder": "Type to search national events…",
                "data-minimum-input-length": 0,
            },
        ),
        help_text="National event to record attendance for (type to search).",
    )
    file = forms.FileField(
        label="Attendance CSV",
        help_text=(
            "CSV with any of: member_id, badge, email, name (or first_name/last_name), "
            "chapter, graduation_year. A member id is optional."
        ),
    )
    default_status = forms.ChoiceField(
        choices=AttendanceRecord.STATUS.choices,
        initial=AttendanceRecord.STATUS.ATTENDED,
        help_text="Status assigned to every matched member from this upload.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["event"].queryset = Event.objects.national().order_by("-date", "name")

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        name = (getattr(uploaded, "name", "") or "").lower()
        if not name.endswith(".csv"):
            raise forms.ValidationError("Please upload a .csv file.")
        if getattr(uploaded, "size", 0) and uploaded.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError("File too large (max 5 MB).")
        return uploaded


class MemberAttendanceForm(forms.Form):
    """Log a member's attendance at an existing chapter or national event (WI-8).

    Members cannot create events — they pick an existing national event or one of
    their own chapter's events via a type-to-search autocomplete (the same widget
    used elsewhere for event lookups). The event queryset is scoped to national +
    the member's chapter so a tampered submission cannot record attendance for an
    unrelated chapter's event.
    """

    event = forms.ModelChoiceField(
        queryset=Event.objects.none(),
        widget=autocomplete.ModelSelect2(
            url="attendance:member-event-autocomplete",
            attrs={
                "data-placeholder": "Type to search your chapter or national events…",
                "data-minimum-input-length": 0,
            },
        ),
        help_text="Search an existing national event or one of your chapter's events.",
    )
    status = forms.ChoiceField(
        choices=AttendanceRecord.STATUS.choices,
        initial=AttendanceRecord.STATUS.ATTENDED,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, member=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.member = member
        scope = Q(is_national=True)
        if member is not None and member.chapter_id:
            scope |= Q(chapter_id=member.chapter_id)
        # Setting ``queryset`` re-binds the widget's ModelChoiceIterator, so it
        # must happen on the class-level widget (do not reassign the widget).
        self.fields["event"].queryset = Event.objects.filter(scope).order_by("-date", "name")
        if member is not None:
            self.fields["event"].widget.forward = [forward.Const(member.pk, "member_pk")]


class NationalEventLookupForm(forms.Form):
    """Type-to-search a national event for the attendance breakdown dashboard (WI-9).

    Only national events are searchable/selectable — the autocomplete forwards
    ``is_national`` and the field queryset is limited to ``Event.objects.national()``.
    """

    event = forms.ModelChoiceField(
        queryset=Event.objects.none(),
        required=False,
        widget=autocomplete.ModelSelect2(
            url="events:event-autocomplete",
            forward=[forward.Const(True, "is_national")],
            attrs={
                "data-placeholder": "Type to search a national event…",
                "data-minimum-input-length": 0,
            },
        ),
        help_text="Search a national event to see its chapter-by-chapter attendance.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["event"].queryset = Event.objects.national().order_by("-date", "name")
