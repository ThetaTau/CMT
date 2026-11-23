"""Forms for the Case Competition pages (NECCWI-5, 6, 9 and 10)."""

from dal import autocomplete, forward
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.models import Q
from django.forms import inlineformset_factory

from thetatauCMT.users.models import User

from . import services, uploads
from .models import Entry, EntryMember, SubmissionItem

MEMBER_PLACEHOLDER = "Type a name or badge number"
DATETIME_FORMAT = "%Y-%m-%dT%H:%M"


def chapter_members(chapter):
    """The chapter's current members and PNMs: who a team or the contacts may name (S29)."""
    if chapter is None:
        return User.objects.none()
    return chapter.members.filter(current_status__in=services.MEMBER_STATUSES).order_by("name")


def member_label(user):
    return f"{user.name} (PNM)" if user.current_status == "pnm" else user.name


def _member_widget(chapter, multiple=False, label=""):
    widget_class = autocomplete.ModelSelect2Multiple if multiple else autocomplete.ModelSelect2
    forwards = [forward.Const(chapter.slug, "chapter")] if chapter is not None else []
    attrs = {"data-placeholder": MEMBER_PLACEHOLDER}
    if label:
        attrs["aria-label"] = label
    return widget_class(url="competitions:member-autocomplete", forward=forwards, attrs=attrs)


class ParticipationForm(forms.Form):
    """Register the chapter, or update its registration (Q8 A)."""

    contacts = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="Main contacts",
        help_text="The members in charge of the chapter's entry. They also get the chapter's competition emails.",
    )
    team_size_estimate = forms.IntegerField(
        label="Estimated team size",
        required=False,
        min_value=1,
        max_value=100,
        help_text="How many members expect to take part.",
    )
    note = forms.CharField(
        label="A note for national",
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Optional. Anything the competition managers should know.",
    )

    def __init__(self, *args, chapter, participant=None, **kwargs):
        if participant is not None:
            kwargs.setdefault(
                "initial",
                {
                    "contacts": list(participant.contacts.values_list("pk", flat=True)),
                    "team_size_estimate": participant.team_size_estimate,
                    "note": participant.note,
                },
            )
        super().__init__(*args, **kwargs)
        current = list(participant.contacts.values_list("pk", flat=True)) if participant is not None else []
        field = self.fields["contacts"]
        field.queryset = User.objects.filter(Q(pk__in=chapter_members(chapter)) | Q(pk__in=current)).order_by("name")
        field.label_from_instance = member_label
        field.widget = _member_widget(chapter, multiple=True)
        field.widget.choices = field.choices


class EntryForm(forms.Form):
    """The entry: title, summary, and one upload or link per item of the round (Q10 A).

    Nothing is required to save (S6): the page shows what is still missing. A new file
    replaces the item's current one; an emptied link removes it.
    """

    title = forms.CharField(label="Project title", max_length=200, required=False)
    summary = forms.CharField(
        label="Summary",
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 5, "maxlength": 1000}),
        help_text="Up to 1,000 characters: the problem, your idea and the impact you expect.",
    )

    def __init__(self, *args, round_, entry=None, **kwargs):
        if entry is not None:
            kwargs.setdefault("initial", {"title": entry.title, "summary": entry.summary})
        super().__init__(*args, **kwargs)
        self.round = round_
        self.items = list(round_.items.all())
        self.current = services.current_files(entry)
        for item in self.items:
            existing = self.current.get(item.pk)
            if item.kind == SubmissionItem.Kind.LINK:
                self.fields[self.field_name(item)] = forms.URLField(
                    label=item.label,
                    required=False,
                    max_length=500,
                    validators=[URLValidator(schemes=["http", "https"])],
                    initial=existing.link if existing is not None else "",
                    help_text=item.description or "A link anyone with it can open, such as a video on YouTube.",
                    widget=forms.URLInput(attrs={"placeholder": "https://"}),
                )
            else:
                limits = f"{uploads.describe(item.file_types)}, up to {item.max_size_mb} MB."
                self.fields[self.field_name(item)] = forms.FileField(
                    label=item.label,
                    required=False,
                    help_text=" ".join(part for part in (item.description, limits) if part),
                    widget=forms.FileInput(attrs={"accept": uploads.accept_attribute(item.file_types)}),
                )

    @staticmethod
    def field_name(item):
        return f"item_{item.pk}"

    def item_fields(self):
        """``(item, bound field, current file)`` for the template."""
        return [(item, self[self.field_name(item)], self.current.get(item.pk)) for item in self.items]

    def clean(self):
        cleaned = super().clean()
        for item in self.items:
            upload = cleaned.get(self.field_name(item))
            if item.kind == SubmissionItem.Kind.FILE and upload:
                try:
                    uploads.check_upload(upload, item)
                except ValidationError as error:
                    self.add_error(self.field_name(item), error)
        return cleaned

    def uploads(self):
        return {
            item: self.cleaned_data[self.field_name(item)]
            for item in self.items
            if item.kind == SubmissionItem.Kind.FILE and self.cleaned_data.get(self.field_name(item))
        }

    def links(self):
        return {
            item: self.cleaned_data.get(self.field_name(item)) or ""
            for item in self.items
            if item.kind == SubmissionItem.Kind.LINK
        }


