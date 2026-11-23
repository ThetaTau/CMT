"""NECCWI-2: the rules in ``services.py``, checked against the permission matrix."""

import datetime

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.support.tests.factories import ChapterSupportAssignmentFactory, make_css

from .. import services
from ..models import Participant, Round
from .factories import (
    AssignmentFactory,
    CompetitionFactory,
    EntryFactory,
    EntryFileFactory,
    JudgeFactory,
    ParticipantFactory,
    RoundFactory,
    SubmissionItemFactory,
    eastern,
    give_role,
    member,
    national_officer,
    set_config,
)

pytestmark = pytest.mark.django_db

DURING = eastern(2026, 12, 8, 12)
BEFORE = eastern(2026, 12, 3, 12)
LAST_SECOND = eastern(2026, 12, 11, 23, 59, 58)
IN_GRACE = eastern(2026, 12, 12, 0, 5)
AFTER_GRACE = eastern(2026, 12, 12, 0, 10)


@pytest.fixture
def chapter():
    return ChapterFactory(name="alpha")


@pytest.fixture
def other_chapter():
    return ChapterFactory(name="beta")


@pytest.fixture
def round_():
    round_ = RoundFactory()
    SubmissionItemFactory(round=round_, label="Proposal")
    return round_


def complete_entry(round_, chapter, **kwargs):
    entry = EntryFactory(round=round_, chapter=chapter, summary="What we will build", **kwargs)
    for item in round_.items.all():
        EntryFileFactory(entry=entry, item=item)
    return entry


class TestManagers:
    def test_blank_setting_means_the_professional_development_director(self):
        director = give_role(member(ChapterFactory(name="alpha"), status="alumni"), "professional development director")
        assert services.can_manage(director)
        assert not services.can_manage(member(ChapterFactory(name="beta")))

    @pytest.mark.parametrize("how", ["username", "email", "role"])
    def test_named_by_username_email_or_role(self, how):
        person = member(ChapterFactory(name="alpha"), status="alumni")
        if how == "role":
            give_role(person, "grand regent")
            value = "Grand Regent"
        else:
            value = getattr(person, how).upper()
        set_config(services.MANAGERS_CONFIG_KEY, f"<p>someone-else@example.com</p><p>{value}</p>")
        assert services.can_manage(person)

    def test_view_as_member_switches_it_off(self):
        from thetatauCMT.users.models import UserAlter

        director = give_role(member(ChapterFactory(name="alpha"), status="alumni"), "professional development director")
        assert director.in_national_officer_group
        UserAlter.objects.update_or_create(user=director, defaults={"chapter": director.chapter, "hide_natoff": True})
        director.refresh_from_db()
        assert not services.can_manage(director)
        assert not services.can_view_status(director)

    def test_admins_manage(self, admin_user):
        assert services.can_manage(admin_user)

    def test_national_officers_see_the_status_page_only(self):
        officer = national_officer()
        assert services.can_view_status(officer)
        assert not services.can_manage(officer)


class TestMembership:
    @pytest.mark.parametrize("status", ["active", "activepend", "alumnipend", "pendexpul", "activeCC", "pnm"])
    def test_current_members_and_pnms_belong(self, chapter, status):
        assert services.is_chapter_member(member(chapter, status=status), chapter)

    @pytest.mark.parametrize("status", ["alumni", "away", "resigned", "nonmember", "advisor"])
    def test_other_statuses_do_not(self, chapter, status):
        assert not services.is_chapter_member(member(chapter, status=status), chapter)

    def test_the_region_bar_does_not_make_a_member(self, chapter, other_chapter):
        from thetatauCMT.users.models import UserAlter

        officer = national_officer(chapter=other_chapter)
        UserAlter.objects.update_or_create(user=officer, defaults={"chapter": chapter})
        officer.refresh_from_db()
        assert officer.current_chapter == chapter
        assert not services.is_chapter_member(officer, chapter)
        assert services.panel_chapter(officer) == other_chapter


