"""Pages for the Case Competition (docs/specs/case-competition.md, Pages).

Every permission check is a call into ``services`` or ``judging`` (NECCWI-2). Pages with a
competition run, and render, in its time zone, so form times are read and shown in Eastern
(Gotchas 1). No page changes anything on a GET (Gotchas 9).
"""

import csv
from collections import Counter

from dal import autocomplete
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import SimpleTemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.views.generic import RedirectView, TemplateView, View

from thetatauCMT.chapters.models import Chapter
from thetatauCMT.users.models import User

from . import forms, judging, services, uploads
from .models import Assignment, CriterionScore, Entry, EntryFile, Participant, Round
from .notifications import round_windows

ONLY_MANAGERS = "Only the competition managers can use that page."


def _render_in(zone, view, request, *args, **kwargs):
    """Run a view, and render its page, in ``zone``; template responses otherwise render later."""
    with timezone.override(zone):
        response = view(request, *args, **kwargs)
        if isinstance(response, SimpleTemplateResponse) and not response.is_rendered:
            response.render()
    return response


def _whole_number(value):
    value = (value or "").strip()
    return int(value) if value.isdigit() else None


class CompetitionPageMixin(LoginRequiredMixin):
    """Loads ``self.competition`` (404 unless the viewer may see it) and runs the page in its zone."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.competition = get_object_or_404(services.visible_competitions(request.user), slug=kwargs["slug"])
        self.manager = services.can_manage(request.user)
        refused = self.refuse(request)
        if refused is not None:
            return refused
        return _render_in(self.competition.zone, super().dispatch, request, *args, **kwargs)

    def refuse(self, request):
        """A redirect when the viewer may not use this page; None when they may."""
        return None

    def back_to_competition(self, message, fragment=""):
        messages.info(self.request, message)
        return HttpResponseRedirect(reverse("competitions:detail", args=[self.competition.slug]) + fragment)

    def get_round(self):
        return get_object_or_404(
            Round.objects.select_related("competition").prefetch_related("items", "criteria"),
            competition=self.competition,
            number=self.kwargs["number"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"competition": self.competition, "manager": self.manager})
        return context


class ManagerPageMixin(CompetitionPageMixin):
    def refuse(self, request):
        if not self.manager:
            return self.back_to_competition(ONLY_MANAGERS)
        return None


# --- The competition (NECCWI-4) --------------------------------------------------------------


class CompetitionListView(LoginRequiredMixin, TemplateView):
    template_name = "competitions/list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = []
        for competition in services.visible_competitions(self.request.user).prefetch_related("rounds"):
            winners = []
            for round_ in competition.rounds.all():
                if round_.selection == Round.Selection.PLACES and round_.is_published:
                    winners = [entry for entry in judging.showcase(round_) if entry.place]
            rows.append({"competition": competition, "windows": round_windows(competition), "winners": winners})
        context.update({"rows": rows, "manager": services.can_manage(self.request.user)})
        return context


class CurrentCompetitionView(LoginRequiredMixin, RedirectView):
    """Slug-free addresses for the feature catalog (Gotchas 7): the current competition's pages."""

    target = "detail"

    def get_redirect_url(self, *args, **kwargs):
        user = self.request.user
        competition = services.current_competition(user)
        if competition is None:
            messages.info(self.request, "No Case Competition is published yet.")
            return reverse("competitions:list")
        detail = reverse("competitions:detail", args=[competition.slug])
        if self.target == "submit":
            chapter = services.member_chapter(user)
            for round_ in competition.rounds.all():
                if chapter is not None and services.can_submit(user, round_, chapter):
                    return reverse("competitions:submit", args=[competition.slug, round_.number])
            messages.info(self.request, "No window is open for your chapter right now. Its status is below.")
            return detail + "#your-chapter"
        if self.target == "manage":
            if services.can_view_status(user):
                return reverse("competitions:manage", args=[competition.slug])
            messages.info(self.request, "Only the competition managers and National Officers can see the status page.")
            return detail
        if self.target == "results":
            published = [round_ for round_ in competition.rounds.all() if round_.is_published]
            if published:
                return reverse("competitions:results", args=[competition.slug, published[-1].number])
            messages.info(self.request, "No results are published yet.")
            return detail
        if self.target == "scores":
            if not services.can_manage(user):
                messages.info(self.request, ONLY_MANAGERS)
                return detail
            round_ = self.round_for_scores(competition)
            if round_ is not None:
                return reverse("competitions:scores", args=[competition.slug, round_.number])
        return detail

    @staticmethod
    def round_for_scores(competition):
        """The round being judged, else the latest round that has opened, else the first."""
        now = timezone.now()
        rounds = list(competition.rounds.all())
        judging_now = [
            round_ for round_ in rounds if not round_.is_published and services.judging_started(round_, now=now)
        ]
        started = [round_ for round_ in rounds if round_.opens_at <= now]
        for candidates in (judging_now, started[-1:], rounds[:1]):
            if candidates:
                return candidates[0]
        return None


