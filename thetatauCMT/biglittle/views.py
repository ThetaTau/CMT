import json

from dal import autocomplete
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F, Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.functional import cached_property
from django.views.generic import FormView, RedirectView, TemplateView, View
from plotly.offline import get_plotlyjs_version

from core.views import PagedFilteredTableView
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.users.models import User

from . import services, tree
from .filters import BigLittleListFormHelper, BigLittleMemberFilter
from .forms import BigLittleUploadForm, PendingPairingForm, RecordBigForm
from .models import BigLittle, PendingPairing
from .tables import BigLittleMemberTable

PLOTLYJS_URL = f"https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js"


def _return_url(request):
    """Where to go after a POST, from a fixed list rather than a URL in the request."""
    target = request.POST.get("return_to")
    if target == "myinfo":
        return reverse("users:detail") + "#big_little"
    if target == "list" or services.can_manage(request.user, request.user.current_chapter):
        return reverse("biglittle:list")
    return reverse("users:detail") + "#big_little"


def _report_saved(request, result, little, big):
    if result.outcome == services.UNCHANGED:
        messages.info(request, f"No change: {big} was already {little}'s Big.")
    elif result.outcome == services.CHANGED:
        messages.success(request, f"Changed {little}'s Big from {result.previous_big} to {big}.")
    else:
        messages.success(request, f"Recorded {big} as {little}'s Big.")


class BigLittleManagerRequiredMixin(LoginRequiredMixin):
    """Pages that change anyone's pairing in the viewer's current chapter (Q4)."""

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and not services.can_manage(user, user.current_chapter):
            messages.error(
                request,
                f"Only chapter officers and {services.manager_roles_label()} can record Bigs and "
                "Littles for the whole chapter.",
            )
            return HttpResponseRedirect(reverse("biglittle:list"))
        return super().dispatch(request, *args, **kwargs)


class BigLittleMemberAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    """Type-to-search picker over the members who can be a Big or a Little.

    Searches the viewer's current chapter, or their own chapter when the form forwards
    ``scope=own`` (Edit My Info). Never offers a "create" option.
    """

    def get_queryset(self):
        user = self.request.user
        chapter = user.chapter if self.forwarded.get("scope") == "own" else user.current_chapter
        queryset = services.eligible_members(chapter)
        if self.forwarded.get("exclude_self") == "true":
            queryset = queryset.exclude(pk=user.pk)
        term = (self.q or "").strip()
        if term:
            match = Q(name__icontains=term)
            # Nine digits fits a badge number and stays inside the integer column.
            if term.isdigit() and len(term) <= 9:
                match |= Q(badge_number=int(term))
            queryset = queryset.filter(match)
        return queryset

    def get_result_label(self, result):
        return services.member_label(result)


class BigLittleRemoveView(LoginRequiredMixin, View):
    """Delete a current pairing entered by mistake (S2)."""

    http_method_names = ["post"]

    def post(self, request, pk):
        link = get_object_or_404(BigLittle.objects.current().select_related("big", "little", "chapter"), pk=pk)
        if services.can_remove(request.user, link):
            services.remove_link(link)
            messages.success(request, f"Removed {link.big} as {link.little}'s Big.")
        else:
            messages.error(request, f"You cannot remove {link.big} as {link.little}'s Big.")
        return HttpResponseRedirect(_return_url(request))


class MemberProfileRedirectView(LoginRequiredMixin, RedirectView):
    """Profile links for the tree, which must not print every username (an email address)."""

    def get_redirect_url(self, *args, **kwargs):
        member = get_object_or_404(User, pk=kwargs["pk"])
        return reverse("users:profile", kwargs={"username": member.username})


