from datetime import datetime
from django.urls import reverse
from django.views.generic import DetailView, RedirectView
from core.views import PagedFilteredTableView, RequestConfig, LoginRequiredMixin
from .models import ScoreType, ScoreChapter
from .tables import ScoreTable, ChapterScoreTable
from events.tables import EventTable
from chapters.models import Chapter
from submissions.tables import SubmissionTable
from core.models import BIENNIUM_START
from .filters import ScoreListFilter, ChapterScoreListFilter
from .forms import ScoreListFormHelper, ChapterScoreListFormHelper


class ScoreDetailView(LoginRequiredMixin, DetailView):
    model = ScoreType
    # These next two lines tell the view to index lookups by chapter
    slug_field = "slug"
    slug_url_kwarg = "slug"
    template_name = "scores/score_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if context["object"].type == "Evt":
            chapter_events = context["object"].events.filter(
                chapter=self.request.user.current_chapter
            )
            table = EventTable(data=chapter_events)
        elif context["object"].type == "Sub":
            chapter_submissions = context["object"].submissions.filter(
                chapter=self.request.user.current_chapter
            )
            table = SubmissionTable(data=chapter_submissions)
        else:
            context["table"] = ScoreType.objects.none()
            return context
        RequestConfig(self.request, paginate={"per_page": 50}).configure(table)
        context["table"] = table
        return context


class ScoreRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse(
            "scores:detail", kwargs={"chapter": self.request.user.current_chapter}
        )


class ScoreListView(LoginRequiredMixin, PagedFilteredTableView):
    model = ScoreType
    template_name = "scores/score_list.html"
    slug_field = "slug"
    slug_url_kwarg = "slug"
    context_object_name = "event"
    ordering = ["name"]
    table_class = ScoreTable
    filter_class = ScoreListFilter
    formhelper_class = ScoreListFormHelper
    table_pagination = {"per_page": 50}

    def get_queryset(self):
        request_get = self.request.GET.copy()
        cancel = self.request.GET.get("cancel", False)
        start_year = None
        if not cancel:
            start_year = request_get.get("start_year", None)
            start_year = None if not start_year else start_year
        self.start_year = start_year
        qs = super().get_queryset()
        score_list = self.model.annotate_chapter_score(
            self.request.user.current_chapter,
            qs=qs,
            start_year=self.start_year,
        )
        return score_list

    def get_table_kwargs(self):
        return {"start_year": self.start_year}


class ChapterScoreListView(LoginRequiredMixin, PagedFilteredTableView):
    model = Chapter
    template_name = "scores/chapterscore_list.html"
    slug_field = "slug"
    slug_url_kwarg = "slug"
    context_object_name = "scores"
    ordering = ["name"]
    table_class = ChapterScoreTable
    filter_class = ChapterScoreListFilter
    formhelper_class = ChapterScoreListFormHelper
    table_pagination = {"per_page": 150}

    def get_queryset(self):
        request_get = self.request.GET.copy()
        cancel = self.request.GET.get("cancel", False)
        term = "fa"
        year = BIENNIUM_START
        if not cancel:
            year = request_get.get("year", BIENNIUM_START)
            year = BIENNIUM_START if not year else year
            term = request_get.get("term", "fa")
            term = "fa" if not term else term
        qs = super().get_queryset(request_get=request_get)
        month = {"sp": 3, "fa": 10}[term]
        date = datetime(int(year), month, 1)
        data = ScoreChapter.type_score_biennium(date=date, chapters=qs)
        return data
