from django.contrib import messages
from django.db.models import OuterRef, Subquery
from django.utils.dateparse import parse_date
from django.views.generic import TemplateView

from core.views import LoginRequiredMixin, PagedFilteredTableView, SuperuserRequiredMixin
from thetatauCMT.users.models import UserStatusChange

from .filters import TrainingListFilter
from .forms import TrainingListFormHelper
from .models import Training
from .services import chapter_completion_stats, default_window
from .tables import TrainingTable


class TrainingListView(LoginRequiredMixin, PagedFilteredTableView):
    model = Training
    # Most recent PNM status, so a member who re-pledged shows their current class.
    queryset = Training.objects.annotate(
        pledge_date=Subquery(
            UserStatusChange.objects.filter(user=OuterRef("user"), status="pnm").order_by("-start").values("start")[:1]
        )
    )
    context_object_name = "training"
    ordering = ["-completed_time"]
    table_class = TrainingTable
    filter_class = TrainingListFilter
    formhelper_class = TrainingListFormHelper
    filter_user_chapter = True


class CommunityEduCompletionView(LoginRequiredMixin, SuperuserRequiredMixin, TemplateView):
    """Admin tool: calculate Vector/CommunityEdu completion % per chapter.

    Shows, for every active chapter, how many prior-year new members
    completed the required CommunityEdu training and lets an admin apply the
    resulting `Chapter.SURCHARGE` bracket directly to the chapter. Restricted
    to Admins (not just National Officers) so "Hide admin functionality"
    correctly hides it.
    """

    template_name = "trainings/community_edu_completion.html"

    def _window(self):
        default_start, default_end = default_window()
        params = self.request.POST if self.request.method == "POST" else self.request.GET
        start_date = parse_date(params.get("start", "") or "") or default_start
        end_date = parse_date(params.get("end", "") or "") or default_end
        return start_date, end_date

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        start_date, end_date = self._window()
        context["start_date"] = start_date
        context["end_date"] = end_date
        context["stats"] = chapter_completion_stats(start_date=start_date, end_date=end_date)
        return context

    def post(self, request, *args, **kwargs):
        start_date, end_date = self._window()
        stats = chapter_completion_stats(start_date=start_date, end_date=end_date)
        apply_all = "apply_all" in request.POST
        apply_chapter_pk = request.POST.get("apply_chapter")
        applied = 0
        for stat in stats:
            if stat.surcharge_bracket is None:
                continue
            if not (apply_all or str(stat.chapter.pk) == apply_chapter_pk):
                continue
            if stat.chapter.health_safety_surcharge != stat.surcharge_bracket:
                stat.chapter.health_safety_surcharge = stat.surcharge_bracket
                stat.chapter.save(update_fields=["health_safety_surcharge"])
            applied += 1
        if applied:
            messages.add_message(
                request,
                messages.SUCCESS,
                f"Applied the calculated surcharge to {applied} chapter{'s' if applied != 1 else ''}.",
            )
        else:
            messages.add_message(request, messages.WARNING, "No chapters were updated.")
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)
