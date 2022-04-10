from django.urls import reverse
from django.db import transaction
from django.db.utils import IntegrityError
from django.contrib import messages
from django.views.generic import DetailView, UpdateView, RedirectView, CreateView
from core.views import (
    PagedFilteredTableView,
    TypeFieldFilteredChapterAdd,
    OfficerRequiredMixin,
    LoginRequiredMixin,
    NatOfficerRequiredMixin,
    RequestConfig,
)
from scores.models import ScoreType
from core.forms import MultiFormsView
from .models import Event, Picture
from .tables import EventTable
from .filters import EventListFilter
from .forms import EventListFormHelper, EventForm, PictureForm
from django.http.response import HttpResponseRedirect
from django.forms.models import modelformset_factory
import logging


class EventDetailView(LoginRequiredMixin, DetailView):
    model = Event
    slug_field = "chapter"
    slug_url_kwarg = "chapter"


class EventCreateView(
    LoginRequiredMixin,
    OfficerRequiredMixin,
    CreateView,
    MultiFormsView,
):
    model = Event
    template_name = "events/event_create_form.html"
    officer_edit = "events"
    officer_edit_type = "create"
    score_type = "Evt"
    form_classes = {
        "event": EventForm,
        "picture": PictureForm,
    }
    fields = [
        "name",
        "date",
        "type",
        "description",
        "members",
        "pledges",
        "alumni",
        "guests",
        "duration",
        "stem",
        "host",
        "miles",
        "raised",
        "virtual",
    ]
    grouped_forms = {"eventpage": ["event", "picture"]}

    def get_success_url(self):
        return reverse("events:list")

    def _group_exists(self, group_name):
        return False

    def forms_valid(self, forms):
        event_form = forms["event"]
        picture_forms = forms["picture"]
        chapter = self.request.user.current_chapter
        event_form.instance.chapter = chapter
        try:
            with transaction.atomic():
                event_form.save()
        except IntegrityError:
            message = "Name and date together must be unique. You can have the same name on different date."
            messages.add_message(self.request, messages.ERROR, message)
            event_form.add_error("name", message)
            event_form.add_error("date", message)
            forms["event"] = event_form
            return self.render_to_response(self.get_context_data(forms=forms))
        for picture_form in picture_forms:
            picture_form.instance.event = event_form.instance
            picture_form.save()
        return HttpResponseRedirect(self.get_success_url())

    def create_picture_form(self, **kwargs):
        factory = modelformset_factory(
            Picture, form=PictureForm, **{"can_delete": True, "extra": 1}
        )
        formset_kwargs = dict(queryset=Picture.objects.none())
        if self.request.method in ("POST", "PUT"):
            formset_kwargs.update(
                {"data": self.request.POST.copy(), "files": self.request.FILES.copy()}
            )
        return factory(**formset_kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        descriptions = (
            ScoreType.objects.filter(type=self.score_type)
            .all()
            .values("id", "description", "formula", "points", "slug")
        )
        logging.debug(f"context {context}")
        form = context["forms"]["event"]
        slug = self.kwargs.get("slug")
        if slug:
            score_obj = ScoreType.objects.filter(slug=slug)
            form.initial = {"type": score_obj[0].pk}
            form.fields["type"].queryset = score_obj
        else:
            form.fields["type"].queryset = ScoreType.objects.filter(
                type=self.score_type
            ).all()
        # return form
        context["descriptions"] = descriptions
        return context


class EventCopyView(EventCreateView):
    fields = [
        "name",
        "date",
        "type",
        "description",
        "members",
        "pledges",
        "alumni",
        "guests",
        "duration",
        "stem",
        "host",
        "miles",
        "raised",
        "virtual",
    ]

    def get_event_initial(self):
        event = Event.objects.get(pk=self.kwargs["pk"])
        self.initial = {
            "name": event.name,
            "date": event.date,
            "type": event.type,
            "description": event.description,
            "members": event.members,
            "pledges": event.pledges,
            "alumni": event.alumni,
            "guests": event.guests,
            "duration": event.duration,
            "stem": event.stem,
            "host": event.host,
            "miles": event.miles,
            "raised": event.raised,
            "virtual": event.virtual,
        }
        return self.initial


class EventRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse("events:list")


class EventUpdateView(
    LoginRequiredMixin,
    OfficerRequiredMixin,
    TypeFieldFilteredChapterAdd,
    UpdateView,
):
    officer_edit = "events"
    officer_edit_type = "edit"
    fields = [
        "name",
        "date",
        "type",
        "description",
        "members",
        "pledges",
        "alumni",
        "guests",
        "duration",
        "stem",
        "host",
        "virtual",
        "miles",
        "raised",
    ]
    model = Event

    def get_success_url(self):
        return reverse("events:list")


class EventListView(LoginRequiredMixin, PagedFilteredTableView):
    # These next two lines tell the view to index lookups by username
    model = Event
    slug_field = "chapter"
    slug_url_kwarg = "chapter"
    context_object_name = "event"
    ordering = ["-date"]
    table_class = EventTable
    filter_class = EventListFilter
    formhelper_class = EventListFormHelper
    filter_chapter = True


class EventListAllView(EventListView, NatOfficerRequiredMixin):
    filter_chapter = False
    template_name = "events/event_list_all.html"

    def get_table_kwargs(self):
        return {"natoff": True}

    def get_filter_kwargs(self):
        return {"natoff": True}

    def get_filter_helper_kwargs(self):
        return {"natoff": True}