class TestRegistering:
    @pytest.fixture
    def competition(self):
        return CompetitionFactory(intent_opens_at=eastern(2026, 9, 11), intent_closes_at=eastern(2026, 9, 28, 23, 59))

    def test_any_member_or_pnm_while_the_intent_window_is_open(self, competition, chapter):
        now = eastern(2026, 9, 20)
        assert services.can_register(member(chapter), competition, chapter, now)
        assert services.can_register(member(chapter, status="pnm"), competition, chapter, now)
        assert not services.can_register(member(chapter, status="alumni"), competition, chapter, now)

    def test_not_outside_the_window_or_for_another_chapter(self, competition, chapter, other_chapter):
        person = member(chapter)
        assert not services.can_register(person, competition, chapter, eastern(2026, 9, 10))
        assert not services.can_register(person, competition, chapter, eastern(2026, 9, 29))
        assert not services.can_register(person, competition, other_chapter, eastern(2026, 9, 20))

    def test_not_before_publishing_or_without_both_dates(self, chapter):
        person, now = member(chapter), eastern(2026, 9, 20)
        hidden = CompetitionFactory(
            is_published=False, intent_opens_at=eastern(2026, 9, 1), intent_closes_at=eastern(2026, 9, 30)
        )
        assert not services.can_register(person, hidden, chapter, now)
        assert not services.can_register(person, CompetitionFactory(intent_opens_at=eastern(2026, 9, 1)), chapter, now)

    def test_contacts_change_until_the_last_round_closes(self, competition, chapter):
        RoundFactory(competition=competition)
        participant = ParticipantFactory(competition=competition, chapter=chapter)
        person = member(chapter)
        assert services.can_update_participation(person, participant, eastern(2026, 10, 15))
        assert services.can_update_participation(person, participant, LAST_SECOND)
        assert not services.can_update_participation(person, participant, AFTER_GRACE)
        assert not services.can_update_participation(member(chapter, status="alumni"), participant, DURING)

    def test_registering_twice_updates_rather_than_duplicates(
        self, competition, chapter, django_capture_on_commit_callbacks
    ):
        person, contact = member(chapter), member(chapter)
        with django_capture_on_commit_callbacks() as callbacks:
            first = services.register(competition, chapter, by=person, contacts=[contact], team_size_estimate=4)
        assert first.created and len(callbacks) == 1
        with django_capture_on_commit_callbacks() as callbacks:
            again = services.register(competition, chapter, by=person, team_size_estimate=6, note="Six of us")
        assert not again.created and not callbacks
        participant = Participant.objects.get()
        assert (participant.team_size_estimate, participant.note) == (6, "Six of us")
        assert list(participant.contacts.all()) == [contact]

    def test_withdrawing_and_rejoining(self, competition, chapter):
        participant = ParticipantFactory(competition=competition, chapter=chapter)
        assert services.withdraw(participant, by=member(chapter))
        assert not services.withdraw(participant)
        rejoined = services.register(competition, chapter)
        assert rejoined.rejoined
        participant.refresh_from_db()
        assert participant.withdrawn_at is None

    def test_admin_additions_get_no_welcome(self, competition, chapter, django_capture_on_commit_callbacks):
        with django_capture_on_commit_callbacks() as callbacks:
            services.register(competition, chapter, source=Participant.Source.ADMIN)
        assert not callbacks


