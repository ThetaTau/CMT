import datetime

import pytest
from django.contrib import admin
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.tests.factories import UserFactory

from ..admin import RubricCriterionInline
from ..models import Assignment, Competition, Entry, Judge, NotificationLog, Participant, Round, Scorecard
from .factories import CompetitionFactory, CriterionScoreFactory, EntryFileFactory, ParticipantFactory, RoundFactory

UTC = datetime.timezone.utc
# Superusers get past the two-factor middleware only when DEBUG is on.
pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("superuser_debug")]


@pytest.fixture
def superuser_debug():
    with override_settings(DEBUG=True):
        yield


@pytest.fixture
def admin_client_for(auto_login_user, admin_user):
    client, _ = auto_login_user(user=admin_user)
    return client


def management_form(prefix, total=0, initial=0):
    return {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": str(initial),
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }


def form_errors(response):
    context = response.context or {}
    errors = [context["adminform"].form.errors] if "adminform" in context else []
    errors += [formset.formset.errors for formset in context.get("inline_admin_formsets", [])]
    return errors


def test_round_times_are_entered_and_shown_in_eastern(admin_client_for):
    proposal = RoundFactory()
    url = reverse("admin:competitions_round_change", args=[proposal.pk])

    page = admin_client_for.get(url).content.decode()
    assert 'value="23:59:59"' in page
    assert "21:59:59" not in page  # the site's own (Arizona) time
    assert "Every date and time on this page is Eastern time" in page

    data = {
        "competition": proposal.competition_id,
        "number": "1",
        "name": "Proposal",
        "selection": "advance",
        "eligibility": "participants",
        "instructions": "",
        "opens_at_0": "2026-12-04",
        "opens_at_1": "00:00:00",
        "closes_at_0": "2026-12-11",
        "closes_at_1": "23:30:00",
        "grace_minutes": "10",
        "judging_closes_at_0": "2027-01-08",
        "judging_closes_at_1": "23:59:59",
        "score_min": "1",
        "advance_per_region": "2",
        "advance_total": "20",
        "reminder_days_before_open": "7",
        "reminder_days_before_close": "3, 1, 0",
        "judge_reminder_days": "7,3,1",
        "share_feedback": "on",
        **management_form("criteria"),
        **management_form("items"),
    }
    response = admin_client_for.post(url, data)

    assert response.status_code == 302, form_errors(response)
    proposal.refresh_from_db()
    assert proposal.closes_at == datetime.datetime(2026, 12, 12, 4, 30, tzinfo=UTC)
    assert proposal.reminder_days_before_close == "3, 1, 0"


def test_chapters_added_on_the_competition_page_record_who_added_them(admin_client_for, admin_user):
    competition = CompetitionFactory()
    chapter = ChapterFactory(name="alpha")
    contact = UserFactory(chapter=chapter, status="active")
    data = {
        "name": competition.name,
        "short_name": competition.short_name,
        "year_label": competition.year_label,
        "slug": competition.slug,
        "is_published": "on",
        "case_title": competition.case_title,
        "case_description": "",
        "about": "",
        "resources": "",
        "contact_role": "Professional Development Director",
        "contact_email": "",
        "time_zone": "America/New_York",
        "intent_opens_at_0": "2026-09-11",
        "intent_opens_at_1": "00:00:00",
        "intent_closes_at_0": "2026-09-28",
        "intent_closes_at_1": "23:59:59",
        **management_form("key_dates"),
        **management_form("rounds"),
        **management_form("participants", total=1),
        "participants-0-competition": competition.pk,
        "participants-0-chapter": chapter.pk,
        "participants-0-contacts": [contact.pk],
        "participants-0-team_size_estimate": "6",
    }

    response = admin_client_for.post(reverse("admin:competitions_competition_change", args=[competition.pk]), data)

    assert response.status_code == 302, form_errors(response)
    participant = Participant.objects.get(competition=competition)
    assert (participant.chapter, participant.source, participant.declared_by) == (chapter, "admin", admin_user)
    assert list(participant.contacts.all()) == [contact]
    competition.refresh_from_db()
    assert competition.contact_role == "professional development director"
    assert competition.intent_closes_at == datetime.datetime(2026, 9, 29, 3, 59, 59, tzinfo=UTC)


def test_a_closed_chapter_cannot_be_added(admin_client_for):
    competition = CompetitionFactory()
    closed = ChapterFactory(name="delta", active=False)
    data = {
        "competition": competition.pk,
        "chapter": closed.pk,
        "source": "admin",
    }

    response = admin_client_for.post(reverse("admin:competitions_participant_add"), data)

    assert response.status_code == 200
    assert "Only active chapters can take part." in response.content.decode()
    assert not Participant.objects.exists()


def test_the_copy_action_makes_an_unpublished_copy(admin_client_for):
    competition = CompetitionFactory(year_label="2026-2027", slug="necc-2026-2027")

    response = admin_client_for.post(
        reverse("admin:competitions_competition_changelist"),
        {"action": "copy_to_next_year", "_selected_action": [competition.pk]},
        follow=True,
    )

    assert Competition.objects.get(slug="necc-2027-2028").is_published is False
    assert "Copied National Engineering Case Competition 2026-2027" in response.content.decode()


def test_a_locked_rubric_is_read_only(rf, admin_user):
    request = rf.get("/")
    request.user = admin_user
    inline = RubricCriterionInline(Round, admin.site)
    locked = RoundFactory(rubric_locked_at=timezone.now())
    unlocked = RoundFactory(competition=locked.competition, number=2, name="Final submission")

    assert not inline.has_add_permission(request, locked)
    assert not inline.has_change_permission(request, locked)
    assert not inline.has_delete_permission(request, locked)
    assert inline.has_change_permission(request, unlocked)


@pytest.mark.parametrize(
    "model", [Competition, Round, Participant, Entry, Judge, Assignment, Scorecard, NotificationLog]
)
def test_every_list_and_record_page_opens(admin_client_for, model):
    score = CriterionScoreFactory()
    entry = score.scorecard.assignment.entry
    EntryFileFactory(entry=entry)
    ParticipantFactory(competition=entry.round.competition, chapter=entry.chapter)
    NotificationLog.objects.create(
        key="welcome:1", kind=NotificationLog.Kind.WELCOME, competition=entry.round.competition, chapter=entry.chapter
    )
    name = f"admin:competitions_{model._meta.model_name}"

    assert admin_client_for.get(reverse(f"{name}_changelist")).status_code == 200
    assert admin_client_for.get(reverse(f"{name}_change", args=[model.objects.first().pk])).status_code == 200
