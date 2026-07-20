from dal import autocomplete, forward
from django import forms

from core.models import NAT_OFFICERS_CHOICES
from thetatauCMT.users.models import User

from .models import Nomination

# Shown when the nominee has previously responded that they are not interested.
NOT_INTERESTED_MESSAGE = "This person has indicated they are not interested."


class NominationForm(forms.ModelForm):
    """The volunteer recommendation form -- the flow ``Start`` node.

    Only existing members can be nominated (only members can be officers). A
    member may nominate themselves; a self-nomination overrides any previous
    "not interested" response.
    """

    nominee = forms.ModelChoiceField(
        label="Who are you recommending?",
        queryset=User.objects.all(),
        required=True,
        widget=autocomplete.ModelSelect2(
            url="users:autocomplete",
            forward=(forward.Const("false", "chapter"),),
        ),
        help_text="Only existing members can be nominated.",
    )

    class Meta:
        model = Nomination
        fields = [
            "nominee",
            "level",
            "recommended_positions",
            "reason",
            "discussed_with_nominee",
        ]

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("request_user", None)
        super().__init__(*args, **kwargs)

    def is_self_nomination(self):
        nominee = self.cleaned_data.get("nominee")
        return self.request_user is not None and nominee is not None and nominee.pk == self.request_user.pk

    def clean(self):
        cleaned = super().clean()
        nominee = cleaned.get("nominee")
        if nominee is None:
            return cleaned
        # Multiple recommendations for the same person are allowed and retained.
        # A prior "not interested" response blocks a fresh recommendation --
        # UNLESS the member is nominating themselves (expressing their own
        # interest), which overrides the previous decline.
        if not self.is_self_nomination() and Nomination.objects.filter(nominee=nominee, not_interested=True).exists():
            raise forms.ValidationError(NOT_INTERESTED_MESSAGE)
        return cleaned


class NomineeConsentForm(forms.Form):
    """The tokenized (no-login) landing form the nominee fills in.

    Offers the three responses; when interested, the nominee may capture the
    positions / level they are interested in. ``note`` is used as the decline
    reason or a follow-up note.
    """

    INTERESTED = Nomination.CONSENT.interested.value[0]
    FOLLOW_UP_LATER = Nomination.CONSENT.follow_up_later.value[0]
    NOT_INTERESTED = Nomination.CONSENT.not_interested.value[0]

    RESPONSE_CHOICES = [
        (INTERESTED, "Yes, I'm interested in serving"),
        (FOLLOW_UP_LATER, "Ask me again later"),
        (NOT_INTERESTED, "No, I'm not interested"),
    ]

    response = forms.ChoiceField(
        label="How would you like to respond?",
        choices=RESPONSE_CHOICES,
        widget=forms.RadioSelect,
    )
    interested_positions = forms.MultipleChoiceField(
        label="Which position(s) interest you?",
        choices=NAT_OFFICERS_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Only needed if you are interested.",
    )
    interested_level = forms.MultipleChoiceField(
        label="Which level(s) interest you?",
        choices=[level.value for level in Nomination.LEVELS],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="You can select more than one.",
    )
    note = forms.CharField(
        label="Anything you'd like to add?",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )
