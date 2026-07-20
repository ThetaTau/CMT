from dal import autocomplete, forward
from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class MemberCommunicationForm(forms.Form):
    """Pick a member (autocomplete) OR type any email to look up in Mailjet."""

    member = forms.ModelChoiceField(
        label="Member",
        queryset=User.objects.all(),
        required=False,
        widget=autocomplete.ModelSelect2(
            url="users:autocomplete",
            forward=(forward.Const("false", "chapter"),),
            attrs={
                "data-placeholder": "Search members by name…",
                "data-minimum-input-length": 2,
            },
        ),
    )
    email = forms.EmailField(
        label="Or look up any email address",
        required=False,
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "name@example.com"}),
    )
    date_from = forms.DateField(
        label="From date",
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    date_to = forms.DateField(
        label="To date",
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    subject = forms.CharField(
        label="Subject contains",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. invoice"}),
    )

    def clean(self):
        cleaned = super().clean()
        date_from = cleaned.get("date_from")
        date_to = cleaned.get("date_to")
        if date_from and date_to and date_from > date_to:
            self.add_error("date_to", "The 'To date' must be on or after the 'From date'.")
        return cleaned
