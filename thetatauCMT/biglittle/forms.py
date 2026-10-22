from dal import autocomplete, forward
from django import forms
from django.urls import reverse

from thetatauCMT.users.models import User

from . import services

FINAL_BIG_HELP = "The final Big Brother mentor, chosen at initiation, not a temporary one."
NOT_INITIATED_MESSAGE = "You can record Bigs and Littles after you are initiated."
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
SEARCH_HELP = "Used instead of a suggestion when filled in."
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
            "One Little per row. Name each side by badge number (badge_number_big, badge_number_little) "
            "or by full name (big_full_name, little_full_name). Other columns are ignored."
        ),
    )

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if not (uploaded.name or "").lower().endswith(".csv"):
            raise forms.ValidationError("Please upload a .csv file.")
        if uploaded.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError("The file is too large (5 MB at most).")
        return uploaded


class PendingPairingForm(forms.Form):
    """Pick the members an uploaded row means: a suggestion, or anyone found by searching."""

    little = forms.TypedChoiceField(
        label="Suggested Littles",
        coerce=int,
        empty_value=None,
        required=False,
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
    )
    little_other = member_choice_field("Or search for the Little", help_text=SEARCH_HELP, required=False)
    big = forms.TypedChoiceField(
        label="Suggested Bigs",
        coerce=int,
        empty_value=None,
        required=False,
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
    )
    big_other = member_choice_field(
        "Or search for the Big", help_text=f"{SEARCH_HELP} {FINAL_BIG_HELP}", required=False
    )

    def __init__(self, *args, item, choices, chapter, **kwargs):
        super().__init__(*args, prefix=f"row-{item.pk}", **kwargs)
        self.item = item
        self.members = services.eligible_members(chapter)
        for side in services.SIDES:
            options = choices[item.pk, side]
            self.fields[side].choices = options
            if options:
                self.initial[side] = options[0][0]
            self.fields[f"{side}_other"].queryset = self.members

    def clean(self):
        cleaned = super().clean()
        picked = {}
        for side in services.SIDES:
            member = cleaned.get(f"{side}_other")
            if member is None and cleaned.get(side) is not None:
                member = self.members.filter(pk=cleaned[side]).first()
            if member is None and f"{side}_other" not in self.errors:
                self.add_error(f"{side}_other", f"Choose the {side.title()}, or dismiss this row.")
            picked[side] = member
        if picked["little"] is not None and picked["big"] is not None:
            try:
                services.validate_pairing(picked["little"], picked["big"])
            except services.BigLittleError as error:
                self.add_error(None, error)
        cleaned["little_member"], cleaned["big_member"] = picked["little"], picked["big"]
        return cleaned


class FamilyTreeSearchForm(forms.Form):
    """Find someone in one chapter's family tree; the page then opens and highlights their family."""

    member = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label="Find a member",
        required=False,
        widget=autocomplete.ModelSelect2(attrs={"data-placeholder": "Type a name or badge number"}),
    )

    def __init__(self, *args, chapter, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields["member"]
        field.queryset = services.tree_members(chapter)
        field.label_from_instance = services.member_label
        field.widget.url = reverse("biglittle:tree-members", kwargs={"slug": chapter.slug})
