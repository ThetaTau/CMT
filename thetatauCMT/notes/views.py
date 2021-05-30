from django.urls import reverse
from django.views.generic import CreateView
from core.views import (
    LoginRequiredMixin,
    NatOfficerRequiredMixin,
)
from chapters.models import Chapter
from users.models import User
from .models import ChapterNote, UserNote


class ChapterNoteCreateView(
    LoginRequiredMixin, NatOfficerRequiredMixin, CreateView,
):
    model = ChapterNote
    template_name = "notes/create_form.html"
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


class UserNoteCreateView(
    LoginRequiredMixin, NatOfficerRequiredMixin, CreateView,
):
    model = UserNote
    template_name = "notes/create_form.html"
    fields = [
        "title",
        "type",
        "note",
        "file",
    ]

    def get_success_url(self):
        return reverse("users:info", kwargs={"user_id": self.kwargs["user_id"]})

    def form_valid(self, form):
        """If the form is valid, redirect to the supplied URL."""
        user = self.request.user
        form_user = User.objects.get(user_id=self.kwargs["user_id"])
        instance = form.save(commit=False)
        instance.user = form_user
        instance.created_by = user
        instance.modified_by = user
        instance.save()
        form.save_m2m()
        return super().form_valid(form)
