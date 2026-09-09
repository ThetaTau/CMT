import datetime

import pytest
from django.contrib.auth.models import AnonymousUser, Group
from django.core import mail
from django.utils import timezone

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.configs.models import Config
from thetatauCMT.regions.tests.factories import RegionFactory
from thetatauCMT.users.models import UserAlter, UserRoleChange
from thetatauCMT.users.tests.factories import UserFactory

from .. import services
from ..models import (
    HandoffNotice,
    PositionOverride,
    ReportAcknowledgement,
    ReportAnswer,
    ReportAttachment,
    ReportObligation,
    ReportTag,
    ReportTemplate,
    TemplatePrompt,
    TransitionReport,
)

pytestmark = pytest.mark.django_db

TODAY = datetime.date.today()


def _role_change(chapter, role, end, start=None, user=None):
    # NOTE: deliberately NOT UserRoleChangeFactory -- its `current`
    # post_generation hook unconditionally overwrites `end` (persisted to the
    # DB despite skip_postgeneration_save) with a random date whenever it
    # isn't passed truthy, clobbering the exact date this helper needs.
    user = user or UserFactory(chapter=chapter)
    start = start or end - datetime.timedelta(days=180)
    return UserRoleChange.objects.create(user=user, role=role, start=start, end=end)


def _council_officer():
    """A user who sees every submitted report nationally (2026-09 access
    tightening narrowed a plain NATIONAL_OFFICER role to "their own
    position_key only" -- tests that just need "someone who can see
    everything" to exercise an unrelated filter use a Council role instead).
    """
    user = UserFactory()
    user.current_roles = ["grand regent"]
    user.save(update_fields=["current_roles"])
    user.groups.add(Group.objects.get_or_create(name="natoff")[0])
    return user


# ---------------------------------------------------------------------------
# resolve_position_status / is_position_required
# ---------------------------------------------------------------------------
def test_chapter_officer_position_is_always_required():
    assert services.resolve_position_status("treasurer") == "required"
    assert services.is_position_required("treasurer") is True


def test_pledge_educator_and_risk_mgmt_chair_are_required_like_chapter_officers():
    assert services.resolve_position_status("pledge/new member educator") == "required"
    assert services.resolve_position_status("risk management chair") == "required"


def test_council_position_is_optional_by_default():
    assert services.resolve_position_status("grand regent") == "optional"
    assert services.is_position_required("grand regent") is False


def test_national_officer_position_is_optional_by_default():
    assert services.resolve_position_status("regional director") == "optional"


def test_committee_chair_position_is_optional_by_default():
    assert services.resolve_position_status("committee chair") == "optional"


def test_advisor_roles_and_unknown_keys_are_out_of_scope():
    assert services.resolve_position_status("adviser") is None
    assert services.resolve_position_status("not a real position") is None


def test_type_level_disable_excludes_optional_positions():
    Config.objects.create(key="TRANSITIONS_COUNCIL_ENABLED", value="off", description="")
    assert services.resolve_position_status("grand regent") == "excluded"
    # A different optional type is unaffected.
    assert services.resolve_position_status("regional director") == "optional"


def test_type_level_disable_never_affects_chapter_officer():
    Config.objects.create(key="TRANSITIONS_COUNCIL_ENABLED", value="off", description="")
    assert services.resolve_position_status("treasurer") == "required"


def test_per_position_override_wins_over_chapter_officer_default():
    PositionOverride.objects.create(position_key="treasurer", status="excluded")
    assert services.resolve_position_status("treasurer") == "excluded"


def test_per_position_override_wins_over_disabled_type():
    Config.objects.create(key="TRANSITIONS_COUNCIL_ENABLED", value="off", description="")
    PositionOverride.objects.create(position_key="grand regent", status="required")
    assert services.resolve_position_status("grand regent") == "required"


# ---------------------------------------------------------------------------
# Offset config -- defaults present, Config values parsed correctly
# ---------------------------------------------------------------------------
def test_offset_defaults_present_with_no_config_rows():
    assert services.get_due_date_offset_days() == services.DEFAULT_DUE_DATE_OFFSET_DAYS
    assert services.get_seasonal_reminder_offset_days() == services.DEFAULT_SEASONAL_REMINDER_OFFSET_DAYS
    assert services.get_reminder_offsets_days() == list(services.DEFAULT_REMINDER_OFFSETS_DAYS)


def test_offset_config_rows_are_parsed():
    Config.objects.create(key="TRANSITIONS_DUE_DATE_OFFSET_DAYS", value="21", description="")
    Config.objects.create(key="TRANSITIONS_SEASONAL_REMINDER_OFFSET_DAYS", value="45", description="")
    Config.objects.create(key="TRANSITIONS_REMINDER_OFFSETS_DAYS", value="30,15,-7,-14", description="")

    assert services.get_due_date_offset_days() == 21
    assert services.get_seasonal_reminder_offset_days() == 45
    assert services.get_reminder_offsets_days() == [30, 15, -7, -14]


def test_reminder_offsets_default_includes_past_due_escalation():
    # 21/14/7/1 before due, plus -1/-7/-14 after due for past-due escalation.
    assert services.get_reminder_offsets_days() == [21, 14, 7, 1, -1, -7, -14]


def test_offset_config_falls_back_on_unparsable_value():
    Config.objects.create(key="TRANSITIONS_DUE_DATE_OFFSET_DAYS", value="not a number", description="")
    assert services.get_due_date_offset_days() == services.DEFAULT_DUE_DATE_OFFSET_DAYS


# ---------------------------------------------------------------------------
# get_default_lookahead_days -- derived from the offsets above (decision I21)
# ---------------------------------------------------------------------------
def test_default_lookahead_days_with_no_config_rows():
    # due_offset(14) + largest reminder offset(21) + buffer(10) = 45.
    assert services.get_default_lookahead_days() == 45


def test_default_lookahead_days_widens_when_reminder_offsets_configured_larger():
    Config.objects.create(key="TRANSITIONS_REMINDER_OFFSETS_DAYS", value="60,30,14", description="")
    assert services.get_default_lookahead_days() == 14 + 60 + services.DEFAULT_LOOKAHEAD_BUFFER_DAYS


# ---------------------------------------------------------------------------
# resolve_template -- 3-tier resolution (TRWI-2)
# ---------------------------------------------------------------------------
def test_resolve_template_out_of_scope_position_returns_none():
    assert services.resolve_template("adviser") is None
    assert services.resolve_template("not a real position") is None


def test_resolve_template_returns_none_when_nothing_is_seeded():
    assert services.resolve_template("treasurer") is None


def test_resolve_template_falls_back_to_type_default():
    type_default = ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Chapter Officer Report")
    assert services.resolve_template("treasurer") == type_default
    # Any chapter_officer-type position resolves to the same type default.
    assert services.resolve_template("pledge/new member educator") == type_default


def test_resolve_template_prefers_exact_position_key_match():
    ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Chapter Officer Report")
    treasurer_specific = ReportTemplate.objects.create(
        position_type="CHAPTER_OFFICER", position_key="treasurer", name="Treasurer Report"
    )
    assert services.resolve_template("treasurer") == treasurer_specific
    # A sibling chapter_officer position still gets the type default.
    assert services.resolve_template("scribe").name == "Chapter Officer Report"


def test_resolve_template_falls_back_to_global_default():
    global_default = ReportTemplate.objects.create(position_type="", position_key="", name="Global Default")
    assert services.resolve_template("treasurer") == global_default
    assert services.resolve_template("grand regent") == global_default


def test_resolve_template_ignores_inactive_templates():
    ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Inactive", is_active=False)
    global_default = ReportTemplate.objects.create(position_type="", position_key="", name="Global Default")
    assert services.resolve_template("treasurer") == global_default


# ---------------------------------------------------------------------------
# generate_obligations -- term-end trigger (TRWI-3)
# ---------------------------------------------------------------------------
def test_generate_obligations_creates_obligation_for_term_ending_soon():
    chapter = ChapterFactory()
    # 30 days out so due_date (end - 14) is still in the future -- keeps
    # status "open" rather than being immediately marked "missed" below.
    end = TODAY + datetime.timedelta(days=30)
    role_change = _role_change(chapter, "treasurer", end)

    counts = services.generate_obligations()

    obligation = ReportObligation.objects.get(chapter=chapter, position_key="treasurer")
    assert counts["term_end_created"] == 1
    assert obligation.officer == role_change.user
    assert obligation.role_change == role_change
    assert obligation.position_type == "CHAPTER_OFFICER"
    assert obligation.term_start == role_change.start
    assert obligation.term_end == end
    assert obligation.due_date == end - datetime.timedelta(days=services.DEFAULT_DUE_DATE_OFFSET_DAYS)
    assert obligation.is_required is True
    assert obligation.status == "open"


def test_generate_obligations_is_idempotent():
    chapter = ChapterFactory()
    _role_change(chapter, "treasurer", TODAY + datetime.timedelta(days=10))

    services.generate_obligations()
    pk = ReportObligation.objects.get(chapter=chapter, position_key="treasurer").pk
    counts = services.generate_obligations()

    assert ReportObligation.objects.filter(chapter=chapter, position_key="treasurer").count() == 1
    assert ReportObligation.objects.get(chapter=chapter, position_key="treasurer").pk == pk
    assert counts["term_end_created"] == 0


def test_generate_obligations_optional_position_excluded_when_config_off():
    Config.objects.create(key="TRANSITIONS_COUNCIL_ENABLED", value="off", description="")
    chapter = ChapterFactory()
    _role_change(chapter, "grand regent", TODAY + datetime.timedelta(days=10))

    services.generate_obligations()

    assert not ReportObligation.objects.filter(chapter=chapter, position_key="grand regent").exists()


def test_generate_obligations_optional_position_created_when_config_on():
    chapter = ChapterFactory()
    _role_change(chapter, "grand regent", TODAY + datetime.timedelta(days=10))

    services.generate_obligations()

    obligation = ReportObligation.objects.get(chapter=chapter, position_key="grand regent")
    assert obligation.position_type == "COUNCIL"
    assert obligation.is_required is False


