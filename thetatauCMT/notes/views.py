from django.urls import reverse
from django.views.generic import UpdateView, CreateView
from core.views import (
    LoginRequiredMixin,
    NatOfficerRequiredMixin,
)
from chapters.models import Chapter
from .models import ChapterNote


class ChapterNoteCreateView(
    LoginRequiredMixin, NatOfficerRequiredMixin, CreateView,
):
    model = ChapterNote
    template_name_suffix = "_create_form"
    fields = [
        "chapter",
        "title",
        "type",
        "note",
        "file",
    ]

    def get_success_url(self):
        return reverse("chapters:detail", kwargs={"slug": self.kwargs["slug"]})

    def get_initial(self):
        chapter = Chapter.objects.get(slug=self.kwargs["slug"])
        self.initial = {
            "chapter": chapter,
        }
        return self.initial

    def form_valid(self, form):
        """If the form is valid, redirect to the supplied URL."""
        user = self.request.user
        instance = form.save(commit=False)
        instance.created_by = user
        instance.modified_by = user
        instance.save()
        form.save_m2m()
        return super().form_valid(form)