class TeamMemberForm(forms.ModelForm):
    class Meta:
        model = EntryMember
        fields = ["user", "team_role"]
        labels = {"user": "Member", "team_role": "Role on the team"}
        widgets = {
            "team_role": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Such as Team lead", "aria-label": "Role on the team"}
            )
        }

    def __init__(self, *args, chapter=None, team_ids=(), **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields["user"]
        field.queryset = User.objects.filter(Q(pk__in=chapter_members(chapter)) | Q(pk__in=list(team_ids)))
        field.label_from_instance = member_label
        field.widget = _member_widget(chapter, label="Team member")
        field.widget.choices = field.choices
        field.required = False

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("user") and (cleaned.get("team_role") or "").strip() and not self.instance.pk:
            self.add_error("user", "Choose the member, or clear the role.")
        return cleaned


class BaseTeamFormSet(forms.BaseInlineFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        if "DELETE" in form.fields:
            form.fields["DELETE"].label = "Remove"
            form.fields["DELETE"].widget.attrs.update(
                {"class": "form-check-input", "aria-label": "Remove from the team"}
            )


TeamFormSet = inlineformset_factory(
    Entry,
    EntryMember,
    form=TeamMemberForm,
    formset=BaseTeamFormSet,
    extra=3,
    can_delete=True,
    max_num=40,
    validate_max=True,
)


def team_formset(data=None, *, entry, chapter):
    team_ids = list(entry.team.values_list("user_id", flat=True)) if entry is not None and entry.pk else []
    return TeamFormSet(
        data,
        instance=entry if entry is not None else Entry(),
        prefix="team",
        form_kwargs={"chapter": chapter, "team_ids": team_ids},
    )


def save_team(formset, entry):
    """Save the team rows in the order shown; an emptied member deletes the row."""
    formset.instance = entry
    for form in formset.forms:
        if form.instance.pk and not form.cleaned_data.get("user"):
            form.cleaned_data["DELETE"] = True
    formset.save()
    order = 0
    for form in formset.forms:
        if form.instance.pk and EntryMember.objects.filter(pk=form.instance.pk).exists():
            EntryMember.objects.filter(pk=form.instance.pk).update(order=order)
            order += 1


class ExtensionForm(forms.Form):
    until = forms.DateTimeField(
        label="Extended deadline",
        required=False,
        input_formats=[DATETIME_FORMAT],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format=DATETIME_FORMAT),
        help_text="In the competition's time zone. Leave it empty to remove the extension.",
    )


class AddJudgeForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        label="Add a judge",
        help_text="Anyone with a CMT account.",
        widget=autocomplete.ModelSelect2(
            url="competitions:judge-autocomplete", attrs={"data-placeholder": MEMBER_PLACEHOLDER}
        ),
    )


class ScorecardForm(forms.Form):
    """One score and comment per criterion (Q18, Q19), the overall feedback and a private note."""

    feedback = forms.CharField(
        label="Feedback for the chapter",
        required=False,
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text="Needed to submit. The chapter reads it without your name once results are published.",
    )
    private_note = forms.CharField(
        label="Private note",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Optional. Only the competition managers see it.",
    )

    def __init__(self, *args, round_, scorecard=None, **kwargs):
        self.criteria = list(round_.criteria.all())
        if scorecard is not None:
            initial = {"feedback": scorecard.feedback, "private_note": scorecard.private_note}
            for score in scorecard.scores.all():
                initial[f"points_{score.criterion_id}"] = score.points
                initial[f"comment_{score.criterion_id}"] = score.comment
            kwargs.setdefault("initial", initial)
        super().__init__(*args, **kwargs)
        for criterion in self.criteria:
            low, high = round_.score_min, criterion.max_points
            choices = [(str(points), str(points)) for points in range(low, high + 1)]
            self.fields[f"points_{criterion.pk}"] = forms.TypedChoiceField(
                label=criterion.name,
                choices=choices,
                coerce=int,
                empty_value=None,
                required=False,
                widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
                help_text=f"{low} is the lowest and {high} the highest.",
            )
            self.fields[f"comment_{criterion.pk}"] = forms.CharField(
                label=f"Comment on {criterion.name}",
                required=False,
                widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            )

    def criterion_fields(self):
        return [(c, self[f"points_{c.pk}"], self[f"comment_{c.pk}"]) for c in self.criteria]

    def scores(self):
        return {
            criterion.pk: (
                self.cleaned_data.get(f"points_{criterion.pk}"),
                self.cleaned_data.get(f"comment_{criterion.pk}", ""),
            )
            for criterion in self.criteria
        }


class StepAsideForm(forms.Form):
    reason = forms.CharField(
        label="Reason",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Such as a conflict of interest. Only the competition managers see it.",
    )