def test_generate_obligations_per_position_override_excludes_even_required_position():
    PositionOverride.objects.create(position_key="treasurer", status="excluded")
    chapter = ChapterFactory()
    _role_change(chapter, "treasurer", TODAY + datetime.timedelta(days=10))

    services.generate_obligations()

    assert not ReportObligation.objects.filter(chapter=chapter, position_key="treasurer").exists()


def test_generate_obligations_respects_lookahead_window():
    chapter = ChapterFactory()
    _role_change(chapter, "treasurer", TODAY + datetime.timedelta(days=100))

    services.generate_obligations(lookahead_days=45)
    assert not ReportObligation.objects.filter(chapter=chapter, position_key="treasurer").exists()

    services.generate_obligations(lookahead_days=150)
    assert ReportObligation.objects.filter(chapter=chapter, position_key="treasurer").exists()


def test_generate_obligations_default_lookahead_boundary():
    chapter = ChapterFactory()
    # 50 days is just beyond the 45-day default (14 + 21 + 10).
    _role_change(chapter, "treasurer", TODAY + datetime.timedelta(days=50))

    services.generate_obligations()
    assert not ReportObligation.objects.filter(chapter=chapter, position_key="treasurer").exists()

    services.generate_obligations(lookahead_days=60)
    assert ReportObligation.objects.filter(chapter=chapter, position_key="treasurer").exists()


def test_generate_obligations_skips_role_change_outside_lookback_grace():
    chapter = ChapterFactory()
    # Ended more than a year ago -- outside the 365-day backward grace window
    # (decision I22) -- and there's a current holder so the vacancy safety
    # net doesn't apply either.
    _role_change(chapter, "treasurer", TODAY - datetime.timedelta(days=400))
    _role_change(chapter, "treasurer", TODAY + datetime.timedelta(days=300))

    services.generate_obligations()

    assert ReportObligation.objects.filter(chapter=chapter, position_key="treasurer").count() == 0


def test_generate_obligations_mid_term_turnover_each_role_change_gets_its_own_obligation():
    chapter = ChapterFactory()
    first = _role_change(chapter, "treasurer", TODAY + datetime.timedelta(days=5))
    second = _role_change(chapter, "treasurer", TODAY + datetime.timedelta(days=40))

    services.generate_obligations()

    obligations = ReportObligation.objects.filter(chapter=chapter, position_key="treasurer")
    assert obligations.count() == 2
    assert set(obligations.values_list("role_change_id", flat=True)) == {first.pk, second.pk}


# ---------------------------------------------------------------------------
# generate_obligations -- already-vacant safety net (TRWI-3)
# ---------------------------------------------------------------------------
def test_generate_obligations_never_creates_vacancy_obligation_from_a_holder_more_than_a_year_stale():
    # Decision I20: the vacancy safety net never reaches back further than a
    # year to pick a stale role change. Neither trigger fires here since
    # trigger 1's own grace window (decision I22) is also capped at 365 days.
    chapter = ChapterFactory()
    _role_change(chapter, "regent", TODAY - datetime.timedelta(days=400))

    services.generate_obligations()

    assert not ReportObligation.objects.filter(chapter=chapter, position_key="regent").exists()


def test_generate_obligations_vacant_required_position_within_a_year_still_gets_an_obligation():
    # Decisions I20 and I22 both cap at 365 days, so a required position
    # that's vacant now but was held within the last year gets its
    # obligation via trigger 1 (term-ending-soon) with the last known holder
    # as officer -- NOT trigger 2's officer=None path, since trigger 1 always
    # claims the natural key first. See open question J24 in
    # transitions-app.md re: whether officer should still be nulled out here.
    chapter = ChapterFactory()
    stale = _role_change(chapter, "regent", TODAY - datetime.timedelta(days=200))

    services.generate_obligations()

    obligation = ReportObligation.objects.get(chapter=chapter, position_key="regent")
    assert obligation.officer == stale.user
    assert obligation.role_change == stale
    assert obligation.is_required is True


def test_generate_obligations_never_held_position_creates_nothing():
    chapter = ChapterFactory()
    # No UserRoleChange at all for "regent" in this chapter.
    services.generate_obligations()
    assert not ReportObligation.objects.filter(chapter=chapter, position_key="regent").exists()


def test_generate_obligations_vacancy_safety_net_only_applies_to_required_positions():
    chapter = ChapterFactory()
    # Also outside trigger 1's 365-day grace, so only trigger 2's role scoping
    # is under test here -- committee chair is never in CHAPTER_OFFICER_REQUIRED.
    _role_change(chapter, "committee chair", TODAY - datetime.timedelta(days=400))

    services.generate_obligations()

    assert not ReportObligation.objects.filter(chapter=chapter, position_key="committee chair").exists()


def test_generate_obligations_vacancy_safety_net_does_not_duplicate_term_end_trigger():
    # The stale role change's end (2 days ago) is inside the lookback grace
    # window, so trigger 1 already covers it -- trigger 2 must not also fire.
    # This is now the COMMON case since decisions I20/I22 widened both
    # windows to 365 days -- see the "within_a_year" test above.
    chapter = ChapterFactory()
    role_change = _role_change(chapter, "regent", TODAY - datetime.timedelta(days=2))

    counts = services.generate_obligations()

    assert ReportObligation.objects.filter(chapter=chapter, position_key="regent").count() == 1
    obligation = ReportObligation.objects.get(chapter=chapter, position_key="regent")
    assert obligation.officer == role_change.user  # trigger 1's officer, not trigger 2's None
    assert counts["term_end_created"] == 1
    assert counts["vacant_created"] == 0


# ---------------------------------------------------------------------------
# generate_obligations -- missed marking (TRWI-3)
# ---------------------------------------------------------------------------
def test_generate_obligations_marks_past_due_open_obligations_missed():
    chapter = ChapterFactory()
    role_change = _role_change(chapter, "treasurer", TODAY - datetime.timedelta(days=20))
    obligation = ReportObligation.objects.create(
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key="treasurer",
        officer=role_change.user,
        role_change=role_change,
        term_start=role_change.start,
        term_end=role_change.end,
        due_date=TODAY - datetime.timedelta(days=1),
        is_required=True,
        status="open",
    )

    counts = services.generate_obligations()

    obligation.refresh_from_db()
    assert obligation.status == "missed"
    assert counts["missed"] == 1


@pytest.mark.parametrize("status", ["submitted", "na_vacant", "missed"])
def test_generate_obligations_does_not_touch_non_open_obligations(status):
    chapter = ChapterFactory()
    role_change = _role_change(chapter, "treasurer", TODAY - datetime.timedelta(days=20))
    ReportObligation.objects.create(
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key="treasurer",
        officer=role_change.user,
        role_change=role_change,
        term_start=role_change.start,
        term_end=role_change.end,
        due_date=TODAY - datetime.timedelta(days=1),
        is_required=True,
        status=status,
    )

    services.generate_obligations()

    assert ReportObligation.objects.get(chapter=chapter, position_key="treasurer").status == status


# ---------------------------------------------------------------------------
# generate_obligations -- dry-run (TRWI-3)
# ---------------------------------------------------------------------------
def test_generate_obligations_dry_run_writes_nothing():
    chapter = ChapterFactory()
    _role_change(chapter, "treasurer", TODAY + datetime.timedelta(days=10))

    counts = services.generate_obligations(dry_run=True)

    assert counts["term_end_created"] == 1
    assert ReportObligation.objects.count() == 0


# ---------------------------------------------------------------------------
# _current_reminder_threshold / get_rd_escalation_offset_days (TRWI-4)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "days_until_due,expected",
    [
        (25, None),  # nothing crossed yet (furthest offset is 21)
        (21, 21),
        (15, 21),  # still short of the 14-day mark -- 21 remains the most recent crossed
        (0, 1),  # crossed 21/14/7/1 -- most urgent (smallest) crossed is 1
        (-1, -1),
        (-5, -1),
        (-7, -7),
        (-20, -14),  # crossed everything -- most urgent is the most negative
    ],
)
def test_current_reminder_threshold(days_until_due, expected):
    assert services._current_reminder_threshold(days_until_due, services.DEFAULT_REMINDER_OFFSETS_DAYS) == expected


def test_rd_escalation_offset_default_and_configured():
    assert services.get_rd_escalation_offset_days() == services.DEFAULT_RD_ESCALATION_OFFSET_DAYS
    Config.objects.create(key="TRANSITIONS_RD_ESCALATION_OFFSET_DAYS", value="-10", description="")
    assert services.get_rd_escalation_offset_days() == -10


# ---------------------------------------------------------------------------
# send_due_date_reminders (TRWI-4 mechanism 1)
# ---------------------------------------------------------------------------
def _open_obligation(
    chapter, officer, due_date, status="open", last_reminder_offset_sent=None, position_key="treasurer"
):
    return ReportObligation.objects.create(
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key=position_key,
        officer=officer,
        term_start=due_date - datetime.timedelta(days=166),
        term_end=due_date + datetime.timedelta(days=services.DEFAULT_DUE_DATE_OFFSET_DAYS),
        due_date=due_date,
        is_required=True,
        status=status,
        last_reminder_offset_sent=last_reminder_offset_sent,
    )


def test_send_due_date_reminders_sends_to_officer_when_threshold_crossed():
    chapter = ChapterFactory()
    user = UserFactory(chapter=chapter)
    _open_obligation(chapter, user, TODAY + datetime.timedelta(days=21))

    sent = services.send_due_date_reminders()

    assert sent == 1
    obligation = ReportObligation.objects.get(chapter=chapter)
    assert obligation.last_reminder_offset_sent == 21
    assert len(mail.outbox) == 1
    assert set(mail.outbox[0].to) == set(user.emails)


def test_send_due_date_reminders_is_idempotent_for_the_same_threshold():
    chapter = ChapterFactory()
    user = UserFactory(chapter=chapter)
    _open_obligation(chapter, user, TODAY + datetime.timedelta(days=21))

    services.send_due_date_reminders()
    sent_again = services.send_due_date_reminders()

    assert sent_again == 0
    assert len(mail.outbox) == 1