class CompetitionDetailView(CompetitionPageMixin, TemplateView):
    template_name = "competitions/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        competition, user, now = self.competition, self.request.user, timezone.now()
        judge_rounds = sorted(
            (block for block in judging.judging_rounds(user) if block.judge.round.competition_id == competition.pk),
            key=lambda block: block.judge.round.number,
        )
        rounds = []
        for round_ in competition.rounds.prefetch_related("criteria", "items"):
            state = services.round_state(round_, now)
            criteria = list(round_.criteria.all())
            rounds.append(
                {
                    "round": round_,
                    "state": state,
                    "state_label": services.STATE_LABELS[state],
                    "opens": competition.format_time(round_.opens_at),
                    "closes": competition.format_time(round_.closes_at),
                    "judging_closes": competition.format_time(round_.judging_closes_at),
                    "criteria": criteria,
                    "max_total": sum(criterion.max_points for criterion in criteria),
                    "items": [(item, uploads.describe(item.file_types)) for item in round_.items.all()],
                    "showcase": judging.showcase(round_),
                    "qualifiers_only": round_.eligibility == Round.Eligibility.ADVANCED,
                }
            )
        context.update(
            {
                "rounds": rounds,
                "key_dates": list(competition.key_dates.all()),
                "contact": services.contact_person(competition),
                "contact_email": services.reply_to(competition)[0],
                "intent_opens": competition.format_time(competition.intent_opens_at),
                "intent_closes": competition.format_time(competition.intent_closes_at),
                "intent_open": services.intent_open(competition, now),
                "entry_round": services.entry_round(competition),
                "late_entry_open": services.late_entry_open(competition, now),
                "qualifier_round": competition.rounds.filter(eligibility=Round.Eligibility.ADVANCED).first(),
                "panel": services.chapter_panel(user, competition, now),
                "can_view_status": services.can_view_status(user),
                "is_judge": bool(judge_rounds),
                "my_judging": [
                    {
                        "round": block.judge.round,
                        "to_do": block.to_do,
                        "assigned": len(block.rows),
                        "deadline": block.deadline if block.judge.round.judging_closes_at else "",
                        "closes": competition.format_time(block.judge.round.closes_at),
                        "started": services.judging_started(block.judge.round, now=now),
                    }
                    for block in judge_rounds
                    if not block.judge.round.is_published
                ],
            }
        )
        return context


# --- Taking part (NECCWI-5) ------------------------------------------------------------------


