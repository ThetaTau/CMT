"""NECCWI-4, 5 and 6: the competition pages, taking part and submitting."""

import csv
import io

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.support.tests.factories import ChapterSupportAssignmentFactory, make_css

from ..models import Entry, EntryMember, Participant, Round
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
)

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("debug_on")]

PDF = b"%PDF-1.4\n1 0 obj\n"
INTENT_OPEN = "2026-09-20 16:00:00"
WINDOW_OPEN = "2026-12-08 17:00:00"
IN_GRACE = "2026-12-12 05:05:00"
AFTER_GRACE = "2026-12-12 05:10:00"


@pytest.fixture
def debug_on():
    # Two-factor sign-in (superusers, CSSs) is off while DEBUG is on.
    with override_settings(DEBUG=True):
        yield


@pytest.fixture
def chapter():
    return ChapterFactory(name="alpha")


@pytest.fixture
def other_chapter():
    return ChapterFactory(name="beta")


@pytest.fixture
def competition():
    return CompetitionFactory(intent_opens_at=eastern(2026, 9, 11), intent_closes_at=eastern(2026, 9, 28, 23, 59, 59))


@pytest.fixture
def round_(competition):
    round_ = RoundFactory(competition=competition)
    SubmissionItemFactory(round=round_, label="Proposal", file_types=["pdf", "powerpoint"], order=1)
    SubmissionItemFactory(round=round_, label="Video", kind="link", file_types=[], required=False, order=2)
    return round_


@pytest.fixture
def login(auto_login_user):
    def log_in(user):
        client, _ = auto_login_user(user=user)
        return client

    return log_in


@pytest.fixture
def manager(chapter):
    return give_role(member(ChapterFactory(name="delta"), status="alumni"), "professional development director")


def detail_url(competition):
    return reverse("competitions:detail", args=[competition.slug])


def submit_url(round_):
    return reverse("competitions:submit", args=[round_.competition.slug, round_.number])


def entry_post(round_, title="Solar for all", summary="Panels on every roof", pdf=PDF, name="deck.pdf", **extra):
    proposal = round_.items.get(label="Proposal")
    video = round_.items.get(label="Video")
    data = {
        "title": title,
        "summary": summary,
        f"item_{video.pk}": extra.pop("video", ""),
        "team-TOTAL_FORMS": "0",
        "team-INITIAL_FORMS": "0",
        "team-MIN_NUM_FORMS": "0",
        "team-MAX_NUM_FORMS": "40",
    }
    if pdf is not None:
        data[f"item_{proposal.pk}"] = SimpleUploadedFile(name, pdf)
    data.update(extra)
    return data


class TestCompetitionPage:
    def test_members_see_published_competitions_only(self, login, chapter, competition, manager):
        hidden = CompetitionFactory(is_published=False, case_title="A secret case")
        client = login(member(chapter))
        assert client.get(detail_url(hidden)).status_code == 404
        listing = client.get(reverse("competitions:list")).content.decode()
        assert competition.case_title in listing and "A secret case" not in listing
        manager_page = login(manager).get(detail_url(hidden))
        assert manager_page.status_code == 200
        assert "Not published" in manager_page.content.decode()

    def test_times_show_in_eastern(self, login, chapter, round_):
        page = login(member(chapter)).get(detail_url(round_.competition)).content.decode()
        assert "Fri, Dec 11, 2026, 11:59 pm Eastern" in page

    def test_entering_without_registering_is_offered_only_while_the_proposal_window_is_open(
        self, login, chapter, round_, freezer
    ):
        freezer.move_to(WINDOW_OPEN)
        page = login(member(chapter)).get(detail_url(round_.competition)).content.decode()
        assert "can still enter by uploading its proposal" in page
        freezer.move_to(AFTER_GRACE)
        page = login(member(chapter)).get(detail_url(round_.competition)).content.decode()
        assert "can still enter" not in page

    def test_the_menu_item_and_current_redirect(self, login, chapter, competition):
        client = login(member(chapter))
        home = client.get(reverse("home")).content.decode()
        assert reverse("competitions:detail", args=[competition.slug]) in home
        assert client.get(reverse("competitions:current"))["Location"] == detail_url(competition)
        competition.is_published = False
        competition.save()
        assert (
            reverse("competitions:detail", args=[competition.slug]) not in client.get(reverse("home")).content.decode()
        )
        assert client.get(reverse("competitions:current"))["Location"] == reverse("competitions:list")