def test_send_due_date_reminders_no_threshold_crossed_yet_sends_nothing():
    chapter = ChapterFactory()
    user = UserFactory(chapter=chapter)
    _open_obligation(chapter, user, TODAY + datetime.timedelta(days=25))

    sent = services.send_due_date_reminders()

    assert sent == 0
    obligation = ReportObligation.objects.get(chapter=chapter)
    assert obligation.last_reminder_offset_sent is None
    assert len(mail.outbox) == 0


def test_send_due_date_reminders_escalates_to_regent_once_past_due():
    chapter = ChapterFactory(email_regent="regent@example.com")
    user = UserFactory(chapter=chapter)
    _open_obligation(chapter, user, TODAY - datetime.timedelta(days=1))

    services.send_due_date_reminders()

    assert "regent@example.com" in mail.outbox[0].to
    assert set(user.emails).issubset(set(mail.outbox[0].to))


def test_send_due_date_reminders_does_not_escalate_to_regent_before_due():
    chapter = ChapterFactory(email_regent="regent@example.com")
    user = UserFactory(chapter=chapter)
    _open_obligation(chapter, user, TODAY + datetime.timedelta(days=1))

    services.send_due_date_reminders()

    assert "regent@example.com" not in mail.outbox[0].to


def test_send_due_date_reminders_escalates_to_rd_at_configured_offset():
    region = RegionFactory(email="region-mailbox@example.com")
    chapter = ChapterFactory(region=region, email_regent="regent@example.com")
    director = UserFactory(chapter=chapter)
    region.directors.add(director)
    user = UserFactory(chapter=chapter)
    # -7 is the default RD escalation offset.
    _open_obligation(chapter, user, TODAY - datetime.timedelta(days=7))

    services.send_due_date_reminders()

    recipients = set(mail.outbox[0].to)
    assert "region-mailbox@example.com" in recipients
    assert set(director.emails).issubset(recipients)
    assert "regent@example.com" in recipients  # RD tier implies the Regent tier too


def test_send_due_date_reminders_does_not_escalate_to_rd_before_configured_offset():
    region = RegionFactory(email="region-mailbox@example.com")
    chapter = ChapterFactory(region=region, email_regent="regent@example.com")
    user = UserFactory(chapter=chapter)
    _open_obligation(chapter, user, TODAY - datetime.timedelta(days=1))

    services.send_due_date_reminders()

    assert "region-mailbox@example.com" not in mail.outbox[0].to


def test_send_due_date_reminders_vacant_pre_due_sends_nothing_but_records_threshold():
    chapter = ChapterFactory()
    _open_obligation(chapter, None, TODAY + datetime.timedelta(days=21))

    sent = services.send_due_date_reminders()

    assert sent == 0
    assert len(mail.outbox) == 0
    assert ReportObligation.objects.get(chapter=chapter).last_reminder_offset_sent == 21


def test_send_due_date_reminders_vacant_past_due_still_escalates_to_regent():
    chapter = ChapterFactory(email_regent="regent@example.com")
    _open_obligation(chapter, None, TODAY - datetime.timedelta(days=1))

    sent = services.send_due_date_reminders()

    assert sent == 1
    assert "regent@example.com" in mail.outbox[0].to


def test_send_due_date_reminders_continues_for_missed_status():
    chapter = ChapterFactory()
    user = UserFactory(chapter=chapter)
    _open_obligation(chapter, user, TODAY - datetime.timedelta(days=1), status="missed")

    sent = services.send_due_date_reminders()

    assert sent == 1


@pytest.mark.parametrize("status", ["submitted", "na_vacant"])
def test_send_due_date_reminders_stops_on_closure(status):
    chapter = ChapterFactory()
    user = UserFactory(chapter=chapter)
    _open_obligation(chapter, user, TODAY - datetime.timedelta(days=1), status=status)

    sent = services.send_due_date_reminders()

    assert sent == 0
    assert len(mail.outbox) == 0


def test_send_due_date_reminders_dry_run_sends_nothing_and_writes_nothing():
    chapter = ChapterFactory()
    user = UserFactory(chapter=chapter)
    _open_obligation(chapter, user, TODAY + datetime.timedelta(days=21))

    sent = services.send_due_date_reminders(dry_run=True)

    assert sent == 1
    assert len(mail.outbox) == 0
    assert ReportObligation.objects.get(chapter=chapter).last_reminder_offset_sent is None


# ---------------------------------------------------------------------------
# send_seasonal_reminder (TRWI-4 mechanism 2)
# ---------------------------------------------------------------------------
@pytest.mark.freeze_time("2026-12-15")  # 17 days before the fall semester ends (Jan 1, 2027)
def test_send_seasonal_reminder_fires_within_window():
    chapter = ChapterFactory()
    user = UserFactory(chapter=chapter)
    _open_obligation(chapter, user, datetime.date(2027, 1, 15))

    sent = services.send_seasonal_reminder()

    assert sent == 1
    assert len(mail.outbox) == 1
    assert set(mail.outbox[0].to) == set(user.emails)
    assert Config.get_value("TRANSITIONS_SEASONAL_REMINDER_LAST_SENT_FOR") == "2027-01-01"


@pytest.mark.freeze_time("2026-11-01")  # 61 days before the fall semester ends -- outside the 30-day window
def test_send_seasonal_reminder_outside_window_does_nothing():
    chapter = ChapterFactory()
    user = UserFactory(chapter=chapter)
    _open_obligation(chapter, user, datetime.date(2027, 1, 15))

    sent = services.send_seasonal_reminder()

    assert sent == 0
    assert len(mail.outbox) == 0


@pytest.mark.freeze_time("2026-12-15")
def test_send_seasonal_reminder_does_not_resend_for_the_same_semester():
    chapter = ChapterFactory()
    user = UserFactory(chapter=chapter)
    _open_obligation(chapter, user, datetime.date(2027, 1, 15))

    services.send_seasonal_reminder()
    sent_again = services.send_seasonal_reminder()

    assert sent_again == 0
    assert len(mail.outbox) == 1


@pytest.mark.freeze_time("2026-12-15")
def test_send_seasonal_reminder_only_emails_users_with_open_obligations():
    chapter = ChapterFactory()
    has_obligation = UserFactory(chapter=chapter)
    no_obligation = UserFactory(chapter=chapter)
    _open_obligation(chapter, has_obligation, datetime.date(2027, 1, 15))

    services.send_seasonal_reminder()

    assert len(mail.outbox) == 1
    assert set(mail.outbox[0].to) == set(has_obligation.emails)
    assert not any(email in mail.outbox[0].to for email in no_obligation.emails)


@pytest.mark.freeze_time("2026-12-15")
def test_send_seasonal_reminder_dry_run_sends_nothing_and_writes_nothing():
    chapter = ChapterFactory()
    user = UserFactory(chapter=chapter)
    _open_obligation(chapter, user, datetime.date(2027, 1, 15))

    sent = services.send_seasonal_reminder(dry_run=True)

    assert sent == 1
    assert len(mail.outbox) == 0
    assert Config.get_value("TRANSITIONS_SEASONAL_REMINDER_LAST_SENT_FOR") == ""


# ---------------------------------------------------------------------------
# get_my_open_obligations (TRWI-4 home dashboard card)
# ---------------------------------------------------------------------------
def test_get_my_open_obligations_scoped_to_viewer():
    chapter = ChapterFactory()
    viewer = UserFactory(chapter=chapter)
    someone_else = UserFactory(chapter=chapter)
    mine = _open_obligation(chapter, viewer, TODAY + datetime.timedelta(days=10), position_key="treasurer")
    _open_obligation(chapter, someone_else, TODAY + datetime.timedelta(days=10), position_key="scribe")

    obligations = list(services.get_my_open_obligations(viewer))

    assert obligations == [mine]


def test_get_my_open_obligations_includes_missed_excludes_closed():
    chapter = ChapterFactory()
    viewer = UserFactory(chapter=chapter)
    _open_obligation(chapter, viewer, TODAY - datetime.timedelta(days=1), status="missed", position_key="treasurer")
    _open_obligation(
        chapter,
        viewer,
        TODAY - datetime.timedelta(days=1),
        status="submitted",
        last_reminder_offset_sent=-14,
        position_key="scribe",
    )

    obligations = list(services.get_my_open_obligations(viewer))

    assert len(obligations) == 1
    assert obligations[0].status == "missed"


# ---------------------------------------------------------------------------
# TRWI-5: compose & submit
# ---------------------------------------------------------------------------
def test_get_my_obligations_includes_every_status():
    chapter = ChapterFactory()
    viewer = UserFactory(chapter=chapter)
    _open_obligation(chapter, viewer, TODAY + datetime.timedelta(days=10), status="open", position_key="treasurer")
    _open_obligation(chapter, viewer, TODAY - datetime.timedelta(days=1), status="submitted", position_key="scribe")
    _open_obligation(
        chapter, viewer, TODAY - datetime.timedelta(days=1), status="na_vacant", position_key="vice regent"
    )

    obligations = services.get_my_obligations(viewer)

    assert obligations.count() == 3


def test_get_or_create_report_creates_draft_authored_by_officer():
    chapter = ChapterFactory()
    officer = UserFactory(chapter=chapter)
    ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Chapter Officer Report", version=3)
    obligation = _open_obligation(chapter, officer, TODAY + datetime.timedelta(days=10))

    report = services.get_or_create_report(obligation)

    assert report.author == officer
    assert report.status == "draft"
    assert report.template_version == 3


def test_get_or_create_report_is_idempotent():
    chapter = ChapterFactory()
    officer = UserFactory(chapter=chapter)
    ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Chapter Officer Report")
    obligation = _open_obligation(chapter, officer, TODAY + datetime.timedelta(days=10))

    first = services.get_or_create_report(obligation)
    second = services.get_or_create_report(obligation)

    assert first.pk == second.pk
    assert TransitionReport.objects.count() == 1