class TestWindows:
    def test_states_follow_the_dates(self, round_):
        assert services.round_state(round_, BEFORE) == services.UPCOMING
        assert services.round_state(round_, eastern(2026, 12, 4)) == services.OPEN
        assert services.round_state(round_, LAST_SECOND) == services.OPEN
        assert services.round_state(round_, eastern(2026, 12, 12)) == services.JUDGING
        round_.results_published_at = AFTER_GRACE
        assert services.round_state(round_, AFTER_GRACE) == services.PUBLISHED

    def test_eastern_edges_and_the_grace_minutes(self, round_):
        assert round_.closes_at == datetime.datetime(2026, 12, 12, 4, 59, 59, tzinfo=datetime.timezone.utc)
        assert services.window_open(round_, now=LAST_SECOND)
        assert not services.window_open(round_, now=IN_GRACE)
        assert services.accepts_upload(round_, now=IN_GRACE)
        assert not services.accepts_upload(round_, now=AFTER_GRACE)
        assert not services.accepts_upload(round_, now=eastern(2026, 12, 3, 23, 59))

    def test_no_grace_when_turned_off(self, round_):
        round_.grace_minutes = 0
        assert not services.accepts_upload(round_, now=IN_GRACE)

    def test_an_extension_moves_one_chapters_deadline(self, round_, chapter):
        entry = EntryFactory(round=round_, chapter=chapter, deadline_override=eastern(2026, 12, 14, 23, 59))
        assert services.window_open(round_, entry, eastern(2026, 12, 13))
        assert not services.window_open(round_, None, eastern(2026, 12, 13))
        assert not services.judging_started(round_, entry, eastern(2026, 12, 13))
        assert services.judging_started(round_, None, eastern(2026, 12, 13))

    def test_an_extension_must_end_after_the_close(self, round_, chapter):
        with pytest.raises(services.CompetitionError):
            services.extend_deadline(round_, chapter, eastern(2026, 12, 10))
        entry = services.extend_deadline(round_, chapter, eastern(2026, 12, 13, 12))
        assert services.deadline_for(round_, entry) == eastern(2026, 12, 13, 12)
        assert services.extend_deadline(round_, chapter, None).deadline_override is None