class TestYourChapterPanel:
    def test_unregistered_chapter_during_the_intent_window(self, login, chapter, round_, freezer):
        person = member(chapter, status="pnm")
        freezer.move_to(INTENT_OPEN)
        page = login(person).get(detail_url(round_.competition)).content.decode()
        assert 'id="your-chapter"' in page
        assert "Register the chapter" in page

    def test_registered_chapter_during_the_window(self, login, chapter, round_, freezer):
        person = member(chapter)
        ParticipantFactory(competition=round_.competition, chapter=chapter)
        freezer.move_to(WINDOW_OPEN)
        page = login(person).get(detail_url(round_.competition)).content.decode()
        assert "Registered" in page and "Start the entry" in page

    def test_an_alumnus_gets_no_buttons(self, login, chapter, round_, freezer):
        alumnus = member(chapter, status="alumni")
        freezer.move_to(WINDOW_OPEN)
        page = login(alumnus).get(detail_url(round_.competition)).content.decode()
        assert "Current members and PNMs of the chapter register it" in page
        assert "Start the entry" not in page and "Register the chapter" not in page

    def test_a_national_officer_using_the_region_bar_keeps_their_own_chapter(
        self, login, chapter, other_chapter, round_, freezer
    ):
        from thetatauCMT.users.models import UserAlter

        officer = national_officer(chapter=other_chapter)
        UserAlter.objects.update_or_create(user=officer, defaults={"chapter": chapter})
        ParticipantFactory(competition=round_.competition, chapter=chapter)
        freezer.move_to(WINDOW_OPEN)
        page = login(officer).get(detail_url(round_.competition)).content.decode()
        assert f"Your chapter: {other_chapter.full_name}" in page
        assert "Start the entry" not in page


class TestHomeCard:
    def test_register_then_submit_then_nothing(self, login, chapter, round_, freezer):
        person = member(chapter)
        freezer.move_to(INTENT_OPEN)
        assert "Register the" in login(person).get(reverse("home")).content.decode()
        ParticipantFactory(competition=round_.competition, chapter=chapter)
        freezer.move_to(WINDOW_OPEN)
        client = login(person)  # sessions last two weeks; the clock moved further
        page = client.get(reverse("home")).content.decode()
        assert 'id="case-competition-card"' in page and "Open the Proposal" in page
        entry = EntryFactory(round=round_, chapter=chapter, summary="Done")
        EntryFileFactory(entry=entry, item=round_.items.get(label="Proposal"))
        assert 'id="case-competition-card"' not in client.get(reverse("home")).content.decode()

    def test_unregistered_chapters_are_not_nagged_during_the_window(self, login, chapter, round_, freezer):
        person = member(chapter)
        freezer.move_to(WINDOW_OPEN)
        assert 'id="case-competition-card"' not in login(person).get(reverse("home")).content.decode()