def test_save_draft_writes_answers_without_changing_status():
    chapter = ChapterFactory()
    officer = UserFactory(chapter=chapter)
    template = ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Chapter Officer Report")
    prompt = TemplatePrompt.objects.create(template=template, prompt_key="successes", label="Successes?")
    obligation = _open_obligation(chapter, officer, TODAY + datetime.timedelta(days=10))
    report = services.get_or_create_report(obligation)

    services.save_draft(report, [(prompt, "made progress")])

    report.refresh_from_db()
    assert report.status == "draft"
    answer = report.answers.get(prompt_key="successes")
    assert answer.value == "made progress"
    assert answer.prompt_label_snapshot == "Successes?"


def test_save_draft_upserts_the_same_prompt_key():
    chapter = ChapterFactory()
    officer = UserFactory(chapter=chapter)
    template = ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Chapter Officer Report")
    prompt = TemplatePrompt.objects.create(template=template, prompt_key="successes", label="Successes?")
    obligation = _open_obligation(chapter, officer, TODAY + datetime.timedelta(days=10))
    report = services.get_or_create_report(obligation)

    services.save_draft(report, [(prompt, "first draft")])
    services.save_draft(report, [(prompt, "revised draft")])

    assert report.answers.count() == 1
    assert report.answers.get(prompt_key="successes").value == "revised draft"


def test_submit_report_closes_obligation_and_stamps_submitted_at():
    chapter = ChapterFactory()
    officer = UserFactory(chapter=chapter)
    template = ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Chapter Officer Report")
    prompt = TemplatePrompt.objects.create(template=template, prompt_key="successes", label="Successes?")
    obligation = _open_obligation(chapter, officer, TODAY + datetime.timedelta(days=10))
    report = services.get_or_create_report(obligation)

    services.submit_report(report, [(prompt, "we did well")])

    report.refresh_from_db()
    obligation.refresh_from_db()
    assert report.status == "submitted"
    assert report.submitted_at is not None
    assert obligation.status == "submitted"


def test_submit_report_records_the_template_version_used_at_submission():
    chapter = ChapterFactory()
    officer = UserFactory(chapter=chapter)
    template = ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Chapter Officer Report", version=1)
    obligation = _open_obligation(chapter, officer, TODAY + datetime.timedelta(days=10))
    report = services.get_or_create_report(obligation)
    assert report.template_version == 1

    template.version = 2
    template.save(update_fields=["version"])

    services.submit_report(report, [])

    report.refresh_from_db()
    assert report.template_version == 2


def test_can_close_na_vacant_true_for_chapter_regent():
    chapter = ChapterFactory()
    regent = UserFactory(chapter=chapter)
    regent.current_roles = ["regent"]
    regent.save(update_fields=["current_roles"])
    obligation = _open_obligation(chapter, None, TODAY + datetime.timedelta(days=10))

    assert services.can_close_na_vacant(regent, obligation) is True


def test_can_close_na_vacant_false_for_regent_of_a_different_chapter():
    chapter = ChapterFactory(name="alpha")
    other_chapter = ChapterFactory(name="beta")
    regent = UserFactory(chapter=other_chapter)
    regent.current_roles = ["regent"]
    regent.save(update_fields=["current_roles"])
    obligation = _open_obligation(chapter, None, TODAY + datetime.timedelta(days=10))

    assert services.can_close_na_vacant(regent, obligation) is False


def test_can_close_na_vacant_true_for_regional_director():
    chapter = ChapterFactory(name="alpha")
    rd = UserFactory(chapter=ChapterFactory(name="beta"))
    chapter.region.directors.add(rd)
    obligation = _open_obligation(chapter, None, TODAY + datetime.timedelta(days=10))

    assert services.can_close_na_vacant(rd, obligation) is True


def test_can_close_na_vacant_false_for_a_plain_member():
    chapter = ChapterFactory()
    member = UserFactory(chapter=chapter)
    obligation = _open_obligation(chapter, None, TODAY + datetime.timedelta(days=10))

    assert services.can_close_na_vacant(member, obligation) is False


def test_close_as_na_vacant_sets_status():
    chapter = ChapterFactory()
    obligation = _open_obligation(chapter, None, TODAY + datetime.timedelta(days=10))

    services.close_as_na_vacant(obligation)

    obligation.refresh_from_db()
    assert obligation.status == "na_vacant"


def test_get_vacant_obligations_for_closer_scoped_to_regents_own_chapter():
    # Explicit distinct names -- ChapterFactory.name is a random pick from a
    # small fixed Greek-letter list (get_or_create'd), so two plain
    # ChapterFactory() calls can collide onto the SAME chapter.
    chapter = ChapterFactory(name="alpha")
    other_chapter = ChapterFactory(name="beta")
    regent = UserFactory(chapter=chapter)
    regent.current_roles = ["regent"]
    regent.save(update_fields=["current_roles"])
    mine = _open_obligation(chapter, None, TODAY + datetime.timedelta(days=10), position_key="regent")
    _open_obligation(other_chapter, None, TODAY + datetime.timedelta(days=10), position_key="regent")

    vacant = list(services.get_vacant_obligations_for_closer(regent))

    assert vacant == [mine]


def test_get_vacant_obligations_for_closer_scoped_to_rds_own_region():
    # Explicit distinct names -- see the collision note above.
    chapter = ChapterFactory(name="alpha")
    other_chapter = ChapterFactory(name="beta")
    rd = UserFactory(chapter=ChapterFactory(name="delta"))
    chapter.region.directors.add(rd)
    mine = _open_obligation(chapter, None, TODAY + datetime.timedelta(days=10), position_key="regent")
    _open_obligation(other_chapter, None, TODAY + datetime.timedelta(days=10), position_key="regent")

    vacant = list(services.get_vacant_obligations_for_closer(rd))

    assert vacant == [mine]


def test_get_vacant_obligations_for_closer_excludes_filled_positions():
    chapter = ChapterFactory()
    regent = UserFactory(chapter=chapter)
    regent.current_roles = ["regent"]
    regent.save(update_fields=["current_roles"])
    filled_officer = UserFactory(chapter=chapter)
    _open_obligation(chapter, filled_officer, TODAY + datetime.timedelta(days=10), position_key="treasurer")

    vacant = list(services.get_vacant_obligations_for_closer(regent))

    assert vacant == []


def test_get_vacant_obligations_for_closer_empty_for_a_plain_member():
    chapter = ChapterFactory()
    member = UserFactory(chapter=chapter)
    _open_obligation(chapter, None, TODAY + datetime.timedelta(days=10), position_key="regent")

    assert list(services.get_vacant_obligations_for_closer(member)) == []


# ---------------------------------------------------------------------------
# can_read_report / get_readable_reports (TRWI-6)
# ---------------------------------------------------------------------------
def _report(chapter, position_key, author, status="submitted", due_date=None):
    due_date = due_date or TODAY + datetime.timedelta(days=10)
    obligation = _open_obligation(chapter, author, due_date, position_key=position_key)
    template, _created = ReportTemplate.objects.get_or_create(
        position_type="CHAPTER_OFFICER", position_key=position_key, defaults={"name": f"{position_key} report"}
    )
    return TransitionReport.objects.create(
        obligation=obligation,
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key=position_key,
        author=author,
        template=template,
        template_version=1,
        status=status,
        # Matches submit_report's own invariant: a "submitted" report always
        # has submitted_at set. Needed so TRWI-11's cycle-bounded queries
        # (which filter on submitted_at) see these fixtures as "current
        # cycle" by default -- individual tests still override this
        # explicitly when they need a specific submission date.
        submitted_at=timezone.now() if status == TransitionReport.Status.submitted.value[0] else None,
    )


def test_get_readable_reports_anonymous_user_sees_nothing():
    assert list(services.get_readable_reports(AnonymousUser())) == []


def test_can_read_report_author_always_reads_their_own_report_even_as_a_draft():
    chapter = ChapterFactory()
    author = UserFactory(chapter=chapter)
    report = _report(chapter, "treasurer", author, status="draft")

    assert services.can_read_report(author, report) is True


def test_can_read_report_denied_for_an_unrelated_plain_member():
    chapter = ChapterFactory(name="alpha")
    other_chapter = ChapterFactory(name="beta")
    report = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    member = UserFactory(chapter=other_chapter)

    assert services.can_read_report(member, report) is False


def test_can_read_report_denied_for_someone_elses_draft():
    # No approval step, but a draft is not "submitted and immediately
    # visible" yet -- even the current position holder can't preview it.
    chapter = ChapterFactory()
    report = _report(chapter, "treasurer", UserFactory(chapter=chapter), status="draft")
    successor = UserFactory(chapter=chapter)
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])

    assert services.can_read_report(successor, report) is False


def test_can_read_report_successor_reads_full_submitted_history_same_position_and_chapter():
    chapter = ChapterFactory()
    report_1 = _report(chapter, "treasurer", UserFactory(chapter=chapter), due_date=TODAY + datetime.timedelta(days=10))
    report_2 = _report(
        chapter, "treasurer", UserFactory(chapter=chapter), due_date=TODAY + datetime.timedelta(days=200)
    )
    successor = UserFactory(chapter=chapter)
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])

    assert services.can_read_report(successor, report_1) is True
    assert services.can_read_report(successor, report_2) is True
    readable = set(services.get_readable_reports(successor).values_list("pk", flat=True))
    assert readable == {report_1.pk, report_2.pk}


def test_can_read_report_denied_for_a_different_position_in_the_same_chapter():
    chapter = ChapterFactory()
    report = _report(chapter, "scribe", UserFactory(chapter=chapter))
    treasurer = UserFactory(chapter=chapter)
    treasurer.current_roles = ["treasurer"]
    treasurer.save(update_fields=["current_roles"])

    assert services.can_read_report(treasurer, report) is False


def test_can_read_report_denied_for_the_same_position_in_a_different_chapter():
    chapter = ChapterFactory(name="alpha")
    other_chapter = ChapterFactory(name="beta")
    report = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    treasurer = UserFactory(chapter=other_chapter)
    treasurer.current_roles = ["treasurer"]
    treasurer.save(update_fields=["current_roles"])

    assert services.can_read_report(treasurer, report) is False


