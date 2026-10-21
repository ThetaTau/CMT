from dal import autocomplete, forward
from django import forms

from thetatauCMT.users.models import User

from . import services

FINAL_BIG_HELP = "The final Big Brother mentor, chosen at initiation, not a temporary one."
NOT_INITIATED_MESSAGE = "You can record Bigs and Littles after you are initiated."
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
# Edit My Info searches the member's own chapter, never the chapter switcher's.
OWN_CHAPTER_FORWARD = (forward.Const("own", "scope"), forward.Const("true", "exclude_self"))


def member_choice_field(label, help_text="", forwards=(), required=True, aria_label=None):
    """A type-to-search member picker; callers set ``queryset`` per request."""
    attrs = {"data-placeholder": "Type a name or badge number"}
    if aria_label:
        attrs["aria-label"] = aria_label
    return forms.ModelChoiceField(
        queryset=User.objects.none(),
        label=label,
        help_text=help_text,
        required=required,
        widget=autocomplete.ModelSelect2(url="biglittle:member-autocomplete", forward=forwards, attrs=attrs),
    )


class RecordBigForm(forms.Form):
    little = member_choice_field("Little")
    big = member_choice_field("Big", help_text=FINAL_BIG_HELP)

    def __init__(self, *args, chapter=None, **kwargs):
        super().__init__(*args, **kwargs)
        members = services.eligible_members(chapter)
        self.fields["little"].queryset = members
        self.fields["big"].queryset = members

    def clean(self):
        cleaned = super().clean()
        little, big = cleaned.get("little"), cleaned.get("big")
        if little is not None and big is not None:
            try:
                services.validate_pairing(little, big)
            except services.BigLittleError as error:
                self.add_error("big", error)
        return cleaned


class _OwnPairingForm(forms.Form):
    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields[self.field_name].queryset = services.eligible_members(user.chapter).exclude(pk=user.pk)

    def clean(self):
        cleaned = super().clean()
        if not services.is_initiated(self.user):
            raise forms.ValidationError(NOT_INITIATED_MESSAGE)
        other = cleaned.get(self.field_name)
        if other is not None:
            little, big = (self.user, other) if self.field_name == "big" else (other, self.user)
            try:
                services.validate_pairing(little, big)
            except services.BigLittleError as error:
                self.add_error(self.field_name, error)
        return cleaned


class MyBigForm(_OwnPairingForm):
    field_name = "big"
    big = member_choice_field("My Big", help_text=FINAL_BIG_HELP, forwards=OWN_CHAPTER_FORWARD)


class AddLittleForm(_OwnPairingForm):
    field_name = "little"
    little = member_choice_field(
        "Add a Little",
        help_text="A member of your chapter who has no Big recorded yet.",
        forwards=OWN_CHAPTER_FORWARD,
    )

    def clean_little(self):
        little = self.cleaned_data["little"]
        existing = services.current_big(little)
        if existing is not None:
            raise forms.ValidationError(
                f"{little} already has a Big recorded ({existing}). Ask a chapter officer to change it."
            )
        return little


class BigLittleUploadForm(forms.Form):
    file = forms.FileField(
        label="CSV file",
        help_text=(
            "Columns badge_number_big and badge_number_little, with one Little per row. "
            "Other columns, such as names, are ignored."
        ),
    )

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if not (uploaded.name or "").lower().endswith(".csv"):
            raise forms.ValidationError("Please upload a .csv file.")
        if uploaded.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError("The file is too large (5 MB at most).")
        return uploaded
