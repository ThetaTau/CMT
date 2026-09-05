import datetime

import pytest
from django.core import mail

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.configs.models import Config
from thetatauCMT.regions.tests.factories import RegionFactory
from thetatauCMT.users.models import UserRoleChange
from thetatauCMT.users.tests.factories import UserFactory

from .. import services
from ..models import PositionOverride, ReportObligation, ReportTemplate

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