def test_can_read_report_regent_reads_every_position_in_their_own_chapter():
    chapter = ChapterFactory()
    treasurer_report = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    scribe_report = _report(
        chapter, "scribe", UserFactory(chapter=chapter), due_date=TODAY + datetime.timedelta(days=200)
    )
    regent = UserFactory(chapter=chapter)
    regent.current_roles = ["regent"]
    regent.save(update_fields=["current_roles"])

    assert services.can_read_report(regent, treasurer_report) is True
    assert services.can_read_report(regent, scribe_report) is True


def test_can_read_report_regent_denied_for_a_different_chapter():
    chapter = ChapterFactory(name="alpha")
    other_chapter = ChapterFactory(name="beta")
    report = _report(other_chapter, "treasurer", UserFactory(chapter=other_chapter))
    regent = UserFactory(chapter=chapter)
    regent.current_roles = ["regent"]
    regent.save(update_fields=["current_roles"])

    assert services.can_read_report(regent, report) is False


def test_can_read_report_rd_reads_any_position_in_their_own_region():
    chapter = ChapterFactory(name="alpha")
    report = _report(chapter, "scribe", UserFactory(chapter=chapter))
    rd = UserFactory(chapter=ChapterFactory(name="beta"))
    chapter.region.directors.add(rd)

    assert services.can_read_report(rd, report) is True


def test_can_read_report_rd_denied_outside_their_own_region():
    chapter = ChapterFactory(name="alpha")
    report = _report(chapter, "scribe", UserFactory(chapter=chapter))
    rd = UserFactory(chapter=ChapterFactory(name="beta"))
    other_region = RegionFactory()
    other_region.directors.add(rd)

    assert services.can_read_report(rd, report) is False


def test_can_read_report_national_officer_reads_only_their_own_position_nationally():
    # 2026-09 access tightening: a plain NATIONAL_OFFICER role (e.g. CCD) no
    # longer sees every chapter's reports, only ones for the SAME
    # position_key, across chapters -- "reports related to them."
    chapter = ChapterFactory()
    unrelated_report = _report(chapter, "scribe", UserFactory(chapter=chapter))
    ccd_report = _report(ChapterFactory(), "candidate chapter director", UserFactory())
    natoff = UserFactory()
    natoff.current_roles = ["candidate chapter director"]
    natoff.save(update_fields=["current_roles"])
    natoff.groups.add(Group.objects.get_or_create(name="natoff")[0])

    assert services.can_read_report(natoff, unrelated_report) is False
    assert services.can_read_report(natoff, ccd_report) is True


def test_can_read_report_council_member_reads_everything_nationally():
    # NAT_OFFICERS = COUNCIL | NATIONAL_OFFICER, so a Council role also lands
    # in the natoff group -- Council retains full access, unlike a plain
    # National Officer above.
    chapter = ChapterFactory()
    report = _report(chapter, "scribe", UserFactory(chapter=chapter))
    council = UserFactory()
    council.current_roles = ["grand regent"]
    council.save(update_fields=["current_roles"])
    council.groups.add(Group.objects.get_or_create(name="natoff")[0])

    assert services.can_read_report(council, report) is True


def test_can_read_report_admin_reads_everything_nationally():
    chapter = ChapterFactory()
    report = _report(chapter, "scribe", UserFactory(chapter=chapter))
    admin = UserFactory(is_superuser=True)

    assert services.can_read_report(admin, report) is True


def test_can_read_report_denied_when_natoff_functionality_is_hidden():
    # is_national_officer_group respects the "view as member" toggle -- a
    # natoff user previewing as a member is scoped like a plain member here
    # too, same as everywhere else this property is used.
    chapter = ChapterFactory()
    report = _report(chapter, "scribe", UserFactory(chapter=chapter))
    natoff = UserFactory()
    natoff.groups.add(Group.objects.get_or_create(name="natoff")[0])
    UserAlter.objects.create(user=natoff, chapter=natoff.chapter, role=None, hide_natoff=True)

    assert services.can_read_report(natoff, report) is False


def test_get_readable_reports_filters_narrow_what_the_rules_already_allow():
    chapter = ChapterFactory()
    treasurer_report = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    _report(chapter, "scribe", UserFactory(chapter=chapter), due_date=TODAY + datetime.timedelta(days=200))
    regent = UserFactory(chapter=chapter)
    regent.current_roles = ["regent"]
    regent.save(update_fields=["current_roles"])

    readable = services.get_readable_reports(regent, position_key="treasurer")

    assert list(readable) == [treasurer_report]


# ---------------------------------------------------------------------------
# get_handoff_packet / acknowledge_report (TRWI-7)
# ---------------------------------------------------------------------------
def test_get_handoff_packet_shows_predecessor_reports_to_the_successor():
    chapter = ChapterFactory()
    predecessor_report = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    successor = UserFactory(chapter=chapter)
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])

    packet = list(services.get_handoff_packet(successor, chapter, "treasurer"))

    assert packet == [predecessor_report]


def test_get_handoff_packet_excludes_the_viewers_own_report():
    chapter = ChapterFactory()
    successor = UserFactory(chapter=chapter)
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])
    _report(chapter, "treasurer", successor)  # the successor's own (already-submitted) report

    packet = list(services.get_handoff_packet(successor, chapter, "treasurer"))

    assert packet == []


def test_get_handoff_packet_empty_when_not_entitled():
    chapter = ChapterFactory(name="alpha")
    other_chapter = ChapterFactory(name="beta")
    _report(chapter, "treasurer", UserFactory(chapter=chapter))
    member = UserFactory(chapter=other_chapter)

    assert list(services.get_handoff_packet(member, chapter, "treasurer")) == []


def test_acknowledge_report_creates_a_record():
    chapter = ChapterFactory()
    report = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    reader = UserFactory(chapter=chapter)

    services.acknowledge_report(report, reader)

    assert ReportAcknowledgement.objects.filter(report=report, user=reader).exists()


def test_acknowledge_report_is_idempotent():
    chapter = ChapterFactory()
    report = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    reader = UserFactory(chapter=chapter)

    services.acknowledge_report(report, reader)
    services.acknowledge_report(report, reader)

    assert ReportAcknowledgement.objects.filter(report=report, user=reader).count() == 1


# ---------------------------------------------------------------------------
# send_handoff_notices (TRWI-7)
# ---------------------------------------------------------------------------
def test_send_handoff_notices_sends_when_predecessor_reports_exist():
    chapter = ChapterFactory()
    predecessor = UserFactory(chapter=chapter)
    _report(chapter, "treasurer", predecessor)
    successor = UserFactory(chapter=chapter)
    _role_change(chapter, "treasurer", TODAY + datetime.timedelta(days=180), start=TODAY, user=successor)

    sent = services.send_handoff_notices()

    assert sent == 1
    assert len(mail.outbox) == 1
    assert set(mail.outbox[0].to) == set(successor.emails)
    assert HandoffNotice.objects.filter(role_change__user=successor, role_change__role="treasurer").exists()


def test_send_handoff_notices_skips_the_email_but_still_records_when_nothing_to_read():
    chapter = ChapterFactory()
    successor = UserFactory(chapter=chapter)
    _role_change(chapter, "treasurer", TODAY + datetime.timedelta(days=180), start=TODAY, user=successor)

    sent = services.send_handoff_notices()

    assert sent == 0
    assert len(mail.outbox) == 0
    assert HandoffNotice.objects.filter(role_change__user=successor, role_change__role="treasurer").exists()


def test_send_handoff_notices_is_idempotent():
    chapter = ChapterFactory()
    _report(chapter, "treasurer", UserFactory(chapter=chapter))
    successor = UserFactory(chapter=chapter)
    _role_change(chapter, "treasurer", TODAY + datetime.timedelta(days=180), start=TODAY, user=successor)

    services.send_handoff_notices()
    mail.outbox.clear()
    sent_again = services.send_handoff_notices()

    assert sent_again == 0
    assert len(mail.outbox) == 0


def test_send_handoff_notices_skips_a_position_excluded_from_the_feature():
    Config.objects.create(key="TRANSITIONS_COUNCIL_ENABLED", value="off", description="")
    chapter = ChapterFactory()
    _report(chapter, "grand regent", UserFactory(chapter=chapter))
    successor = UserFactory(chapter=chapter)
    _role_change(chapter, "grand regent", TODAY + datetime.timedelta(days=180), start=TODAY, user=successor)

    sent = services.send_handoff_notices()

    assert sent == 0
    assert not HandoffNotice.objects.filter(role_change__user=successor).exists()


def test_send_handoff_notices_ignores_a_role_that_started_outside_the_lookback_window():
    chapter = ChapterFactory()
    _report(chapter, "treasurer", UserFactory(chapter=chapter))
    successor = UserFactory(chapter=chapter)
    # Started well over a year ago (LOOKBACK_GRACE_DAYS) but still "current" --
    # a historical backfill, not a fresh take-office event.
    _role_change(
        chapter,
        "treasurer",
        TODAY + datetime.timedelta(days=180),
        start=TODAY - datetime.timedelta(days=services.LOOKBACK_GRACE_DAYS + 30),
        user=successor,
    )

    sent = services.send_handoff_notices()

    assert sent == 0
    assert not HandoffNotice.objects.filter(role_change__user=successor).exists()


def test_send_handoff_notices_ignores_a_role_that_has_not_started_yet():
    chapter = ChapterFactory()
    _report(chapter, "treasurer", UserFactory(chapter=chapter))
    successor = UserFactory(chapter=chapter)
    _role_change(
        chapter,
        "treasurer",
        TODAY + datetime.timedelta(days=180),
        start=TODAY + datetime.timedelta(days=10),
        user=successor,
    )

    sent = services.send_handoff_notices()

    assert sent == 0
    assert not HandoffNotice.objects.filter(role_change__user=successor).exists()


def test_send_handoff_notices_dry_run_sends_and_writes_nothing():
    chapter = ChapterFactory()
    _report(chapter, "treasurer", UserFactory(chapter=chapter))
    successor = UserFactory(chapter=chapter)
    _role_change(chapter, "treasurer", TODAY + datetime.timedelta(days=180), start=TODAY, user=successor)

    sent = services.send_handoff_notices(dry_run=True)

    assert sent == 1
    assert len(mail.outbox) == 0
    assert not HandoffNotice.objects.filter(role_change__user=successor).exists()