class BigLittleListView(LoginRequiredMixin, PagedFilteredTableView):
    """Every member of the current chapter and their Big; managers get the edit buttons (S3)."""

    model = User
    table_class = BigLittleMemberTable
    filter_class = BigLittleMemberFilter
    formhelper_class = BigLittleListFormHelper
    template_name = "biglittle/big_little_list.html"

    @cached_property
    def can_manage(self):
        return services.can_manage(self.request.user, self.request.user.current_chapter)

    def get_queryset(self, **kwargs):
        rows = services.member_rows(self.request.user.current_chapter)
        return super().get_queryset(other_qs=rows, **kwargs)

    def get_table_kwargs(self):
        return {} if self.can_manage else {"exclude": ("actions",)}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["chapter"] = self.request.user.current_chapter
        context["can_manage"] = self.can_manage
        context["manager_roles_label"] = services.manager_roles_label()
        context["pending_count"] = services.pending_rows(context["chapter"]).count() if self.can_manage else 0
        return context


class BigLittleRecordView(BigLittleManagerRequiredMixin, FormView):
    form_class = RecordBigForm
    template_name = "biglittle/record_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["chapter"] = self.request.user.current_chapter
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        little_pk = self.request.GET.get("little", "")
        if little_pk.isdigit():
            little = services.eligible_members(self.request.user.current_chapter).filter(pk=little_pk).first()
            if little is not None:
                initial["little"] = little.pk
                big = services.current_big(little)
                if big is not None:
                    initial["big"] = big.pk
        return initial

    def form_valid(self, form):
        little, big = form.cleaned_data["little"], form.cleaned_data["big"]
        try:
            result = services.set_big(little, big, actor=self.request.user, source=BigLittle.Source.OFFICER)
        except services.BigLittleError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        _report_saved(self.request, result, little, big)
        return HttpResponseRedirect(reverse("biglittle:list"))


class BigLittleUploadView(BigLittleManagerRequiredMixin, FormView):
    """Record many pairings at once from a CSV of badge numbers or names; results show on the same page."""

    form_class = BigLittleUploadForm
    template_name = "biglittle/upload.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pending_count"] = services.pending_rows(self.request.user.current_chapter).count()
        return context

    def form_valid(self, form):
        result = services.import_big_little_csv(
            form.cleaned_data["file"].read(), self.request.user.current_chapter, self.request.user
        )
        if result.error:
            form.add_error("file", result.error)
            return self.form_invalid(form)
        messages.success(self.request, result.summary)
        if result.count(services.ERROR):
            messages.warning(
                self.request,
                "Rows with problems were not saved. Fix them and upload the file again; "
                "rows already saved will show as no change.",
            )
        return self.render_to_response(self.get_context_data(form=self.form_class(), result=result))