class TestRegistering:
    def url(self, competition):
        return reverse("competitions:intent", args=[competition.slug])

    def test_registering_names_contacts_and_sends_the_welcome(
        self, login, chapter, competition, freezer, django_capture_on_commit_callbacks
    ):
        person, contact = member(chapter), member(chapter, status="pnm", email="contact@example.com")
        freezer.move_to(INTENT_OPEN)
        client = login(person)
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(
                self.url(competition), {"contacts": [contact.pk], "team_size_estimate": "5", "note": "Excited"}
            )
        assert response.status_code == 302
        participant = Participant.objects.get(competition=competition, chapter=chapter)
        assert participant.source == Participant.Source.INTENT and participant.declared_by == person
        assert list(participant.contacts.all()) == [contact]
        assert len(mail.outbox) == 1 and "contact@example.com" in mail.outbox[0].to
        assert "is registered" in mail.outbox[0].subject
        assert "Registered the" in client.get(self.url(competition)).content.decode()

    def test_not_after_the_intent_window(self, login, chapter, competition, freezer):
        person = member(chapter)
        freezer.move_to("2026-10-15 16:00:00")
        login(person).post(self.url(competition), {"team_size_estimate": "5"})
        assert not Participant.objects.exists()

    def test_contacts_change_after_the_intent_window_and_withdraw_rejoin(
        self, login, chapter, round_, freezer, django_capture_on_commit_callbacks
    ):
        person, contact = member(chapter), member(chapter)
        participant = ParticipantFactory(competition=round_.competition, chapter=chapter)
        freezer.move_to("2026-10-15 16:00:00")
        client = login(person)
        url = self.url(round_.competition)
        with django_capture_on_commit_callbacks(execute=True):
            client.post(url, {"contacts": [contact.pk], "team_size_estimate": "3", "note": ""})
        assert list(participant.contacts.all()) == [contact]
        assert not mail.outbox  # no welcome for a chapter already registered
        client.post(url, {"action": "withdraw"})
        participant.refresh_from_db()
        assert participant.withdrawn_at is not None
        client.post(url, {"contacts": [contact.pk], "team_size_estimate": "3", "note": ""})
        participant.refresh_from_db()
        assert participant.withdrawn_at is None

    def test_alumni_and_other_chapters_are_turned_away(self, login, chapter, other_chapter, competition, freezer):
        alumnus = member(chapter, status="alumni")
        freezer.move_to(INTENT_OPEN)
        response = login(alumnus).post(self.url(competition), {"team_size_estimate": "5"})
        assert response.status_code == 302 and not Participant.objects.exists()

    def test_a_css_is_refused_by_the_view_only_rule(self, login, chapter, competition, freezer):
        from thetatauCMT.support.services import clear_css_state

        css = make_css()
        ChapterSupportAssignmentFactory(user=css, chapter=chapter)
        clear_css_state(css)
        freezer.move_to(INTENT_OPEN)
        login(css).post(self.url(competition), {"team_size_estimate": "5"})
        assert not Participant.objects.exists()


class TestStatusPage:
    def url(self, competition):
        return reverse("competitions:manage", args=[competition.slug])

    def test_national_officers_read_only_managers_act_members_turned_away(
        self, login, chapter, round_, manager, freezer
    ):
        ParticipantFactory(competition=round_.competition, chapter=chapter)
        freezer.move_to(WINDOW_OPEN)
        officer_page = login(national_officer()).get(self.url(round_.competition))
        assert officer_page.status_code == 200
        text = officer_page.content.decode()
        assert chapter.name in text and "Upload on behalf" not in text and "Download CSV" not in text
        manager_page = login(manager).get(self.url(round_.competition)).content.decode()
        assert "Upload on behalf" in manager_page and "Extension" in manager_page
        assert login(member(chapter)).get(self.url(round_.competition)).status_code == 302

    def test_csv_of_chapters_taking_part(self, login, chapter, round_, manager):
        ParticipantFactory(competition=round_.competition, chapter=chapter, note="Ready")
        response = login(manager).get(reverse("competitions:export", args=[round_.competition.slug, "participants"]))
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        assert rows[0][0] == "Chapter" and rows[1][0] == chapter.name and "Ready" in rows[1]
        assert (
            login(national_officer())
            .get(reverse("competitions:export", args=[round_.competition.slug, "entries"]))
            .status_code
            == 302
        )

    def test_unfinished_entries_are_incomplete_after_the_close(
        self, login, chapter, other_chapter, round_, manager, freezer
    ):
        ParticipantFactory(competition=round_.competition, chapter=chapter)
        ParticipantFactory(competition=round_.competition, chapter=other_chapter)
        EntryFactory(round=round_, chapter=chapter, title="Solar", summary="")
        freezer.move_to(AFTER_GRACE)
        text = login(manager).get(self.url(round_.competition)).content.decode()
        assert "0 submitted, 1 incomplete and 1 not submitted, of 2 taking part." in text
        assert "In progress" not in text and "Not started" not in text


