from django.urls import reverse
from django.views.generic import CreateView
from django.shortcuts import redirect
from django.http import Http404
from django.http.response import HttpResponseRedirect
from django.forms.models import modelformset_factory
from django.contrib import messages
from core.forms import MultiFormsView
from core.views import (
    LoginRequiredMixin,
    NatOfficerRequiredMixin,
)
from chapters.models import Chapter
from users.models import User
from .models import ChapterNote, UserNote
from .forms import ChapterNoteForm


class ChapterNoteDetailView(LoginRequiredMixin, MultiFormsView):
    template_name = "notes/note_detail.html"
    model = ChapterNote
    form_classes = {
        "note": ChapterNoteForm,
        "subnotes": None,
    }

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if (
            self.object.restricted and not request.user.is_council_officer
        ) and not request.user.is_superuser:
            messages.add_message(
                request,
                messages.INFO,
                f"You do not have permission to see this note.",
            )
            return redirect(
                reverse(
                    "chapters:detail",
                    kwargs={"slug": self.request.user.current_chapter.slug},
                )
            )
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        messages.add_message(
            self.request,
            messages.INFO,
            f"Note successfully updated",
        )
        return reverse("notes:detail", kwargs={"pk": self.object.pk})

    def _get_form_kwargs(self, form_name, bind_form=False):
        kwargs = super()._get_form_kwargs(form_name, bind_form)
        if form_name == "note":
            kwargs.update(
                {
                    "instance": self.object,
                }
            )
        return kwargs

    def note_form_valid(self, form):
        if form.has_changed():
            form.save()
        return HttpResponseRedirect(self.get_success_url())

    def subnotes_form_valid(self, formset):
        instances = formset.save(commit=False)
        for instance in instances:
            instance.parent = self.object
            instance.chapter = self.object.chapter
            if instance.created_by is None:
                instance.created_by = self.request.user
            instance.modified_by = self.request.user
            instance.save()
        formset.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_object(self):
        pk = self.kwargs.get("pk")
        queryset = self.model._default_manager.all()
        if pk is not None:
            queryset = queryset.filter(pk=pk)
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                f"No {queryset.model._meta.verbose_name}s found matching the query"
            )
        return obj

    def create_subnotes_form(self, **kwargs):
        subnotes = self.object.subnotes.all()
        extra = 0
        if not subnotes:
            extra = 1
        factory = modelformset_factory(
            ChapterNote, form=ChapterNoteForm, **{"can_delete": True, "extra": extra}
        )
        formset_kwargs = {
            "queryset": subnotes,
        }
        if self.request.method in ("POST", "PUT"):
            if self.request.POST.get("action") == "subnotes":
                formset_kwargs.update(
                    {
                        "data": self.request.POST.copy(),
                        "files": self.request.FILES.copy(),
                    }
                )
        return factory(**formset_kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object"] = self.object
        return context


class ChapterNoteCreateView(
    LoginRequiredMixin,
    NatOfficerRequiredMixin,
    CreateView,
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
    LoginRequiredMixin,
    NatOfficerRequiredMixin,
    CreateView,
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