class TestSubmitting:
    def test_any_member_while_the_window_is_open(self, round_, chapter):
        assert services.can_submit(member(chapter), round_, chapter, DURING)
        assert services.can_submit(member(chapter, status="pnm"), round_, chapter, DURING)
        assert not services.can_submit(member(chapter, status="alumni"), round_, chapter, DURING)
        assert not services.can_submit(member(chapter), round_, chapter, BEFORE)

    def test_the_grace_minutes_are_for_saves_under_way(self, round_, chapter):
        person = member(chapter)
        assert not services.can_submit(person, round_, chapter, IN_GRACE)
        assert services.can_submit(person, round_, chapter, IN_GRACE, posting=True)
        assert not services.can_submit(person, round_, chapter, AFTER_GRACE, posting=True)

    def test_never_for_another_chapter(self, round_, chapter, other_chapter):
        assert not services.can_submit(member(other_chapter), round_, chapter, DURING)

    def test_an_unregistered_chapter_registers_with_its_first_save(
        self, round_, chapter, django_capture_on_commit_callbacks
    ):
        person = member(chapter)
        with django_capture_on_commit_callbacks() as callbacks:
            result = services.save_entry(round_, chapter, person, title="Solar", summary="", now=DURING)
        assert result.registered and not result.complete
        participant = Participant.objects.get(competition=round_.competition, chapter=chapter)
        assert participant.source == Participant.Source.SUBMISSION
        assert len(callbacks) == 1  # the welcome email; no receipt for an incomplete entry

    def test_complete_saves_set_submitted_once_and_send_receipts(
        self, round_, chapter, django_capture_on_commit_callbacks, settings, tmp_path
    ):
        settings.MEDIA_ROOT = tmp_path
        person, item = member(chapter), round_.items.get()
        upload = SimpleUploadedFile("deck.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        with django_capture_on_commit_callbacks() as callbacks:
            first = services.save_entry(
                round_, chapter, person, title="Solar", summary="Panels", uploads={item: upload}, now=DURING
            )
        assert first.first_complete and first.entry.submitted_at == DURING
        assert len(callbacks) == 2  # welcome and receipt
        with django_capture_on_commit_callbacks() as callbacks:
            again = services.save_entry(round_, chapter, person, title="Solar 2", summary="Panels", now=LAST_SECOND)
        assert again.complete and not again.first_complete
        assert again.entry.submitted_at == DURING
        assert len(callbacks) == 1

    def test_replacing_a_file_keeps_the_old_one(self, round_, chapter, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        person, item = member(chapter), round_.items.get()
        for name in ("one.pdf", "two.pdf"):
            upload = SimpleUploadedFile(name, b"%PDF-1.4", content_type="application/pdf")
            services.save_entry(round_, chapter, person, title="T", summary="S", uploads={item: upload}, now=DURING)
        entry = services.entry_for(round_, chapter)
        assert entry.files.count() == 2
        assert services.current_files(entry)[item.pk].original_name == "two.pdf"

    def test_a_qualifiers_only_round(self, round_, chapter, other_chapter):
        final = RoundFactory(
            competition=round_.competition,
            number=2,
            name="Final submission",
            eligibility=Round.Eligibility.ADVANCED,
            selection=Round.Selection.PLACES,
            places=2,
            opens_at=eastern(2027, 5, 21),
            closes_at=eastern(2027, 5, 28, 23, 59, 59),
            judging_closes_at=eastern(2027, 6, 25, 23, 59, 59),
        )
        complete_entry(round_, chapter, advanced=True)
        complete_entry(round_, other_chapter, advanced=False, submitted_at=DURING)
        during_final = eastern(2027, 5, 25)
        assert not services.can_submit(member(chapter), final, chapter, during_final)  # not published yet
        round_.results_published_at = eastern(2027, 1, 20)
        round_.save()
        assert services.can_submit(member(chapter), final, chapter, during_final)
        assert not services.can_submit(member(other_chapter), final, other_chapter, during_final)
        assert services.eligible_chapter_ids(final) == {chapter.pk}
        with pytest.raises(services.CompetitionError):
            services.extend_deadline(final, other_chapter, eastern(2027, 6, 1))
        assert not final.entries.exists()
        assert services.not_selected(final, round_.entries.get(chapter=other_chapter), may_enter=False)

    def test_managers_upload_on_behalf_after_the_close(self, round_, chapter, admin_user):
        assert services.can_submit_on_behalf(admin_user, round_, chapter)
        assert not services.can_submit_on_behalf(member(chapter), round_, chapter)


class TestCompleteness:
    def test_title_summary_and_every_required_item(self, round_, chapter):
        optional = SubmissionItemFactory(round=round_, label="Video", kind="link", file_types=[], required=False)
        entry = EntryFactory(round=round_, chapter=chapter, title="", summary="")
        assert services.missing_items(entry) == ["Project title", "Summary", "Proposal"]
        assert services.entry_status(entry, now=DURING) == services.NOT_STARTED
        entry.title = "Solar"
        assert services.entry_status(entry, now=DURING) == services.IN_PROGRESS
        entry.summary = "Panels"
        EntryFileFactory(entry=entry, item=round_.items.get(label="Proposal"))
        assert services.missing_items(entry) == []
        assert services.entry_status(entry, now=DURING) == services.SUBMITTED
        assert optional.pk not in services.current_files(entry)

    def test_unfinished_entries_are_incomplete_once_the_deadline_passes(self, round_, chapter, other_chapter):
        started = EntryFactory(round=round_, chapter=chapter, title="Solar", summary="")
        assert services.entry_status(started, now=LAST_SECOND) == services.IN_PROGRESS
        assert services.entry_status(started, now=AFTER_GRACE) == services.INCOMPLETE
        assert services.entry_status(None, round_, now=AFTER_GRACE) == services.NOT_SUBMITTED
        assert services.entry_status(complete_entry(round_, other_chapter), now=AFTER_GRACE) == services.SUBMITTED
        started.deadline_override = eastern(2026, 12, 15)
        assert services.entry_status(started, now=AFTER_GRACE) == services.IN_PROGRESS
        assert services.entry_status(started, now=eastern(2026, 12, 15)) == services.INCOMPLETE


class TestVisibility:
    @pytest.fixture
    def entry(self, round_, chapter):
        return complete_entry(round_, chapter)

    def test_members_of_the_chapter_and_its_css(self, entry, chapter):
        from thetatauCMT.support.services import clear_css_state

        assert services.can_view_entry(member(chapter), entry, DURING)
        assert services.can_view_entry(member(chapter, status="pnm"), entry, DURING)
        css = make_css()
        ChapterSupportAssignmentFactory(user=css, chapter=chapter)
        clear_css_state(css)
        assert services.can_view_entry(css, entry, DURING)

    def test_nobody_else_before_results(self, entry, chapter, other_chapter):
        assert not services.can_view_entry(member(other_chapter), entry, AFTER_GRACE)
        assert not services.can_view_entry(member(chapter, status="alumni"), entry, AFTER_GRACE)
        assert not services.can_view_entry(national_officer(), entry, AFTER_GRACE)
        assert not services.can_view_file(national_officer(), entry.files.get(), AFTER_GRACE)

    def test_judges_after_the_close_only(self, entry, round_, other_chapter):
        judge = JudgeFactory(round=round_, user=member(other_chapter, status="alumni"))
        AssignmentFactory(judge=judge, entry=entry)
        assert not services.can_view_entry(judge.user, entry, LAST_SECOND)
        assert not services.can_view_entry(judge.user, entry, IN_GRACE)
        assert services.can_view_entry(judge.user, entry, AFTER_GRACE)
        judge.removed_at = AFTER_GRACE
        judge.save()
        assert not services.can_view_entry(judge.user, entry, AFTER_GRACE)

    def test_qualifiers_are_showcased_after_results(self, entry, round_, other_chapter):
        reader = member(other_chapter)
        entry.advanced = True
        entry.save()
        assert not services.can_view_entry(reader, entry, AFTER_GRACE)
        round_.results_published_at = AFTER_GRACE
        round_.save()
        assert services.can_view_entry(reader, entry, AFTER_GRACE)
        entry.advanced = False
        entry.save()
        assert not services.can_view_entry(reader, entry, AFTER_GRACE)

    def test_replaced_files_are_for_managers(self, entry, chapter, admin_user):
        old = EntryFileFactory(entry=entry, item=entry.round.items.get(), replaced_at=DURING)
        assert not services.can_view_file(member(chapter), old, DURING)
        assert services.can_view_file(admin_user, old, DURING)

    def test_unpublished_competitions_are_for_managers(self, chapter, admin_user):
        round_ = RoundFactory(competition=CompetitionFactory(is_published=False))
        SubmissionItemFactory(round=round_)
        entry = complete_entry(round_, chapter)
        assert not services.can_view_entry(member(chapter), entry, DURING)
        assert services.can_view_entry(admin_user, entry, DURING)


class TestRecipients:
    def test_contacts_officers_pd_chair_and_generic_addresses(self, chapter):
        competition = CompetitionFactory()
        contact = member(chapter, email="contact@example.com")
        give_role(member(chapter, email="pd@example.com"), "pd chair")
        give_role(member(chapter, email="regent@example.com"), "regent")
        member(chapter, email="plain@example.com")
        chapter.email_regent = "regent.generic@example.com"
        chapter.save()
        services.register(competition, chapter, contacts=[contact], welcome=False)
        emails = services.chapter_recipients(chapter, competition)
        assert {"contact@example.com", "pd@example.com", "regent@example.com", "regent.generic@example.com"} <= set(
            emails
        )
        assert "plain@example.com" not in emails

    def test_the_chapter_roles_setting_adds_other_roles(self, chapter):
        give_role(member(chapter, email="service@example.com"), "service chair")
        assert "service@example.com" not in services.chapter_recipients(chapter)
        set_config(services.CHAPTER_ROLES_CONFIG_KEY, "service chair, not a role")
        assert services.email_roles() == {"service chair"}
        assert "service@example.com" in services.chapter_recipients(chapter)

    def test_replies_go_to_the_contact(self):
        competition = CompetitionFactory(contact_email="")
        assert services.reply_to(competition) == [services.CENTRAL_OFFICE_EMAIL]
        give_role(
            member(ChapterFactory(name="delta"), status="alumni", email="pdd@example.com"),
            "professional development director",
        )
        assert services.reply_to(competition) == ["pdd@example.com"]
        competition.contact_email = "necc@example.com"
        assert services.reply_to(competition) == ["necc@example.com"]


class TestCurrentCompetition:
    def test_members_see_the_newest_published_one(self, admin_user):
        assert services.current_competition(member(ChapterFactory(name="alpha"))) is None
        hidden = CompetitionFactory(is_published=False)
        assert services.current_competition(admin_user) == hidden
        shown = CompetitionFactory(is_published=True)
        assert services.current_competition(member(ChapterFactory(name="beta"))) == shown
        assert services.current_competition(admin_user) == shown