class TestFinalRound:
    """Only the Regional Qualifiers enter the final submission (owner, 2026-11-20)."""

    @pytest.fixture
    def final(self, round_, chapter, other_chapter):
        EntryFactory(round=round_, chapter=chapter, submitted_at=eastern(2026, 12, 10), advanced=True)
        EntryFactory(round=round_, chapter=other_chapter, submitted_at=eastern(2026, 12, 10), advanced=False)
        round_.results_published_at = eastern(2027, 1, 15)
        round_.save()
        final = RoundFactory(
            competition=round_.competition,
            number=2,
            name="Final submission",
            selection=Round.Selection.PLACES,
            eligibility=Round.Eligibility.ADVANCED,
            places=2,
            opens_at=eastern(2027, 5, 21),
            closes_at=eastern(2027, 5, 28, 23, 59, 59),
            judging_closes_at=eastern(2027, 6, 25, 23, 59, 59),
        )
        SubmissionItemFactory(round=final, label="Final report", file_types=["pdf"])
        return final

    def test_a_chapter_not_selected_cannot_open_it(self, login, chapter, other_chapter, final, freezer):
        freezer.move_to("2027-05-24 17:00:00")
        assert login(member(chapter)).get(submit_url(final)).status_code == 200
        refused = login(member(other_chapter)).get(submit_url(final), follow=True)
        assert "Only the Regional Qualifiers can enter the Final submission." in refused.content.decode()
        assert not Entry.objects.filter(round=final).exists()

    def test_nor_get_an_extension(self, login, other_chapter, final, manager, freezer):
        freezer.move_to("2027-05-30 17:00:00")
        client = login(manager)
        url = reverse("competitions:extension", args=[final.competition.slug, 2, other_chapter.slug])
        assert client.post(url, {"until": "2027-06-02T23:59"}).status_code == 302
        assert not Entry.objects.filter(round=final).exists()
        status_page = client.get(reverse("competitions:manage", args=[final.competition.slug])).content.decode()
        assert "Not selected" in status_page


class TestMemberPicker:
    def test_scoped_to_the_chapter_with_pnms_and_without_alumni(self, login, chapter, other_chapter):
        searcher = member(chapter, name="Searcher Person")
        member(chapter, status="pnm", name="Paula Prospect")
        member(chapter, status="alumni", name="Paul Alumnus")
        member(other_chapter, name="Paul Elsewhere")
        response = login(searcher).get(reverse("competitions:member-autocomplete"), {"q": "Pa"})
        names = [result["text"] for result in response.json()["results"]]
        assert names == ["Paula Prospect (PNM)"]

    def test_needs_sign_in(self, client):
        assert client.get(reverse("competitions:member-autocomplete")).status_code == 302


