from tempus_dominus.widgets import DatePicker
from django import forms
from dal import autocomplete, forward
from users.models import User
from .models import ChapterNote


class ChapterNoteForm(forms.ModelForm):
    owner = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="users:autocomplete",
            forward=(
                forward.Const("true", "chapter"),
                forward.Const("true", "actives"),
            ),
        ),
    )
    date = forms.DateField(
        label="When do you want the action to be accomplished by?",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )

    class Meta:
        model = ChapterNote
        fields = [
            "title",
            "type",
            "restricted",
            "note",
            "file",
        ]
