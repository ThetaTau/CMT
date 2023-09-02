from django import forms
from .models import ChapterNote


class ChapterNoteForm(forms.ModelForm):
    class Meta:
        model = ChapterNote
        fields = [
            "title",
            "type",
            "restricted",
            "note",
            "file",
        ]