class TestSubmitting:
    def test_before_and_during_the_window(self, login, chapter, round_, freezer, django_capture_on_commit_callbacks):
        person = member(chapter, email="saver@example.com")
        freezer.move_to("2026-12-01 17:00:00")
        client = login(person)
        assert "window opens on" in client.get(submit_url(round_)).content.decode()
        freezer.move_to(WINDOW_OPEN)
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(submit_url(round_), entry_post(round_, video="https://youtu.be/demo"))
        assert response.status_code == 302
        entry = Entry.objects.get(round=round_, chapter=chapter)
        assert entry.submitted_at is not None and entry.files.count() == 2
        assert Participant.objects.get(chapter=chapter).source == Participant.Source.SUBMISSION
        subjects = [message.subject for message in mail.outbox]
        assert any("received" in subject for subject in subjects)  # E5
        assert any("is registered" in subject for subject in subjects)  # E1, a first submission
        receipt = next(message for message in mail.outbox if "received" in message.subject)
        assert "saver@example.com" in receipt.to

    def test_the_grace_minutes_and_after(self, login, chapter, round_, freezer, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        person = member(chapter)
        freezer.move_to(IN_GRACE)
        client = login(person)
        assert "window is closed" in client.get(submit_url(round_)).content.decode()
        client.post(submit_url(round_), entry_post(round_))
        assert Entry.objects.get(chapter=chapter).title == "Solar for all"
        freezer.move_to(AFTER_GRACE)
        client.post(submit_url(round_), entry_post(round_, title="Too late"))
        assert Entry.objects.get(chapter=chapter).title == "Solar for all"

    def test_an_extension_reopens_one_chapter(self, login, chapter, round_, manager, freezer, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        person = member(chapter)
        freezer.move_to("2026-12-13 17:00:00")
        manager_client = login(manager)
        url = reverse("competitions:extension", args=[round_.competition.slug, 1, chapter.slug])
        manager_client.post(url, {"until": "2026-12-14T23:59"})
        entry = Entry.objects.get(round=round_, chapter=chapter)
        assert entry.deadline_override == eastern(2026, 12, 14, 23, 59)
        login(person).post(submit_url(round_), entry_post(round_))
        entry.refresh_from_db()
        assert entry.title == "Solar for all" and entry.submitted_at is not None

    def test_a_manager_uploads_on_behalf_after_the_close(
        self, login, chapter, round_, manager, freezer, settings, tmp_path
    ):
        settings.MEDIA_ROOT = tmp_path
        freezer.move_to("2026-12-20 17:00:00")
        url = reverse("competitions:submit_on_behalf", args=[round_.competition.slug, 1, chapter.slug])
        response = login(manager).post(url, entry_post(round_))
        assert response.status_code == 302
        entry = Entry.objects.get(round=round_, chapter=chapter)
        assert entry.last_saved_on_behalf and entry.last_saved_by == manager
        assert login(member(chapter)).get(url).status_code == 302

    @pytest.mark.parametrize("name, content", [("deck.pdf", b"MZ\x90\x00program"), ("deck.docx", PDF)])
    def test_wrong_files_are_refused_and_nothing_is_saved(self, login, chapter, round_, freezer, name, content):
        person = member(chapter)
        freezer.move_to(WINDOW_OPEN)
        response = login(person).post(submit_url(round_), entry_post(round_, pdf=content, name=name))
        assert response.status_code == 200
        assert "Nothing was saved" in response.content.decode()
        assert not Entry.objects.exists()

    def test_a_missing_required_item_is_listed(self, login, chapter, round_, freezer):
        person = member(chapter)
        freezer.move_to(WINDOW_OPEN)
        client = login(person)
        client.post(submit_url(round_), entry_post(round_, pdf=None))
        entry = Entry.objects.get(chapter=chapter)
        assert entry.submitted_at is None
        assert "<strong>Still needed:</strong> Proposal" in client.get(submit_url(round_)).content.decode()

    def test_replacing_a_file_keeps_the_old_one_for_managers(
        self, login, chapter, round_, manager, freezer, settings, tmp_path
    ):
        settings.MEDIA_ROOT = tmp_path
        person = member(chapter)
        freezer.move_to(WINDOW_OPEN)
        client = login(person)
        client.post(submit_url(round_), entry_post(round_, name="first.pdf"))
        client.post(submit_url(round_), entry_post(round_, name="second.pdf"))
        entry = Entry.objects.get(chapter=chapter)
        page = client.get(reverse("competitions:entry", args=[entry.public_id])).content.decode()
        assert "second.pdf" in page and "first.pdf" not in page
        manager_page = login(manager).get(reverse("competitions:entry", args=[entry.public_id])).content.decode()
        assert "first.pdf" in manager_page

    def test_the_team_list(self, login, chapter, round_, freezer):
        person, teammate, pnm = member(chapter), member(chapter), member(chapter, status="pnm")
        freezer.move_to(WINDOW_OPEN)
        client = login(person)
        rows = {
            "team-TOTAL_FORMS": "3",
            "team-0-user": str(teammate.pk),
            "team-0-team_role": "Team lead",
            "team-1-user": str(pnm.pk),
            "team-1-team_role": "",
            "team-2-user": "",
            "team-2-team_role": "",
        }
        client.post(submit_url(round_), entry_post(round_, pdf=None, **rows))
        entry = Entry.objects.get(chapter=chapter)
        assert [(row.user, row.team_role) for row in entry.team.all()] == [(teammate, "Team lead"), (pnm, "")]

    def test_the_team_takes_members_of_the_chapter_only(self, login, chapter, other_chapter, round_, freezer):
        person, outsider = member(chapter), member(other_chapter)
        freezer.move_to(WINDOW_OPEN)
        rows = {"team-TOTAL_FORMS": "1", "team-0-user": str(outsider.pk), "team-0-team_role": "Lead"}
        response = login(person).post(submit_url(round_), entry_post(round_, pdf=None, **rows))
        assert response.status_code == 200
        assert "Select a valid choice" in response.content.decode()
        assert not Entry.objects.exists() and not EntryMember.objects.exists()

    def test_a_role_without_a_member_is_explained(self, login, chapter, round_, freezer):
        person = member(chapter)
        freezer.move_to(WINDOW_OPEN)
        rows = {"team-TOTAL_FORMS": "1", "team-0-user": "", "team-0-team_role": "Lead"}
        response = login(person).post(submit_url(round_), entry_post(round_, pdf=None, **rows))
        assert "Choose the member, or clear the role." in response.content.decode()


class TestEntryVisibility:
    @pytest.fixture
    def entry(self, round_, chapter):
        entry = EntryFactory(round=round_, chapter=chapter, summary="S", submitted_at=eastern(2026, 12, 8))
        EntryFileFactory(entry=entry, item=round_.items.get(label="Proposal"))
        return entry

    def test_other_chapters_and_early_judges_get_a_404(self, login, entry, round_, other_chapter, freezer):
        judge = JudgeFactory(round=round_, user=member(other_chapter, status="alumni"))
        AssignmentFactory(judge=judge, entry=entry)
        freezer.move_to(WINDOW_OPEN)
        url = reverse("competitions:entry", args=[entry.public_id])
        file_url = reverse("competitions:file", args=[entry.files.get().public_id])
        assert login(member(other_chapter)).get(url).status_code == 404
        judge_client = login(judge.user)
        assert judge_client.get(url).status_code == 404
        assert judge_client.get(file_url).status_code == 404
        freezer.move_to(AFTER_GRACE)
        assert judge_client.get(url).status_code == 200
        assert judge_client.get(file_url)["Location"] == "https://example.com/proposal"

    def test_members_and_css_of_the_chapter(self, login, entry, chapter, freezer):
        from thetatauCMT.support.services import clear_css_state

        freezer.move_to(WINDOW_OPEN)
        url = reverse("competitions:entry", args=[entry.public_id])
        assert login(member(chapter, status="pnm")).get(url).status_code == 200
        css = make_css()
        ChapterSupportAssignmentFactory(user=css, chapter=chapter)
        clear_css_state(css)
        assert login(css).get(url).status_code == 200
        assert login(national_officer()).get(url).status_code == 404