class IntentView(CompetitionPageMixin, TemplateView):
    """Register the chapter, name its contacts, withdraw or rejoin (Q6 B, Q8 A, S31)."""

    template_name = "competitions/intent.html"

    def refuse(self, request):
        self.chapter = services.member_chapter(request.user)
        if self.chapter is None or not self.chapter.active:
            return self.back_to_competition(
                "Only current members and PNMs of a chapter can register it.", fragment="#your-chapter"
            )
        self.participant = services.participant_for(self.competition, self.chapter)
        return None

    def can_change(self):
        if self.participant is None:
            return services.can_register(self.request.user, self.competition, self.chapter)
        return services.can_update_participation(self.request.user, self.participant)

    def get_context_data(self, form=None, **kwargs):
        context = super().get_context_data(**kwargs)
        participant = self.participant
        closes = services.participation_closes_at(self.competition)
        context.update(
            {
                "chapter": self.chapter,
                "participant": participant,
                "registered": participant is not None and participant.withdrawn_at is None,
                "withdrawn": participant is not None and participant.withdrawn_at is not None,
                "can_change": self.can_change(),
                "form": form or forms.ParticipationForm(chapter=self.chapter, participant=participant),
                "intent_opens": self.competition.format_time(self.competition.intent_opens_at),
                "intent_closes": self.competition.format_time(self.competition.intent_closes_at),
                "changes_close": self.competition.format_time(closes),
                "entry_round": services.entry_round(self.competition),
                "late_entry_open": services.late_entry_open(self.competition),
                "registered_on": self.competition.format_time(participant.created) if participant else "None",
                "withdrawn_on": (
                    self.competition.format_time(participant.withdrawn_at)
                    if participant and participant.withdrawn_at
                    else "None"
                ),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        here = reverse("competitions:intent", args=[self.competition.slug])
        name = self.chapter.full_name
        if not self.can_change():
            messages.error(request, "The chapter's registration can no longer be changed here.")
            return HttpResponseRedirect(here)
        if request.POST.get("action") == "withdraw":
            if self.participant is not None and services.withdraw(self.participant, by=request.user):
                messages.success(
                    request,
                    f"Withdrew the {name} from the {self.competition.name}. Its reminders have stopped. "
                    "Any member can rejoin on this page.",
                )
            return HttpResponseRedirect(here)
        form = forms.ParticipationForm(request.POST, chapter=self.chapter, participant=self.participant)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        result = services.register(
            self.competition,
            self.chapter,
            by=request.user,
            source=Participant.Source.INTENT,
            contacts=form.cleaned_data["contacts"],
            team_size_estimate=form.cleaned_data["team_size_estimate"],
            note=form.cleaned_data["note"],
        )
        if result.created:
            messages.success(
                request,
                f"Registered the {name} for the {self.competition.name}. A welcome email is on its way to the "
                "contacts and the chapter's officers.",
            )
        elif result.rejoined:
            messages.success(
                request, f"The {name} has rejoined the {self.competition.name}. Its reminders start again."
            )
        else:
            messages.success(request, f"Saved the {name}'s registration: contacts, team size and note.")
        return HttpResponseRedirect(here)


class ManageView(CompetitionPageMixin, TemplateView):
    """Chapters taking part and each round's status: managers, and National Officers read only (S19)."""

    template_name = "competitions/manage.html"

    def refuse(self, request):
        if not services.can_view_status(request.user):
            return self.back_to_competition(
                "Only the competition managers and National Officers can see the status page."
            )
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        competition = self.competition
        rounds = list(competition.rounds.prefetch_related("items"))
        participants = {
            participant.chapter_id: participant
            for participant in Participant.objects.filter(competition=competition)
            .select_related("chapter__region", "declared_by")
            .prefetch_related("contacts")
        }
        entries = {
            (entry.round_id, entry.chapter_id): entry
            for entry in services.entries_with_files(Entry.objects.filter(round__competition=competition))
        }
        chapter_ids = set(participants) | {chapter_id for _, chapter_id in entries}
        for round_ in rounds:
            chapter_ids |= services.eligible_chapter_ids(round_)
        region = self.request.GET.get("region", "")
        show_withdrawn = self.request.GET.get("withdrawn") == "1"
        chapters = Chapter.objects.filter(pk__in=chapter_ids).select_related("region").order_by("name")
        regions = sorted({chapter.region for chapter in chapters}, key=lambda region: region.name)
        now = timezone.now()
        qualifiers = {
            round_.pk: services.qualifier_chapter_ids(round_)
            for round_ in rounds
            if round_.eligibility == Round.Eligibility.ADVANCED
        }
        previous = {round_.pk: services.previous_round(round_) for round_ in rounds}
        rows, counts = [], {round_.pk: Counter() for round_ in rounds}
        for chapter in chapters:
            participant = participants.get(chapter.pk)
            withdrawn = participant is not None and participant.withdrawn_at is not None
            cells = []
            for round_ in rounds:
                entry = entries.get((round_.pk, chapter.pk))
                status = services.entry_status(entry, round_, now)
                may_enter = services.chapter_may_enter(round_, chapter, qualifiers.get(round_.pk))
                deadline = services.deadline_for(round_, entry)
                earlier = previous[round_.pk]
                earlier_entry = entries.get((earlier.pk, chapter.pk)) if earlier is not None else None
                not_selected = services.not_selected(round_, earlier_entry, may_enter)
                if not withdrawn and (may_enter or entry is not None):
                    counts[round_.pk][status] += 1
                cells.append(
                    {
                        "round": round_,
                        "entry": entry,
                        "status": status,
                        "status_label": services.ENTRY_STATUS_LABELS[status],
                        "started": status in services.STARTED_STATUSES,
                        "may_enter": may_enter,
                        "note": "Not selected" if not_selected else "",
                        "submitted": (
                            competition.format_time(entry.submitted_at) if entry and entry.submitted_at else ""
                        ),
                        "extended": competition.format_time(deadline) if deadline != round_.closes_at else "",
                        "on_behalf": bool(entry and entry.last_saved_on_behalf),
                        "can_act": self.manager and may_enter and not round_.is_published,
                    }
                )
            if region and chapter.region.slug != region:
                continue
            if withdrawn and not show_withdrawn:
                continue
            rows.append({"chapter": chapter, "participant": participant, "withdrawn": withdrawn, "cells": cells})
        context.update(
            {
                "rounds": [(round_, progress_line(counts[round_.pk])) for round_ in rounds],
                "rows": rows,
                "regions": regions,
                "region": region,
                "show_withdrawn": show_withdrawn,
                "is_admin": self.request.user.is_admin,
            }
        )
        return context


def progress_line(counts):
    """Such as "2 submitted, 1 in progress and 3 not started, of 6 taking part."."""
    total = sum(counts.values())
    if not total:
        return "No chapter is taking part yet."
    order = [services.SUBMITTED, services.IN_PROGRESS, services.NOT_STARTED, services.INCOMPLETE]
    parts = [f"{counts[status]} {services.ENTRY_STATUS_LABELS[status].lower()}" for status in order if counts[status]]
    if counts[services.NOT_SUBMITTED]:
        parts.append(f"{counts[services.NOT_SUBMITTED]} not submitted")
    if not counts[services.SUBMITTED]:
        parts.insert(0, "0 submitted")
    listed = parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"
    return f"{listed}, of {total} taking part."


class ExportView(ManagerPageMixin, View):
    """CSV downloads for managers (S26): chapters taking part, entries, and every score."""

    kinds = ("participants", "entries", "scores")

    def get(self, request, slug, kind):
        if kind not in self.kinds:
            raise Http404
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{self.competition.slug}-{kind}.csv"'
        writer = csv.writer(response)
        getattr(self, f"write_{kind}")(writer)
        return response

    def _time(self, value):
        return self.competition.format_time(value) if value else ""

    def write_participants(self, writer):
        writer.writerow(
            [
                "Chapter",
                "Region",
                "Candidate chapter",
                "How it registered",
                "Registered",
                "Registered by",
                "Contacts",
                "Contact emails",
                "Estimated team size",
                "Note",
                "Withdrawn",
            ]
        )
        participants = (
            Participant.objects.filter(competition=self.competition)
            .select_related("chapter__region", "declared_by")
            .prefetch_related("contacts")
            .order_by("chapter__name")
        )
        for participant in participants:
            contacts = list(participant.contacts.order_by("name"))
            writer.writerow(
                [
                    participant.chapter.name,
                    participant.chapter.region.name,
                    "Yes" if participant.chapter.candidate_chapter else "No",
                    participant.get_source_display(),
                    self._time(participant.created),
                    participant.declared_by.name if participant.declared_by else "",
                    "; ".join(person.name for person in contacts),
                    "; ".join(person.email for person in contacts if person.email),
                    participant.team_size_estimate or "",
                    participant.note,
                    self._time(participant.withdrawn_at),
                ]
            )

    def write_entries(self, writer):
        writer.writerow(
            [
                "Round",
                "Chapter",
                "Region",
                "Status",
                "Project title",
                "Summary",
                "First complete",
                "Last saved",
                "Last saved by",
                "Saved on the chapter's behalf",
                "Extended deadline",
                "Eligible",
                "Reason not eligible",
                "Qualified",
                "Place",
                "Team",
                "Files",
            ]
        )
        entries = services.entries_with_files(
            Entry.objects.filter(round__competition=self.competition).order_by("round__number", "chapter__name")
        ).prefetch_related("team__user")
        for entry in entries:
            files = services.current_files(entry)
            writer.writerow(
                [
                    entry.round.name,
                    entry.chapter.name,
                    entry.chapter.region.name,
                    services.ENTRY_STATUS_LABELS[services.entry_status(entry, entry.round)],
                    entry.title,
                    entry.summary,
                    self._time(entry.submitted_at),
                    self._time(entry.last_saved_at),
                    entry.last_saved_by.name if entry.last_saved_by else "",
                    "Yes" if entry.last_saved_on_behalf else "No",
                    self._time(entry.deadline_override),
                    "Yes" if entry.eligible else "No",
                    entry.ineligible_reason,
                    {True: "Yes", False: "No"}.get(entry.advanced, ""),
                    entry.place or "",
                    "; ".join(
                        f"{member.user.name} ({member.team_role})" if member.team_role else member.user.name
                        for member in entry.team.all()
                    ),
                    "; ".join(
                        f"{item.label}: {files[item.pk].original_name or files[item.pk].link}"
                        for item in entry.round.items.all()
                        if item.pk in files
                    ),
                ]
            )

    def write_scores(self, writer):
        writer.writerow(
            [
                "Round",
                "Chapter",
                "Region",
                "Project title",
                "Judge",
                "Judge email",
                "Scorecard",
                "Criterion",
                "Points",
                "Comment",
                "Comment hidden",
                "Total",
                "Feedback",
                "Feedback hidden",
                "Private note",
                "Reason for stepping aside",
            ]
        )
        assignments = (
            Assignment.objects.filter(entry__round__competition=self.competition)
            .select_related("judge__user", "entry__round", "entry__chapter__region", "scorecard")
            .order_by("entry__round__number", "entry__chapter__name", "judge__user__name")
        )
        for assignment in assignments:
            entry, judge = assignment.entry, assignment.judge
            card = judging.scorecard_of(assignment)
            status = judging.SCORECARD_LABELS[judging.assignment_status(assignment)]
            if judge.removed_at is not None:
                status += " (judge removed)"
            base = [entry.round.name, entry.chapter.name, entry.chapter.region.name, entry.title]
            base += [judge.user.name, judge.user.email, status]
            scores = list(card.scores.select_related("criterion")) if card is not None else []
            tail = [
                card.total if card is not None and card.total is not None else "",
                card.feedback if card else "",
                "Yes" if card and card.feedback_hidden else "No",
                card.private_note if card else "",
                assignment.step_aside_reason,
            ]
            if not scores:
                writer.writerow([*base, "", "", "", "", *tail])
            for score in scores:
                points = "" if score.points is None else score.points
                hidden = "Yes" if score.comment_hidden else "No"
                writer.writerow([*base, score.criterion.name, points, score.comment, hidden, *tail])


class MemberAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    """The chapter-scoped member picker for contacts and teams: current members and PNMs (S29).

    Searches the viewer's own chapter; a manager uploading on a chapter's behalf searches that
    chapter (forwarded as ``chapter``).
    """

    def get_queryset(self):
        user = self.request.user
        chapter = None
        slug = self.forwarded.get("chapter")
        if slug:
            candidate = Chapter.objects.filter(slug=slug).first()
            if candidate is not None and (services.can_manage(user) or services.is_chapter_member(user, candidate)):
                chapter = candidate
        if chapter is None:
            chapter = services.member_chapter(user)
        return _search(forms.chapter_members(chapter), self.q)

    def get_result_label(self, result):
        return forms.member_label(result)


class JudgeAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    """Every active account, for managers adding judges (Q16 A; Gotchas 8)."""

    def get_queryset(self):
        if not services.can_manage(self.request.user):
            return User.objects.none()
        people = User.objects.filter(is_active=True).select_related("chapter").order_by("name")
        return _search(people, self.q, emails=True)

    def get_result_label(self, result):
        return f"{result.name} ({result.chapter})"


def _search(queryset, term, emails=False):
    term = (term or "").strip()
    if not term:
        return queryset
    match = Q(name__icontains=term)
    if emails:
        match |= Q(email__icontains=term)
    if term.isdigit() and len(term) <= 9:
        match |= Q(badge_number=int(term))
    return queryset.filter(match)


# --- Submitting (NECCWI-6) -------------------------------------------------------------------


class SubmitView(CompetitionPageMixin, TemplateView):
    """The chapter's entry: any member of the chapter while its window is open (Q26 A), or a
    manager on the chapter's behalf at any time until results are published (S7).
    """

    template_name = "competitions/submit.html"

    def refuse(self, request):
        self.round = self.get_round()
        self.on_behalf = "chapter" in self.kwargs
        if self.on_behalf:
            if not self.manager:
                return self.back_to_competition(ONLY_MANAGERS)
            self.chapter = get_object_or_404(Chapter, slug=self.kwargs["chapter"])
        else:
            self.chapter = services.member_chapter(request.user)
            if self.chapter is None:
                return self.back_to_competition(
                    "Only current members and PNMs of a chapter can change its entry.", fragment="#your-chapter"
                )
        if not services.chapter_may_enter(self.round, self.chapter):
            if self.round.eligibility == Round.Eligibility.ADVANCED:
                message = f"Only the Regional Qualifiers can enter the {self.round.name}."
            else:
                message = f"The {self.chapter.full_name} cannot enter the {self.round.name}."
            return self.back_to_competition(message, fragment="#your-chapter")
        self.entry = services.entry_for(self.round, self.chapter)
        return None

    def editable(self, posting=False):
        if self.on_behalf:
            return services.can_submit_on_behalf(self.request.user, self.round, self.chapter)
        return services.can_submit(self.request.user, self.round, self.chapter, posting=posting)

    def get_context_data(self, form=None, team=None, **kwargs):
        context = super().get_context_data(**kwargs)
        round_, entry = self.round, self.entry
        status = services.entry_status(entry, round_)
        context.update(
            {
                "round": round_,
                "chapter": self.chapter,
                "entry": entry,
                "on_behalf": self.on_behalf,
                "editable": self.editable(),
                "state": services.round_state(round_),
                "opens": self.competition.format_time(round_.opens_at),
                "due": self.competition.format_time(services.deadline_for(round_, entry)),
                "extended": services.deadline_for(round_, entry) != round_.closes_at,
                "status": status,
                "status_label": services.ENTRY_STATUS_LABELS[status],
                "started": status in services.STARTED_STATUSES,
                "past_due": services.past_due(round_, entry),
                "missing": services.missing_items(entry, round_),
                "form": form or forms.EntryForm(round_=round_, entry=entry),
                "team": team or forms.team_formset(entry=entry, chapter=self.chapter),
                "last_saved": self.competition.format_time(entry.last_saved_at) if entry else "None",
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        here = request.path
        if not self.editable(posting=True):
            messages.error(
                request,
                f"The {self.round.name} window is closed, so the changes were not saved. Ask the competition "
                "contact if something went wrong.",
            )
            return HttpResponseRedirect(here)
        form = forms.EntryForm(request.POST, request.FILES, round_=self.round, entry=self.entry)
        team = forms.team_formset(request.POST, entry=self.entry, chapter=self.chapter)
        if not (form.is_valid() and team.is_valid()):
            messages.error(request, "Nothing was saved. Fix the problems below, then choose any files again.")
            return self.render_to_response(self.get_context_data(form=form, team=team))
        result = services.save_entry(
            self.round,
            self.chapter,
            request.user,
            title=form.cleaned_data["title"],
            summary=form.cleaned_data["summary"],
            uploads=form.uploads(),
            links=form.links(),
            on_behalf=self.on_behalf,
        )
        forms.save_team(team, result.entry)
        messages.success(request, self.saved_message(result))
        if self.on_behalf:
            return HttpResponseRedirect(reverse("competitions:manage", args=[self.competition.slug]))
        return HttpResponseRedirect(here)

    def saved_message(self, result):
        name, round_name = self.chapter.full_name, self.round.name
        due = self.competition.format_time(services.deadline_for(self.round, result.entry))
        prefix = f"Saved for the {name}. " if self.on_behalf else "Saved. "
        if result.first_complete:
            return (
                f"{prefix}The {name}'s {round_name} is complete and submitted. A receipt is on its way to you and the "
                f"chapter. It can still be changed until {due}."
            )
        if result.complete:
            return f"{prefix}The {round_name} is still complete, and a new receipt is on its way."
        missing = services.missing_items(result.entry, self.round)
        return f"{prefix}Still needed before it counts as submitted: {', '.join(missing)}."


class EntryDetailView(LoginRequiredMixin, TemplateView):
    """One entry, read only, as the permission matrix allows; its result and feedback once published."""

    template_name = "competitions/entry.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.entry = get_object_or_404(
            Entry.objects.select_related("round__competition", "chapter__region", "last_saved_by", "decided_by"),
            public_id=kwargs["public_id"],
        )
        if not services.can_view_entry(request.user, self.entry):
            raise Http404
        return _render_in(self.entry.round.competition.zone, super().dispatch, request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        entry, user = self.entry, self.request.user
        round_, chapter = entry.round, entry.chapter
        competition = round_.competition
        manager = services.can_manage(user)
        own = services.is_chapter_member(user, chapter) or services.supports(user, chapter)
        files = services.current_files(entry)
        status = services.entry_status(entry, round_)
        my_assignment = judging.assignment_of(user, entry)
        my_status = judging.assignment_status(my_assignment) if my_assignment is not None else None
        context.update(
            {
                "competition": competition,
                "round": round_,
                "chapter": chapter,
                "entry": entry,
                "manager": manager,
                "own": own,
                "my_assignment": my_assignment,
                "my_status": my_status,
                "my_status_label": judging.SCORECARD_LABELS.get(my_status, ""),
                "judging_deadline": (
                    competition.format_time(round_.judging_closes_at) if round_.judging_closes_at else ""
                ),
                "items": [(item, files.get(item.pk)) for item in round_.items.all()],
                "team": list(entry.team.select_related("user__major")),
                "status": status,
                "status_label": services.ENTRY_STATUS_LABELS[status],
                "missing": services.missing_items(entry),
                "due": competition.format_time(services.deadline_for(round_, entry)),
                "submitted": competition.format_time(entry.submitted_at),
                "last_saved": competition.format_time(entry.last_saved_at),
                "can_edit": services.can_submit(user, round_, chapter),
                "result": judging.result_label(entry),
                "feedback": judging.chapter_feedback(entry) if (own or manager) else [],
                "scores": judging.chapter_scores(entry) if (own or manager) else None,
                "replaced": (
                    list(entry.files.filter(replaced_at__isnull=False).select_related("item", "uploaded_by"))
                    if manager
                    else []
                ),
            }
        )
        return context


class EntryFileView(LoginRequiredMixin, View):
    """Checks who is asking, then sends the browser to the stored file or the link (Q11 B)."""

    def get(self, request, public_id):
        entry_file = get_object_or_404(
            EntryFile.objects.select_related("entry__round__competition", "entry__chapter"), public_id=public_id
        )
        if not services.can_view_file(request.user, entry_file):
            raise Http404
        return HttpResponseRedirect(entry_file.link or entry_file.file.url)


class ExtensionView(ManagerPageMixin, TemplateView):
    """Give one chapter its own later deadline for a round (S7)."""

    template_name = "competitions/extension.html"

    def refuse(self, request):
        refused = super().refuse(request)
        if refused is not None:
            return refused
        self.round = self.get_round()
        self.chapter = get_object_or_404(Chapter, slug=self.kwargs["chapter"])
        if not services.chapter_may_enter(self.round, self.chapter):
            messages.info(request, f"The {self.chapter.full_name} cannot enter the {self.round.name}.")
            return HttpResponseRedirect(reverse("competitions:manage", args=[self.competition.slug]))
        self.entry = services.entry_for(self.round, self.chapter)
        return None

    def get_context_data(self, form=None, **kwargs):
        context = super().get_context_data(**kwargs)
        initial = {"until": self.entry.deadline_override} if self.entry and self.entry.deadline_override else {}
        context.update(
            {
                "round": self.round,
                "chapter": self.chapter,
                "form": form or forms.ExtensionForm(initial=initial),
                "closes": self.competition.format_time(self.round.closes_at),
                "due": self.competition.format_time(services.deadline_for(self.round, self.entry)),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        form = forms.ExtensionForm(request.POST)
        if form.is_valid():
            until = form.cleaned_data["until"]
            try:
                services.extend_deadline(self.round, self.chapter, until, by=request.user)
            except services.CompetitionError as error:
                form.add_error("until", str(error))
            else:
                if until is None:
                    messages.success(
                        request,
                        f"Removed the {self.chapter.full_name}'s extension. Its {self.round.name} deadline is the "
                        f"round's, {self.competition.format_time(self.round.closes_at)}.",
                    )
                else:
                    messages.success(
                        request,
                        f"Extended the {self.chapter.full_name}'s {self.round.name} deadline to "
                        f"{self.competition.format_time(until)}.",
                    )
                return HttpResponseRedirect(reverse("competitions:manage", args=[self.competition.slug]))
        return self.render_to_response(self.get_context_data(form=form))


# --- Results (NECCWI-12, 13) -----------------------------------------------------------------


class ResultsView(CompetitionPageMixin, TemplateView):
    """The Regional Qualifiers by region, or the winners and finalists, for every member (Q22 A)."""

    template_name = "competitions/results.html"

    def refuse(self, request):
        self.round = self.get_round()
        if not self.round.is_published:
            return self.back_to_competition(f"The {self.round.name} results are not published yet.")
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        entries = judging.showcase(self.round)
        groups = {}
        for entry in entries:
            groups.setdefault(entry.chapter.region, []).append(entry)
        own = None
        chapter = services.panel_chapter(self.request.user)
        user = self.request.user
        if chapter is not None and (services.is_chapter_member(user, chapter) or services.supports(user, chapter)):
            own = services.entry_for(self.round, chapter)
        context.update(
            {
                "round": self.round,
                "advance": self.round.selection == Round.Selection.ADVANCE,
                "entries": entries,
                "regions": sorted(groups.items(), key=lambda pair: pair[0].name),
                "published": self.competition.format_time(self.round.results_published_at),
                "own_entry": own if own is not None and own.submitted_at else None,
                "own_result": judging.result_label(own) if own is not None else None,
            }
        )
        return context


# --- Judging (NECCWI-9, 10) ------------------------------------------------------------------


class MyJudgingView(LoginRequiredMixin, TemplateView):
    template_name = "competitions/judging.html"

    def get(self, request, *args, **kwargs):
        self.rounds = judging.judging_rounds(request.user)
        if not self.rounds:
            messages.info(request, "You are not judging any round of the Case Competition.")
            return HttpResponseRedirect(reverse("competitions:current"))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["rounds"] = self.rounds
        return context


class ScorecardView(LoginRequiredMixin, TemplateView):
    """One judge's scorecard for one entry: the judge scores; a manager reads it and hides comments (S18)."""

    template_name = "competitions/scorecard.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.assignment = get_object_or_404(
            Assignment.objects.select_related(
                "judge__user", "judge__round__competition", "entry__chapter__region", "entry__round"
            ),
            public_id=kwargs["public_id"],
        )
        if not judging.can_open_scorecard(request.user, self.assignment):
            raise Http404
        self.round = self.assignment.judge.round
        self.competition = self.round.competition
        self.is_judge = self.assignment.judge.user_id == request.user.pk
        self.manager = services.can_manage(request.user)
        return _render_in(self.competition.zone, super().dispatch, request, *args, **kwargs)

    def get_context_data(self, form=None, step_aside_form=None, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment, entry = self.assignment, self.assignment.entry
        card = judging.scorecard_of(assignment)
        editable = self.is_judge and judging.can_score(self.request.user, assignment)
        files = services.current_files(entry)
        scores = {score.criterion_id: score for score in card.scores.all()} if card is not None else {}
        context.update(
            {
                "competition": self.competition,
                "round": self.round,
                "assignment": assignment,
                "entry": entry,
                "card": card,
                "status": judging.assignment_status(assignment),
                "status_label": judging.SCORECARD_LABELS[judging.assignment_status(assignment)],
                "editable": editable,
                "is_judge": self.is_judge,
                "manager": self.manager,
                "items": [(item, files.get(item.pk)) for item in self.round.items.all()],
                "team": list(entry.team.select_related("user__major")),
                "criteria": [(criterion, scores.get(criterion.pk)) for criterion in self.round.criteria.all()],
                "deadline": self.competition.format_time(self.round.judging_closes_at),
                "form": form or forms.ScorecardForm(round_=self.round, scorecard=card),
                "step_aside_form": step_aside_form or forms.StepAsideForm(),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action", "")
        here = request.path
        if action in ("hide_feedback", "show_feedback", "hide_comment", "show_comment"):
            return self.manager_action(request, action, here)
        if action == "undo_step_aside":
            judge = self.assignment.judge
            if self.is_judge and judge.removed_at is None and not self.round.is_published:
                judging.undo_step_aside(self.assignment)
                messages.success(request, "You can score this entry again.")
            return HttpResponseRedirect(here)
        if not (self.is_judge and judging.can_score(request.user, self.assignment)):
            messages.error(request, "This scorecard can no longer be changed.")
            return HttpResponseRedirect(here)
        if action == "step_aside":
            step_form = forms.StepAsideForm(request.POST)
            if step_form.is_valid():
                judging.step_aside(self.assignment, step_form.cleaned_data["reason"])
                messages.success(
                    request, f"You stepped aside from the {self.assignment.entry.chapter.full_name}'s entry."
                )
                return HttpResponseRedirect(reverse("competitions:judging"))
            return self.render_to_response(self.get_context_data(step_aside_form=step_form))
        form = forms.ScorecardForm(request.POST, round_=self.round, scorecard=judging.scorecard_of(self.assignment))
        if form.is_valid():
            submit = action == "submit"
            try:
                card = judging.save_scorecard(
                    self.assignment,
                    form.scores(),
                    form.cleaned_data["feedback"],
                    form.cleaned_data["private_note"],
                    submit=submit,
                )
            except services.CompetitionError as error:
                form.add_error(None, str(error))
            else:
                chapter = self.assignment.entry.chapter.full_name
                if card.submitted_at is not None:
                    messages.success(request, f"Submitted your scorecard for the {chapter}: {card.total} points.")
                    return HttpResponseRedirect(reverse("competitions:judging"))
                messages.success(request, f"Saved a draft of your scorecard for the {chapter}.")
                return HttpResponseRedirect(here)
        return self.render_to_response(self.get_context_data(form=form))

    def manager_action(self, request, action, here):
        if not self.manager:
            raise Http404
        hidden = action.startswith("hide")
        if action.endswith("feedback"):
            card = judging.scorecard_of(self.assignment)
            if card is not None:
                judging.set_hidden(card, hidden)
                messages.success(
                    request,
                    "The feedback is hidden from the chapter." if hidden else "The feedback is shown to the chapter.",
                )
        else:
            score = CriterionScore.objects.filter(
                scorecard__assignment=self.assignment, pk=_whole_number(request.POST.get("score"))
            ).first()
            if score is not None:
                judging.set_hidden(score, hidden)
                messages.success(
                    request,
                    f"The comment on {score.criterion.name} is "
                    f"{'hidden from' if hidden else 'shown to'} the chapter.",
                )
        return HttpResponseRedirect(here)


class JudgesView(ManagerPageMixin, TemplateView):
    """Add and remove a round's judges and follow their progress (NECCWI-9)."""

    template_name = "competitions/judges.html"

    def refuse(self, request):
        refused = super().refuse(request)
        if refused is None:
            self.round = self.get_round()
        return refused

    def get_context_data(self, form=None, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = list(judging.judge_rows(self.round))
        for row in rows:
            row.to_do = row.assigned - row.stepped_aside - row.submitted
        context.update(
            {
                "round": self.round,
                "rows": rows,
                "form": form or forms.AddJudgeForm(),
                "started": services.judging_started(self.round),
                "opens": self.competition.format_time(self.round.closes_at + services.grace(self.round)),
                "deadline": self.competition.format_time(self.round.judging_closes_at),
                "ready": len(judging.entries_for_judging(self.round)),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        here = request.path
        action = request.POST.get("action", "")
        if self.round.is_published:
            messages.error(request, "The results are published, so the judges can no longer change.")
            return HttpResponseRedirect(here)
        if action == "remove":
            judge = self.round.judges.filter(pk=_whole_number(request.POST.get("judge"))).select_related("user").first()
            if judge is not None and judging.remove_judge(judge):
                messages.success(request, f"Removed {judge.user} as a judge. Their scorecards no longer count.")
            return HttpResponseRedirect(here)
        if action == "refresh":
            added = judging.sync_assignments(self.round)
            messages.success(request, f"Added {added} assignment{'s' if added != 1 else ''}.")
            return HttpResponseRedirect(here)
        form = forms.AddJudgeForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        judge, added = judging.add_judge(self.round, form.cleaned_data["user"], by=request.user)
        if added:
            messages.success(request, f"Added {judge.user} as a judge of the {self.round.name}.")
        else:
            messages.info(request, f"{judge.user} is already a judge of the {self.round.name}.")
        return HttpResponseRedirect(here)


class ScoresView(ManagerPageMixin, TemplateView):
    """Scores ranked within each region, the selection and publishing (NECCWI-11 to 13)."""

    template_name = "competitions/scores.html"

    def refuse(self, request):
        refused = super().refuse(request)
        if refused is None:
            self.round = self.get_round()
        return refused

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        round_ = self.round
        criteria, rows = judging.score_rows(round_)
        advance = round_.selection == Round.Selection.ADVANCE
        preselected = judging.preselect(round_, rows) if advance else judging.Preselection()
        context.update(
            {
                "round": round_,
                "advance": advance,
                "criteria": criteria,
                "regions": judging.rows_by_region(rows),
                "count": len(rows),
                "preselection": preselected,
                "warnings": [] if round_.is_published else judging.selection_warnings(round_, rows),
                "blockers": judging.publish_blockers(round_, rows),
                "places": range(1, (round_.places or 0) + 1),
                "published": self.competition.format_time(round_.results_published_at),
                "judging_started": services.judging_started(round_),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        here = request.path
        action = request.POST.get("action", "")
        entry = None
        if action in ("decide", "place", "ineligible", "eligible"):
            entry = (
                Entry.objects.filter(round=self.round, pk=_whole_number(request.POST.get("entry")))
                .select_related("chapter", "round__competition")
                .first()
            )
            if entry is None:
                messages.error(request, "That entry is not in this round.")
                return HttpResponseRedirect(here)
        try:
            message = self.act(request, action, entry)
        except services.CompetitionError as error:
            messages.error(request, str(error))
        else:
            if message:
                messages.success(request, message)
        return HttpResponseRedirect(here + (f"#entry-{entry.pk}" if entry is not None else ""))

    def act(self, request, action, entry):
        user, round_ = request.user, self.round
        if action == "preselect":
            result = judging.apply_preselection(round_, user)
            notes = " ".join(result.warnings)
            chosen = judging._plural(len(result.selected), "entry", "entries")
            return f"Pre-selected {chosen}. Check them before publishing. {notes}".strip()
        if action == "decide":
            value = {"yes": True, "no": False}.get(request.POST.get("advanced"))
            judging.set_decision(entry, value, user)
            label = {True: "qualifies", False: "does not qualify", None: "has no decision"}[value]
            return f"The {entry.chapter.full_name} {label}."
        if action == "place":
            place = _whole_number(request.POST.get("place"))
            judging.set_place(entry, place, user)
            return f"The {entry.chapter.full_name} is {judging.ordinal(place) + ' place' if place else 'not placed'}."
        if action == "ineligible":
            judging.set_eligibility(entry, False, request.POST.get("reason"), user)
            return f"Marked the {entry.chapter.full_name}'s entry ineligible. The chapter sees the reason."
        if action == "eligible":
            judging.set_eligibility(entry, True, "", user)
            return f"The {entry.chapter.full_name}'s entry is eligible again."
        if action == "publish":
            if request.POST.get("confirm") != "yes":
                raise services.CompetitionError("Tick the box to confirm, then publish.")
            if not judging.publish_results(round_, user):
                return "The results were already published."
            if round_.selection == Round.Selection.PLACES:
                return "Announced the winners. Every finalist chapter is being emailed."
            return "Published the results. Every chapter with an entry is being emailed."
        raise services.CompetitionError("Nothing was changed.")
