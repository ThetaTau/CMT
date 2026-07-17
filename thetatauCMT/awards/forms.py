from crispy_forms.bootstrap import FormActions, InlineField, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Fieldset, Layout, Row, Submit
from dal import autocomplete, forward
from django import forms

from thetatauCMT.chapters.models import Chapter
from thetatauCMT.regions.models import Region
from thetatauCMT.users.models import User

from .eligibility import is_eligible
from .models import AwardCycle, AwardNominationProcess, AwardType
from .services import count_active_winners, count_nominations_for, nominatable_award_types, resolve_current_cycle

NOT_ELIGIBLE_NOM_MSG = "This recipient is not eligible for this award, or is outside your scope."
ALREADY_NOMINATED_MSG = "This recipient has already been nominated for this award this cycle."
WINNER_LIMIT_MSG = "This award allows only one winner per cycle; a winner already exists -- cannot approve."


class AwardDirectoryFilterHelper(FormHelper):
    """Crispy helper for the public award-winner directory filter (AWI-11)."""

    form_method = "GET"
    form_id = "award-directory-search-form"
    form_class = "form-inline"
    field_template = "bootstrap5/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True

    def __init__(self, form=None):
        self.layout = Layout(
            Fieldset(
                '<i class="fas fa-search"></i> Filter Award Winners',
                Row(
                    InlineField("recipient"),
                    InlineField("award_type"),
                    InlineField("level"),
                    InlineField("cycle"),
                    InlineField("chapter"),
                    InlineField("region"),
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


class DirectGrantForm(forms.Form):
    """Grant a direct award to one eligible recipient.

    Only active, ``direct``-grantable awards are offered. Exactly one recipient
    field -- matching the award's level-derived recipient kind -- must be set;
    eligibility, actor scope, and winner rules are enforced server-side by
    :func:`thetatauCMT.awards.services.direct_grant`.
    """

    award_type = forms.ModelChoiceField(queryset=AwardType.objects.none(), label="Award")
    cycle = forms.ModelChoiceField(queryset=AwardCycle.objects.all(), label="Award Period")
    recipient_member = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label="Member recipient",
        widget=autocomplete.ModelSelect2(
            url="users:autocomplete",
            forward=(forward.Const("false", "chapter"),),
        ),
        help_text="For member / alumni / active / PNM / national awards.",
    )
    recipient_chapter = forms.ModelChoiceField(
        queryset=Chapter.objects.filter(active=True),
        required=False,
        label="Chapter recipient",
        help_text="For chapter awards.",
    )
    recipient_region = forms.ModelChoiceField(
        queryset=Region.objects.all(),
        required=False,
        label="Region recipient",
        help_text="For region awards.",
    )
    effective_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Leave blank for today. May be backdated for historical records.",
    )
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("request_user", None)
        super().__init__(*args, **kwargs)
        self.fields["award_type"].queryset = AwardType.objects.active().filter(
            grant_method=AwardType.GrantMethod.DIRECT
        )
        current = resolve_current_cycle()
        if current is not None:
            self.fields["cycle"].initial = current.pk

    def clean(self):
        cleaned = super().clean()
        award = cleaned.get("award_type")
        if award is None:
            return cleaned
        kind = award.recipient_kind
        by_kind = {
            "member": cleaned.get("recipient_member"),
            "chapter": cleaned.get("recipient_chapter"),
            "region": cleaned.get("recipient_region"),
        }
        chosen = by_kind[kind]
        wrong = [k for k, value in by_kind.items() if k != kind and value is not None]
        if chosen is None:
            raise forms.ValidationError(f"Select a {kind} recipient for this award.")
        if wrong:
            raise forms.ValidationError(f"This is a {kind}-level award; only the {kind} recipient should be set.")
        cleaned["recipient"] = chosen
        return cleaned


class AwardNominationForm(forms.ModelForm):
    """Role-scoped award nomination entry.

    The award list is limited to nomination-workflow awards the actor may
    nominate for (:func:`nominatable_award_types`). Exactly the recipient field
    matching the award's kind must be set; the recipient must be eligible (and
    in the actor's scope, per AWI-4) and must not violate the per-cycle
    multiple-nomination rule (AWI-2).
    """

    class Meta:
        model = AwardNominationProcess
        fields = [
            "award_type",
            "cycle",
            "recipient_member",
            "recipient_chapter",
            "recipient_region",
            "justification",
            "supporting_docs",
        ]
        widgets = {
            "recipient_member": autocomplete.ModelSelect2(
                url="awards:recipient_member_autocomplete",
                forward=(forward.Field("award_type"), forward.Field("cycle")),
            ),
            "justification": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, request_user=None, **kwargs):
        self.request_user = request_user
        super().__init__(*args, **kwargs)
        self.fields["award_type"].queryset = nominatable_award_types(request_user)
        self.fields["award_type"].label = "Award"
        self.fields["recipient_chapter"].queryset = Chapter.objects.filter(active=True)
        for name in ("recipient_member", "recipient_chapter", "recipient_region"):
            self.fields[name].required = False
        # Clearer standalone labels -- only the field matching the selected award's
        # kind is shown (JS in the template), so each reads naturally on its own.
        self.fields["recipient_member"].label = "Member"
        self.fields["recipient_chapter"].label = "Chapter"
        self.fields["recipient_region"].label = "Region"
        self.fields["cycle"].label = "Award Period"
        self.fields["cycle"].queryset = AwardCycle.objects.current()
        current = resolve_current_cycle()
        if current is not None:
            self.fields["cycle"].initial = current.pk

    def clean(self):
        cleaned = super().clean()
        award = cleaned.get("award_type")
        if award is None:
            return cleaned
        kind = award.recipient_kind
        by_kind = {
            "member": cleaned.get("recipient_member"),
            "chapter": cleaned.get("recipient_chapter"),
            "region": cleaned.get("recipient_region"),
        }
        chosen = by_kind[kind]
        wrong = [k for k, value in by_kind.items() if k != kind and value is not None]
        if chosen is None:
            raise forms.ValidationError(f"Select a {kind} recipient for this award.")
        if wrong:
            raise forms.ValidationError(f"This is a {kind}-level award; only the {kind} recipient should be set.")
        cycle = cleaned.get("cycle")
        if not is_eligible(award, chosen, cycle=cycle, actor=self.request_user):
            raise forms.ValidationError(NOT_ELIGIBLE_NOM_MSG)
        if not award.can_add_nomination(count_nominations_for(award, cycle, chosen)):
            raise forms.ValidationError(ALREADY_NOMINATED_MSG)
        cleaned["recipient"] = chosen
        return cleaned


class AwardNominationReviewForm(forms.ModelForm):
    """Reviewer decision form: approve or reject a nomination.

    Enforces the per-cycle winner rules (AWI-2) when approving -- a single-winner
    award cannot be approved for a second recipient in the same cycle.
    """

    class Meta:
        model = AwardNominationProcess
        fields = ["result", "reject_reason", "review_notes"]
        widgets = {
            "reject_reason": forms.Textarea(attrs={"rows": 2}),
            "review_notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["result"].required = True
        self.fields["result"].choices = [
            (AwardNominationProcess.Result.APPROVED.value, AwardNominationProcess.Result.APPROVED.label),
            (AwardNominationProcess.Result.REJECTED.value, AwardNominationProcess.Result.REJECTED.label),
        ]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("result") == AwardNominationProcess.Result.APPROVED:
            award = self.instance.award_type
            cycle = self.instance.cycle
            if not award.can_add_winner(count_active_winners(award, cycle)):
                raise forms.ValidationError(WINNER_LIMIT_MSG)
        return cleaned