# ---------------------------------------------------------------------------
# get_prior_answers (TRWI-8)
# ---------------------------------------------------------------------------
def _add_prompt(template, prompt_key, label, tag=""):
    TemplatePrompt.objects.get_or_create(
        template=template, prompt_key=prompt_key, defaults={"label": label, "tag": tag}
    )


def test_get_prior_answers_matches_by_prompt_key():
    chapter = ChapterFactory()
    predecessor = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    _add_prompt(predecessor.template, "successes", "Successes?")
    predecessor.answers.create(prompt_key="successes", prompt_label_snapshot="Successes?", value="ask the RD")
    successor = UserFactory(chapter=chapter)
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])
    current_report = _report(
        chapter, "treasurer", successor, status="draft", due_date=TODAY + datetime.timedelta(days=200)
    )

    prior = services.get_prior_answers(successor, current_report)

    assert prior["successes"].value == "ask the RD"


def test_get_prior_answers_uses_the_most_recent_predecessor_only():
    chapter = ChapterFactory()
    oldest = _report(chapter, "treasurer", UserFactory(chapter=chapter), due_date=TODAY + datetime.timedelta(days=10))
    _add_prompt(oldest.template, "successes", "Successes?")
    oldest.answers.create(prompt_key="successes", prompt_label_snapshot="Successes?", value="old advice")
    newest = _report(chapter, "treasurer", UserFactory(chapter=chapter), due_date=TODAY + datetime.timedelta(days=200))
    newest.answers.create(prompt_key="successes", prompt_label_snapshot="Successes?", value="fresh advice")
    successor = UserFactory(chapter=chapter)
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])
    current_report = _report(
        chapter, "treasurer", successor, status="draft", due_date=TODAY + datetime.timedelta(days=400)
    )

    prior = services.get_prior_answers(successor, current_report)

    assert prior["successes"].value == "fresh advice"


def test_get_prior_answers_falls_back_to_label_when_the_key_changed():
    chapter = ChapterFactory()
    predecessor = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    # Predecessor answered under an OLD prompt_key; the current template's
    # prompt for the "same question" (by wording) now uses a different key.
    predecessor.answers.create(prompt_key="old_key", prompt_label_snapshot="Successes?", value="ask the RD")
    _add_prompt(predecessor.template, "successes_v2", "Successes?")
    successor = UserFactory(chapter=chapter)
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])
    current_report = _report(
        chapter, "treasurer", successor, status="draft", due_date=TODAY + datetime.timedelta(days=200)
    )

    prior = services.get_prior_answers(successor, current_report)

    assert prior["successes_v2"].value == "ask the RD"


def test_get_prior_answers_empty_when_not_entitled():
    chapter = ChapterFactory(name="alpha")
    other_chapter = ChapterFactory(name="beta")
    predecessor = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    _add_prompt(predecessor.template, "successes", "Successes?")
    predecessor.answers.create(prompt_key="successes", prompt_label_snapshot="Successes?", value="ask the RD")
    outsider = UserFactory(chapter=other_chapter)
    current_report = _report(
        other_chapter, "treasurer", outsider, status="draft", due_date=TODAY + datetime.timedelta(days=200)
    )

    assert services.get_prior_answers(outsider, current_report) == {}


def test_get_prior_answers_empty_when_no_predecessor_reports():
    chapter = ChapterFactory()
    successor = UserFactory(chapter=chapter)
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])
    current_report = _report(chapter, "treasurer", successor, status="draft")

    assert services.get_prior_answers(successor, current_report) == {}


def test_get_prior_answers_never_shows_the_viewers_own_report():
    chapter = ChapterFactory()
    author = UserFactory(chapter=chapter)
    author.current_roles = ["treasurer"]
    author.save(update_fields=["current_roles"])
    own_older_report = _report(chapter, "treasurer", author, due_date=TODAY + datetime.timedelta(days=10))
    _add_prompt(own_older_report.template, "successes", "Successes?")
    own_older_report.answers.create(prompt_key="successes", prompt_label_snapshot="Successes?", value="my own words")
    current_report = _report(
        chapter, "treasurer", author, status="draft", due_date=TODAY + datetime.timedelta(days=200)
    )

    assert services.get_prior_answers(author, current_report) == {}


def test_get_prior_answers_ignores_prompts_not_on_the_current_template():
    chapter = ChapterFactory()
    predecessor = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    # Answered under a prompt_key that isn't on the current template at all,
    # and whose label doesn't match anything either -- no fallback possible.
    predecessor.answers.create(prompt_key="retired_prompt", prompt_label_snapshot="Old question?", value="obsolete")
    successor = UserFactory(chapter=chapter)
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])
    current_report = _report(
        chapter, "treasurer", successor, status="draft", due_date=TODAY + datetime.timedelta(days=200)
    )

    assert services.get_prior_answers(successor, current_report) == {}


# ---------------------------------------------------------------------------
# Compliance dashboards (TRWI-9)
# ---------------------------------------------------------------------------
@pytest.mark.freeze_time("2026-10-15")
def test_get_cycle_bounds_current_is_the_academic_year_containing_today():
    start, end = services.get_cycle_bounds("current")
    assert start == datetime.date(2026, 7, 1)
    assert end == datetime.date(2027, 7, 1)


@pytest.mark.freeze_time("2026-10-15")
def test_get_cycle_bounds_previous_is_one_academic_year_earlier():
    start, end = services.get_cycle_bounds("previous")
    assert start == datetime.date(2025, 7, 1)
    assert end == datetime.date(2026, 7, 1)


def test_get_cycle_bounds_all_time_returns_none():
    assert services.get_cycle_bounds("all") == (None, None)


@pytest.mark.freeze_time("2026-10-15")
def test_cycle_label_formats_as_a_year_range():
    assert services.cycle_label("current") == "2026-2027"


def test_cycle_label_all_time():
    assert services.cycle_label("all") == "All time"


@pytest.mark.freeze_time("2026-10-15")
def test_chapter_compliance_stats_counts_and_rates():
    chapter = ChapterFactory()
    due = datetime.date(2026, 9, 1)
    submitted_obligation = _open_obligation(
        chapter, UserFactory(chapter=chapter), due, status="submitted", position_key="treasurer"
    )
    template = ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Report")
    report = TransitionReport.objects.create(
        obligation=submitted_obligation,
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key="treasurer",
        author=submitted_obligation.officer,
        template=template,
        template_version=1,
        status="submitted",
    )
    ReportAcknowledgement.objects.create(report=report, user=UserFactory(chapter=chapter))
    _open_obligation(chapter, None, due, status="missed", position_key="scribe")
    _open_obligation(chapter, UserFactory(chapter=chapter), due, status="open", position_key="vice regent")

    stats = services.get_chapter_compliance_stats([chapter])

    assert len(stats) == 1
    row = stats[0]
    assert row.chapter == chapter
    assert row.total == 3
    assert row.submitted == 1
    assert row.missed == 1
    assert row.acknowledged == 1
    assert row.submission_rate == round(1 / 3 * 100, 1)
    assert row.acknowledgment_rate == round(1 / 3 * 100, 1)


def test_chapter_compliance_stats_zero_obligations_rate_is_none():
    chapter = ChapterFactory()

    stats = services.get_chapter_compliance_stats([chapter])

    assert stats[0].total == 0
    assert stats[0].submission_rate is None
    assert stats[0].acknowledgment_rate is None


@pytest.mark.freeze_time("2026-10-15")
def test_chapter_compliance_stats_excludes_obligations_outside_the_current_cycle():
    chapter = ChapterFactory()
    _open_obligation(chapter, UserFactory(chapter=chapter), datetime.date(2026, 9, 1), status="submitted")
    _open_obligation(chapter, UserFactory(chapter=chapter), datetime.date(2025, 9, 1), status="submitted")

    stats = services.get_chapter_compliance_stats([chapter])

    assert stats[0].total == 1


@pytest.mark.freeze_time("2026-10-15")
def test_chapter_compliance_stats_all_time_includes_every_cycle():
    chapter = ChapterFactory()
    _open_obligation(chapter, UserFactory(chapter=chapter), datetime.date(2026, 9, 1), status="submitted")
    _open_obligation(chapter, UserFactory(chapter=chapter), datetime.date(2025, 9, 1), status="submitted")

    stats = services.get_chapter_compliance_stats([chapter], cycle="all")

    assert stats[0].total == 2


@pytest.mark.freeze_time("2026-10-15")
def test_chapter_compliance_stats_filters_by_position():
    chapter = ChapterFactory()
    _open_obligation(chapter, UserFactory(chapter=chapter), datetime.date(2026, 9, 1), position_key="treasurer")
    _open_obligation(chapter, UserFactory(chapter=chapter), datetime.date(2026, 9, 1), position_key="scribe")

    stats = services.get_chapter_compliance_stats([chapter], position_key="treasurer")

    assert stats[0].total == 1


def test_chapter_compliance_stats_query_count_does_not_grow_with_chapter_count():
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    small_chapters = [ChapterFactory(name=name) for name in ["alpha", "beta"]]
    with CaptureQueriesContext(connection) as small:
        services.get_chapter_compliance_stats(small_chapters)

    large_chapters = [ChapterFactory(name=name) for name in ["delta", "epsilon", "eta", "kappa", "mu", "omicron"]]
    with CaptureQueriesContext(connection) as large:
        services.get_chapter_compliance_stats(large_chapters)

    assert len(large) == len(small)


def test_can_view_chapter_dashboard_true_for_own_chapter_officer():
    chapter = ChapterFactory()
    officer = UserFactory(chapter=chapter)
    _role_change(chapter, "treasurer", TODAY + datetime.timedelta(days=180), user=officer)

    assert services.can_view_chapter_dashboard(officer, chapter) is True


def test_can_view_chapter_dashboard_false_for_a_plain_member_of_the_chapter():
    chapter = ChapterFactory()
    member = UserFactory(chapter=chapter)

    assert services.can_view_chapter_dashboard(member, chapter) is False