class BigLittleUploadTemplateView(BigLittleManagerRequiredMixin, View):
    """A header-only CSV: badge number columns, or name columns with ``?columns=names``."""

    def get(self, request):
        if request.GET.get("columns") == "names":
            headers, filename = services.NAME_CSV_HEADERS, "big_little_names_template.csv"
        else:
            headers, filename = services.CSV_HEADERS, "big_little_template.csv"
        response = HttpResponse(",".join(headers) + "\r\n", content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class PendingPairingReviewView(BigLittleManagerRequiredMixin, TemplateView):
    """Uploaded rows naming someone who did not match exactly one member (BLWI-12).

    Each row is its own form: pick a suggestion or search for the member, then save the
    pairing, or dismiss the row when nobody can tell who the name means.
    """

    template_name = "biglittle/review.html"

    def get_context_data(self, bound_form=None, **kwargs):
        context = super().get_context_data(**kwargs)
        chapter = self.request.user.current_chapter
        items = list(services.pending_rows(chapter).annotate(uploaded_by_name=F("uploaded_by__name")))
        choices = services.review_choices(items, chapter)
        rows = []
        for item in items:
            if bound_form is not None and bound_form.item.pk == item.pk:
                rows.append((item, bound_form))
            else:
                rows.append((item, PendingPairingForm(item=item, choices=choices, chapter=chapter)))
        context.update({"chapter": chapter, "rows": rows})
        return context

    def post(self, request, *args, **kwargs):
        chapter = request.user.current_chapter
        item = PendingPairing.objects.filter(chapter=chapter, pk=_whole_number(request.POST.get("item"))).first()
        if item is None or item.status != PendingPairing.Status.PENDING:
            messages.info(request, "That row is no longer waiting for review.")
            return HttpResponseRedirect(reverse("biglittle:review"))
        if request.POST.get("action") == "dismiss":
            services.dismiss_pending(item, request.user)
            messages.success(
                request,
                f'Dismissed line {item.line}: Little "{item.little_text or "None"}", Big "{item.big_text or "None"}".',
            )
            return HttpResponseRedirect(reverse("biglittle:review"))
        choices = services.review_choices([item], chapter)
        form = PendingPairingForm(request.POST, item=item, choices=choices, chapter=chapter)
        if form.is_valid():
            little, big = form.cleaned_data["little_member"], form.cleaned_data["big_member"]
            try:
                result = services.save_pending(item, little, big, request.user)
            except services.BigLittleError as error:
                form.add_error(None, error)
            else:
                _report_saved(request, result, little, big)
                return HttpResponseRedirect(reverse("biglittle:review"))
        return self.render_to_response(self.get_context_data(bound_form=form))


def _whole_number(value):
    return int(value) if value and value.isdigit() else None


def _member_url(pk):
    return reverse("biglittle:member", args=[pk])


class FamilyTreeView(LoginRequiredMixin, TemplateView):
    """A chapter's family tree, drawn with Plotly from its current pairings (BLWI-9)."""

    template_name = "biglittle/family_tree.html"
    max_people = 150

    def get(self, request, *args, **kwargs):
        self.chapter = get_object_or_404(Chapter, slug=kwargs["slug"])
        if not services.can_view_tree(request.user, self.chapter):
            messages.error(
                request,
                f"Only members of {self.chapter}, its Regional Directors, National Officers and Admins "
                "can view its family tree.",
            )
            return HttpResponseRedirect(reverse("biglittle:tree", kwargs={"slug": request.user.current_chapter.slug}))
        return super().get(request, *args, **kwargs)

    def _selection(self, forest, families):
        """The people to draw, the picker's value, who to highlight, and a notice."""
        member = _whole_number(self.request.GET.get("member"))
        if member in forest.people:
            root = tree.family_root(forest, member)
            return tree.subforest(forest, root), str(root), member, ""
        notice = ""
        if member is not None:
            notice = "That member has no Big or Little recorded in this chapter's family tree."
        family = self.request.GET.get("family", "")
        root = _whole_number(family)
        if root in forest.roots:
            return tree.subforest(forest, root), str(root), None, notice
        if family != "all" and len(forest.people) > self.max_people:
            root = families[0].root.pk
            notice = (
                f"This tree has {len(forest.people)} people in {len(families)} families, so it opens on the "
                "largest family. Choose another family, or all families, below."
            )
            return tree.subforest(forest, root), str(root), None, notice
        return forest, "all", None, notice

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chapter = self.chapter
        rows = BigLittle.objects.current().filter(chapter=chapter).values(*tree.pair_fields())
        forest = tree.build_forest(
            (tree.person_from_row(row, "big", chapter.pk), tree.person_from_row(row, "little", chapter.pk))
            for row in rows
        )
        families = tree.families(forest)
        shown, selected_family, highlight, notice = self._selection(forest, families)
        figure = None
        if shown.people:
            positions = tree.layout_forest(shown)
            figure = json.loads(tree.build_figure(shown, positions, _member_url, highlight).to_json())
        user = self.request.user
        context.update(
            {
                "chapter": chapter,
                "figure": figure,
                "plotlyjs_url": PLOTLYJS_URL,
                "families": families,
                "selected_family": selected_family,
                "outline": tree.outline(shown),
                "people_count": len(forest.people),
                "notice": notice,
                "missing_big_count": services.members_without_big(chapter).count(),
                "can_manage": services.can_manage(user, chapter),
                "is_current_chapter": user.current_chapter.pk == chapter.pk,
            }
        )
        return context
