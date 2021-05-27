from django.urls import reverse
from django.views.generic import DetailView, RedirectView
from core.views import PagedFilteredTableView, RequestConfig, LoginRequiredMixin
from .models import ScoreType, ScoreChapter
from .tables import ScoreTable, ChapterScoreTable
from events.tables import EventTable
from chapters.models import Chapter
from submissions.tables import SubmissionTable
from .filters import ScoreListFilter, ChapterScoreListFilter, BIENNIUM_FILTERS
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
        qs = super().get_queryset()
        score_list = self.model.annotate_chapter_score(
            self.request.user.current_chapter, qs
        )
        return score_list


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
        date_info = request_get.get("date", "")
        cancel = self.request.GET.get("cancel", False)
        qs = super().get_queryset(request_get=request_get, clean_date=True,)
        date = None
        if date_info and not cancel:
            date = BIENNIUM_FILTERS[(date_info, date_info.replace("_", " "))][0]
        data = ScoreChapter.type_score_biennium(date=date, chapters=qs)
        return data