def test_can_view_chapter_dashboard_false_for_an_officer_of_a_different_chapter():
    chapter = ChapterFactory(name="alpha")
    other_chapter = ChapterFactory(name="beta")
    officer = UserFactory(chapter=other_chapter)
    _role_change(other_chapter, "treasurer", TODAY + datetime.timedelta(days=180), user=officer)

    assert services.can_view_chapter_dashboard(officer, chapter) is False


def test_can_view_chapter_dashboard_true_for_the_chapters_rd():
    chapter = ChapterFactory(name="alpha")
    rd = UserFactory(chapter=ChapterFactory(name="beta"))
    chapter.region.directors.add(rd)

    assert services.can_view_chapter_dashboard(rd, chapter) is True


def test_can_view_chapter_dashboard_true_for_admin():
    chapter = ChapterFactory()
    admin = UserFactory(is_superuser=True)

    assert services.can_view_chapter_dashboard(admin, chapter) is True


def test_can_view_compliance_rates_true_for_rd():
    chapter = ChapterFactory(name="alpha")
    rd = UserFactory(chapter=ChapterFactory(name="beta"))
    chapter.region.directors.add(rd)

    assert services.can_view_compliance_rates(rd) is True


def test_can_view_compliance_rates_true_for_national_officer():
    natoff = UserFactory()
    natoff.groups.add(Group.objects.get_or_create(name="natoff")[0])

    assert services.can_view_compliance_rates(natoff) is True


def test_can_view_compliance_rates_false_for_a_plain_chapter_officer():
    chapter = ChapterFactory()
    officer = UserFactory(chapter=chapter)
    officer.current_roles = ["regent"]
    officer.save(update_fields=["current_roles"])

    assert services.can_view_compliance_rates(officer) is False


def test_get_compliance_rate_chapters_scopes_an_rd_to_their_own_region():
    chapter = ChapterFactory(name="alpha")
    other_chapter = ChapterFactory(name="beta")
    rd = UserFactory(chapter=ChapterFactory(name="delta"))
    chapter.region.directors.add(rd)

    chapters = list(services.get_compliance_rate_chapters(rd))

    assert chapters == [chapter]
    assert other_chapter not in chapters


def test_get_compliance_rate_chapters_national_sees_every_active_chapter():
    chapter = ChapterFactory(name="alpha")
    other_chapter = ChapterFactory(name="beta")
    natoff = UserFactory()
    natoff.groups.add(Group.objects.get_or_create(name="natoff")[0])

    chapters = list(services.get_compliance_rate_chapters(natoff))

    assert chapter in chapters
    assert other_chapter in chapters


def test_get_compliance_rate_chapters_national_can_narrow_to_one_region():
    chapter = ChapterFactory(name="alpha")
    other_chapter = ChapterFactory(name="beta")
    natoff = UserFactory()
    natoff.groups.add(Group.objects.get_or_create(name="natoff")[0])

    chapters = list(services.get_compliance_rate_chapters(natoff, region=chapter.region))

    assert chapters == [chapter]
    assert other_chapter not in chapters


def test_get_compliance_rate_chapters_excludes_inactive_chapters():
    chapter = ChapterFactory(name="alpha")
    inactive_chapter = ChapterFactory(name="beta", active=False)
    natoff = UserFactory()
    natoff.groups.add(Group.objects.get_or_create(name="natoff")[0])

    chapters = list(services.get_compliance_rate_chapters(natoff))

    assert chapter in chapters
    assert inactive_chapter not in chapters


# ---------------------------------------------------------------------------
# Full history -- no retention, archiving, or pinning (TRWI-10)
# ---------------------------------------------------------------------------
def test_get_readable_reports_includes_a_report_submitted_many_years_ago():
    chapter = ChapterFactory()
    old_report = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    ten_years_ago = timezone.now() - datetime.timedelta(days=3650)
    old_report.created = ten_years_ago
    old_report.submitted_at = ten_years_ago
    old_report.save(update_fields=["created", "submitted_at"])
    successor = UserFactory(chapter=chapter)
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])

    assert old_report in services.get_readable_reports(successor)
    assert old_report in list(services.get_handoff_packet(successor, chapter, "treasurer"))


def test_get_handoff_packet_has_no_time_cutoff_and_sorts_purely_by_recency():
    chapter = ChapterFactory()
    old_report = _report(
        chapter, "treasurer", UserFactory(chapter=chapter), due_date=TODAY + datetime.timedelta(days=10)
    )
    old_report.created = timezone.now() - datetime.timedelta(days=3650)
    old_report.save(update_fields=["created"])
    recent_report = _report(
        chapter, "treasurer", UserFactory(chapter=chapter), due_date=TODAY + datetime.timedelta(days=200)
    )
    recent_report.created = timezone.now() - datetime.timedelta(days=30)
    recent_report.save(update_fields=["created"])
    successor = UserFactory(chapter=chapter)
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])

    packet = list(services.get_handoff_packet(successor, chapter, "treasurer"))

    # Most-recent-first, but the decade-old report is still there -- no
    # "only the last N years" cutoff and no pin-based reordering possible.
    assert packet == [recent_report, old_report]


def test_no_transitions_model_has_a_retention_or_pinning_field():
    # Decision 2026-09-04: no retention window/archive job, no pinning --
    # a permanent regression guard against ever reintroducing any of these
    # fields (is_pinned/pinned_by/pinned_reason/archived_at/
    # retention_expires_on), which the ORIGINAL proposal called for but the
    # codebase review round dropped entirely.
    forbidden = {"is_pinned", "pinned_by", "pinned_reason", "archived_at", "retention_expires_on"}
    models = [
        PositionOverride,
        ReportTemplate,
        TemplatePrompt,
        ReportObligation,
        TransitionReport,
        ReportAnswer,
        ReportAttachment,
        ReportAcknowledgement,
        HandoffNotice,
    ]
    for model in models:
        field_names = {field.name for field in model._meta.get_fields()}
        assert field_names.isdisjoint(forbidden), f"{model.__name__} has a forbidden field: {field_names & forbidden}"


# ---------------------------------------------------------------------------
# TRWI-11: tagging (derive_prompt_tags / set_manual_tags)
# ---------------------------------------------------------------------------
def test_derive_prompt_tags_creates_a_tag_for_each_answered_prompts_tag():
    chapter = ChapterFactory()
    report = _report(chapter, "treasurer", UserFactory(chapter=chapter), status="draft")
    _add_prompt(report.template, "successes", "Successes?", tag="success")
    _add_prompt(report.template, "pitfalls", "Pitfalls?", tag="failure")
    report.answers.create(prompt_key="successes", prompt_label_snapshot="Successes?", value="did great")
    # "pitfalls" left unanswered entirely -- no ReportAnswer row at all.

    services.derive_prompt_tags(report)

    assert set(report.tags.values_list("tag", flat=True)) == {"success"}


def test_derive_prompt_tags_ignores_a_blank_answer():
    chapter = ChapterFactory()
    report = _report(chapter, "treasurer", UserFactory(chapter=chapter), status="draft")
    _add_prompt(report.template, "pitfalls", "Pitfalls?", tag="failure")
    report.answers.create(prompt_key="pitfalls", prompt_label_snapshot="Pitfalls?", value="")

    services.derive_prompt_tags(report)

    assert not report.tags.exists()


def test_derive_prompt_tags_ignores_prompts_without_a_tag():
    chapter = ChapterFactory()
    report = _report(chapter, "treasurer", UserFactory(chapter=chapter), status="draft")
    _add_prompt(report.template, "successes", "Successes?")  # tag left blank
    report.answers.create(prompt_key="successes", prompt_label_snapshot="Successes?", value="did great")

    services.derive_prompt_tags(report)

    assert not report.tags.exists()


def test_derive_prompt_tags_dedupes_multiple_prompts_sharing_a_tag():
    chapter = ChapterFactory()
    report = _report(chapter, "treasurer", UserFactory(chapter=chapter), status="draft")
    _add_prompt(report.template, "successes", "Successes?", tag="success")
    _add_prompt(report.template, "wins", "Wins?", tag="success")
    report.answers.create(prompt_key="successes", prompt_label_snapshot="Successes?", value="a")
    report.answers.create(prompt_key="wins", prompt_label_snapshot="Wins?", value="b")

    services.derive_prompt_tags(report)

    assert report.tags.filter(tag="success").count() == 1


def test_derive_prompt_tags_is_fully_re_derived_on_each_call():
    chapter = ChapterFactory()
    report = _report(chapter, "treasurer", UserFactory(chapter=chapter), status="draft")
    _add_prompt(report.template, "successes", "Successes?", tag="success")
    _add_prompt(report.template, "pitfalls", "Pitfalls?", tag="failure")
    report.answers.create(prompt_key="successes", prompt_label_snapshot="Successes?", value="did great")
    services.derive_prompt_tags(report)
    assert set(report.tags.values_list("tag", flat=True)) == {"success"}

    # A later re-submit with a DIFFERENT answer profile -- the stale
    # "success" tag must be gone, not just the new "failure" tag added.
    report.answers.filter(prompt_key="successes").update(value="")
    report.answers.create(prompt_key="pitfalls", prompt_label_snapshot="Pitfalls?", value="missed a deadline")
    services.derive_prompt_tags(report)

    assert set(report.tags.filter(source=ReportTag.Source.prompt.value[0]).values_list("tag", flat=True)) == {"failure"}


def test_derive_prompt_tags_never_touches_manual_tags():
    chapter = ChapterFactory()
    report = _report(chapter, "treasurer", UserFactory(chapter=chapter), status="draft")
    services.set_manual_tags(report, ["risk"])
    _add_prompt(report.template, "successes", "Successes?", tag="success")
    report.answers.create(prompt_key="successes", prompt_label_snapshot="Successes?", value="did great")

    services.derive_prompt_tags(report)

    assert set(report.tags.values_list("tag", "source")) == {("risk", "manual"), ("success", "prompt")}


def test_submit_report_derives_prompt_tags():
    chapter = ChapterFactory()
    report = _report(chapter, "treasurer", UserFactory(chapter=chapter), status="draft")
    _add_prompt(report.template, "successes", "Successes?", tag="success")
    prompt = report.template.prompts.get(prompt_key="successes")

    services.submit_report(report, [(prompt, "did great")])

    assert report.tags.filter(source=ReportTag.Source.prompt.value[0], tag="success").exists()


