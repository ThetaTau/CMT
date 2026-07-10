"""Forms for the attendance module."""

from dal import autocomplete, forward
from django import forms

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
