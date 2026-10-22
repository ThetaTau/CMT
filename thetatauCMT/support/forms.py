from django import forms
from django.utils import timezone

from thetatauCMT.chapters.models import Chapter
from thetatauCMT.users.models import User

from .services import css_chapters


class CSSInfoForm(forms.ModelForm):
    """Edit My Info for a Chapter Support Specialist staff account (Q5): no member fields."""

    class Meta:
        model = User
        fields = [
            "first_name",
            "preferred_name",
            "last_name",
            "preferred_pronouns",
            "email",
            "email_visibility",
            "phone_number",
            "phone_visibility",
        ]
        labels = {
            "email_visibility": "Who can see my email?",
            "phone_visibility": "Who can see my phone number?",
        }


class CSSChapterForm(forms.Form):
    """Pick which assigned chapter to view. Only current assignments are offered or accepted."""

    chapter = forms.ChoiceField(label="Chapter")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.chapters = {chapter.slug: chapter for chapter in css_chapters(user)} if user is not None else {}
        self.fields["chapter"].choices = [(slug, chapter.name) for slug, chapter in self.chapters.items()]

    def clean_chapter(self):
        slug = self.cleaned_data["chapter"]
        chapter = self.chapters.get(slug)
        if chapter is None:
            raise forms.ValidationError("You are not assigned to that chapter.")
        return chapter


class DateInput(forms.DateInput):
    input_type = "date"


class CSSCreateForm(forms.Form):
    """A new Chapter Support Specialist (CSSWI-5)."""

    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField(
        help_text=(
            "If someone in the CMT already uses this email, such as an alumnus, they keep their "
            "account and membership and gain the role. Otherwise a new account is made and "
            "emailed a link to set its password."
        )
    )


class CSSAssignForm(forms.Form):
    """Assign a chapter to a CSS. Offers active chapters they do not already cover (S2, S15)."""

    chapter = forms.ModelChoiceField(queryset=Chapter.objects.none())
    start = forms.DateField(initial=timezone.localdate, widget=DateInput())
    end = forms.DateField(
        required=False,
        widget=DateInput(),
        help_text="Leave empty while the assignment is open. Access ends after this date.",
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Only Chapter Support Specialist managers see this.",
    )

    def __init__(self, *args, css, **kwargs):
        super().__init__(*args, **kwargs)
        covered = css.support_assignments.exclude(end__lt=timezone.localdate()).values_list("chapter_id", flat=True)
        self.fields["chapter"].queryset = (
            Chapter.objects.filter(active=True).exclude(pk=css.chapter_id).exclude(pk__in=covered).order_by("name")
        )


class CSSEndForm(forms.Form):
    end = forms.DateField(
        label="End date",
        widget=DateInput(),
        help_text="Access ends after this date. Choose yesterday to end it now.",
    )