def test_set_manual_tags_replaces_existing_manual_tags_only():
    chapter = ChapterFactory()
    report = _report(chapter, "treasurer", UserFactory(chapter=chapter), status="draft")
    ReportTag.objects.create(report=report, tag="success", source=ReportTag.Source.prompt.value[0])
    services.set_manual_tags(report, ["risk", "advice"])

    services.set_manual_tags(report, ["risk"])

    assert set(report.tags.values_list("tag", "source")) == {
        ("success", ReportTag.Source.prompt.value[0]),
        ("risk", ReportTag.Source.manual.value[0]),
    }


def test_set_manual_tags_with_empty_list_clears_manual_tags():
    chapter = ChapterFactory()
    report = _report(chapter, "treasurer", UserFactory(chapter=chapter), status="draft")
    services.set_manual_tags(report, ["risk"])

    services.set_manual_tags(report, [])

    assert not report.tags.exists()


# ---------------------------------------------------------------------------
# search_reports (TRWI-11)
# ---------------------------------------------------------------------------
def test_search_reports_only_returns_what_get_readable_reports_allows():
    chapter = ChapterFactory(name="alpha")
    other_chapter = ChapterFactory(name="beta")
    _report(chapter, "treasurer", UserFactory(chapter=chapter))
    member = UserFactory(chapter=other_chapter)

    assert list(services.search_reports(member)) == []


def test_search_reports_no_cross_chapter_leakage_for_a_chapter_scoped_regent():
    chapter = ChapterFactory(name="alpha")
    other_chapter = ChapterFactory(name="beta")
    own_report = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    _report(other_chapter, "treasurer", UserFactory(chapter=other_chapter))
    regent = UserFactory(chapter=chapter)
    regent.current_roles = ["regent"]
    regent.save(update_fields=["current_roles"])

    assert list(services.search_reports(regent)) == [own_report]


def test_search_reports_excludes_drafts_even_the_authors_own():
    chapter = ChapterFactory()
    author = UserFactory(chapter=chapter)
    _report(chapter, "treasurer", author, status="draft")

    assert list(services.search_reports(author)) == []


def test_search_reports_filters_by_query_text():
    chapter = ChapterFactory()
    matching = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    matching.answers.create(prompt_key="successes", prompt_label_snapshot="Successes?", value="we bought a zorblatt")
    matching.save()
    other = _report(chapter, "scribe", UserFactory(chapter=chapter))
    other.answers.create(prompt_key="notes", prompt_label_snapshot="Notes?", value="nothing special")
    other.save()
    national = _council_officer()

    results = list(services.search_reports(national, query="zorblatt"))

    assert results == [matching]


def test_search_reports_finds_a_structured_contact():
    """TRWI-13 proposal: watson's fields= list includes contacts__name/notes,
    so a Contact added via the compose page's formset is findable by full-text
    search the same way answers__value already is (R85/R86's own mechanism).
    """
    chapter = ChapterFactory()
    matching = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    matching.contacts.create(name="Anvie", notes="Domain name renewal trouble")
    matching.save()
    other = _report(chapter, "scribe", UserFactory(chapter=chapter))
    other.save()
    national = _council_officer()

    results = list(services.search_reports(national, query="Anvie"))

    assert results == [matching]


def test_search_reports_empty_query_returns_the_unranked_filtered_queryset():
    chapter = ChapterFactory()
    report = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    national = _council_officer()

    assert list(services.search_reports(national, query="")) == [report]


def test_search_reports_filters_by_position_key():
    chapter = ChapterFactory()
    treasurer_report = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    _report(chapter, "scribe", UserFactory(chapter=chapter))
    national = _council_officer()

    results = list(services.search_reports(national, position_key="treasurer"))

    assert results == [treasurer_report]


def test_search_reports_filters_by_chapter():
    chapter = ChapterFactory(name="alpha")
    other_chapter = ChapterFactory(name="beta")
    report = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    _report(other_chapter, "treasurer", UserFactory(chapter=other_chapter))
    national = _council_officer()

    results = list(services.search_reports(national, chapter=chapter))

    assert results == [report]


def test_search_reports_filters_by_region():
    chapter = ChapterFactory(name="alpha")
    other_chapter = ChapterFactory(name="beta")
    report = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    _report(other_chapter, "treasurer", UserFactory(chapter=other_chapter))
    national = _council_officer()

    results = list(services.search_reports(national, region=chapter.region))

    assert results == [report]


def test_search_reports_filters_by_tag():
    chapter = ChapterFactory()
    tagged = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    services.set_manual_tags(tagged, ["risk"])
    untagged = _report(chapter, "scribe", UserFactory(chapter=chapter))
    national = _council_officer()

    results = list(services.search_reports(national, tag="risk"))

    assert results == [tagged]
    assert untagged not in results


def test_search_reports_filters_by_cycle():
    chapter = ChapterFactory()
    current_report = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    current_report.submitted_at = timezone.now()
    current_report.save(update_fields=["submitted_at"])
    old_report = _report(chapter, "scribe", UserFactory(chapter=chapter))
    old_report.submitted_at = timezone.now() - datetime.timedelta(days=900)
    old_report.save(update_fields=["submitted_at"])
    national = _council_officer()

    results = list(services.search_reports(national, cycle="current"))

    assert results == [current_report]
    assert old_report not in results


def test_search_reports_cycle_all_includes_every_submitted_report_regardless_of_age():
    chapter = ChapterFactory()
    old_report = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    old_report.submitted_at = timezone.now() - datetime.timedelta(days=900)
    old_report.save(update_fields=["submitted_at"])
    national = _council_officer()

    results = list(services.search_reports(national, cycle="all"))

    assert old_report in results


# ---------------------------------------------------------------------------
# get_tag_frequency / get_chapters_with_no_submissions / can_view_trends (TRWI-11)
# ---------------------------------------------------------------------------
def test_get_tag_frequency_counts_reports_per_tag():
    chapter = ChapterFactory()
    report_1 = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    services.set_manual_tags(report_1, ["risk"])
    report_2 = _report(chapter, "scribe", UserFactory(chapter=chapter))
    services.set_manual_tags(report_2, ["risk", "advice"])

    frequency = {row["tag"]: row["count"] for row in services.get_tag_frequency()}

    assert frequency["risk"] == 2
    assert frequency["advice"] == 1


def test_get_tag_frequency_excludes_drafts():
    chapter = ChapterFactory()
    report = _report(chapter, "treasurer", UserFactory(chapter=chapter), status="draft")
    services.set_manual_tags(report, ["risk"])

    frequency = services.get_tag_frequency()

    assert frequency == []


def test_get_tag_frequency_filters_by_position_key():
    chapter = ChapterFactory()
    treasurer_report = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    services.set_manual_tags(treasurer_report, ["risk"])
    scribe_report = _report(chapter, "scribe", UserFactory(chapter=chapter))
    services.set_manual_tags(scribe_report, ["advice"])

    frequency = {row["tag"]: row["count"] for row in services.get_tag_frequency(position_key="treasurer")}

    assert frequency == {"risk": 1}


def test_get_tag_frequency_filters_by_region():
    chapter = ChapterFactory(name="alpha")
    other_chapter = ChapterFactory(name="beta")
    report = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    services.set_manual_tags(report, ["risk"])
    other_report = _report(other_chapter, "treasurer", UserFactory(chapter=other_chapter))
    services.set_manual_tags(other_report, ["advice"])

    frequency = {row["tag"]: row["count"] for row in services.get_tag_frequency(region=chapter.region)}

    assert frequency == {"risk": 1}


def test_get_tag_frequency_filters_by_cycle():
    chapter = ChapterFactory()
    old_report = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    old_report.submitted_at = timezone.now() - datetime.timedelta(days=900)
    old_report.save(update_fields=["submitted_at"])
    services.set_manual_tags(old_report, ["risk"])

    frequency = services.get_tag_frequency(cycle="current")

    assert frequency == []
    assert services.get_tag_frequency(cycle="all") != []


def test_get_chapters_with_no_submissions_excludes_a_chapter_with_a_submission():
    chapter_with_report = ChapterFactory(name="alpha")
    chapter_without_report = ChapterFactory(name="beta")
    _report(chapter_with_report, "treasurer", UserFactory(chapter=chapter_with_report))

    chapters = list(services.get_chapters_with_no_submissions())

    assert chapter_without_report in chapters
    assert chapter_with_report not in chapters


def test_get_chapters_with_no_submissions_excludes_inactive_chapters():
    ChapterFactory(name="alpha", active=False)

    chapters = list(services.get_chapters_with_no_submissions())

    assert chapters == []


def test_get_chapters_with_no_submissions_a_draft_does_not_count_as_a_submission():
    chapter = ChapterFactory()
    _report(chapter, "treasurer", UserFactory(chapter=chapter), status="draft")

    chapters = list(services.get_chapters_with_no_submissions())

    assert chapter in chapters


def test_get_chapters_with_no_submissions_filters_by_region():
    chapter = ChapterFactory(name="alpha")
    other_chapter = ChapterFactory(name="beta")

    chapters = list(services.get_chapters_with_no_submissions(region=chapter.region))

    assert chapters == [chapter]
    assert other_chapter not in chapters


def test_can_view_trends_true_for_national_officer_and_admin():
    natoff = UserFactory()
    natoff.groups.add(Group.objects.get_or_create(name="natoff")[0])
    admin = UserFactory(is_superuser=True)

    assert services.can_view_trends(natoff) is True
    assert services.can_view_trends(admin) is True


def test_can_view_trends_false_for_rd_and_plain_chapter_officer():
    chapter = ChapterFactory()
    rd = UserFactory(chapter=ChapterFactory())
    chapter.region.directors.add(rd)
    officer = UserFactory(chapter=chapter)
    officer.current_roles = ["treasurer"]
    officer.save(update_fields=["current_roles"])

    assert services.can_view_trends(rd) is False
    assert services.can_view_trends(officer) is False


def test_can_view_trends_false_for_anonymous_user():
    assert services.can_view_trends(AnonymousUser()) is False
