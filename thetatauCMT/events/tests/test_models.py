import datetime

import factory
import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.utils.text import slugify
from faker import Faker

from core.models import user_is_national_officer
from thetatauCMT.events.models import Event
from thetatauCMT.events.tests.factories import EventFactory
from thetatauCMT.scores.models import ScoreType

fake = Faker()


def _evt_score_type():
    return ScoreType.objects.filter(type="Evt").first()


def _national_officer(user_factory):
    """A user who reliably qualifies as a National Officer (via the natoff group)."""
    user = user_factory.create()
    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    return user


def _distinct_chapter(chapter_factory, other_than):
    """A chapter guaranteed to differ from ``other_than`` (avoids the small
    ChapterFactory greek-name pool colliding with the event's own chapter)."""
    from thetatauCMT.chapters.models import GREEK_ABR

    for name in GREEK_ABR.values():
        if name != other_than.name:
            return chapter_factory.create(name=name)
    raise RuntimeError("No distinct chapter name available")


@pytest.mark.django_db
def test_event_factory(event_factory):
    assert event_factory == EventFactory


@pytest.mark.django_db
def test_event_instance(event):
    assert isinstance(event, Event)


@pytest.mark.django_db
@pytest.mark.parametrize("event__name,event__date", [("Very Special event", datetime.date(2016, 10, 1))])
def test_event_str(event):
    assert str(event) == "Very Special event on 2016-10-01"


@pytest.mark.django_db
@pytest.mark.parametrize("event__name,event__date", [("Very Special event", datetime.date(2016, 10, 1))])
def test_get_absolute_url(event):
    from django.urls import reverse

    url = event.get_absolute_url()
    assert isinstance(url, str)
    assert url == reverse(
        "events:detail",
        kwargs={
            "year": 2016,
            "month": 10,
            "day": 1,
            "slug": slugify("Very Special event"),
        },
    )


@pytest.mark.django_db
@pytest.mark.parametrize("event__name,event__date", [("Very Special event", datetime.date(2016, 10, 1))])
def test_get_update_url_is_date_slug_based(event):
    from django.urls import reverse

    url = event.get_update_url()
    assert isinstance(url, str)
    assert url.endswith("/edit/")
    assert url == reverse(
        "events:update",
        kwargs={
            "year": 2016,
            "month": 10,
            "day": 1,
            "event_slug": slugify("Very Special event"),
        },
    )


@pytest.mark.django_db
def test_chapter_events(chapter, event_factory):
    expected_events = event_factory.create_batch(10, chapter=chapter)
    actual_events = Event.chapter_events(chapter)
    assert set(list(actual_events)) == set(expected_events)


@pytest.mark.django_db
@pytest.mark.freeze_time("2026-04-15 12:00:00")
def test_calculate_meeting_attendance(chapter, event_factory, user_status_change_factory):
    score_type = ScoreType.objects.get(name="Attendance at meetings")
    user_status_change_factory.create_batch(
        20,
        status="active",
        user__chapter=chapter,
        start=factory.Faker("date_between", start_date="-1y", end_date="-16d"),
        end=factory.Faker("date_between", start_date="today", end_date="+1y"),
    )
    event_factory.create_batch(
        10,
        calculate_score=False,
        type=score_type,
        members=5,
        chapter=chapter,
        date=factory.Faker("date_between", start_date="-15d", end_date="-5d"),
    )
    date = fake.date_between(start_date="-15d", end_date="-5d")
    actual_score = Event.calculate_meeting_attendance(chapter, date)
    # 10 events at 25% attendance each eval "15*MEETINGS"
    # avg_attendance = 0.25, score = 15*0.25 = 3.75, event_score = round(3.75/10, 2) = 0.38
    assert actual_score == 0.38


@pytest.mark.django_db
def test_calculate_meeting_attendance_no_events(chapter, user_status_change_factory):
    user_status_change_factory.create_batch(
        20,
        status="active",
        user__chapter=chapter,
        start=factory.Faker("date_between", start_date="-1y", end_date="today"),
        end=factory.Faker("date_between", start_date="today", end_date="+1y"),
    )
    date = fake.date_between(start_date="-15d", end_date="-5d")
    actual_score = Event.calculate_meeting_attendance(chapter, date)
    # No events, should be 0 score
    assert actual_score == 0


# ===========================================================================
# WI-1 — Events model extensions
# ===========================================================================


# --- national flag permission enforcement (model-level clean check) --------


@pytest.mark.django_db
def test_national_flag_permission_enforcement_blocks_non_national_officer(event_factory, user_factory):
    """A non-National-Officer cannot set is_national=True (model-level clean)."""
    regular_user = user_factory.create()
    assert not user_is_national_officer(regular_user)
    event = event_factory.create(is_national=False)
    event.is_national = True
    event._acting_user = regular_user
    with pytest.raises(ValidationError) as excinfo:
        event.clean()
    assert "is_national" in excinfo.value.message_dict


@pytest.mark.django_db
def test_national_flag_permission_enforcement_allows_national_officer(event_factory, user_factory):
    """A National Officer may set is_national=True without a clean error."""
    natoff = _national_officer(user_factory)
    assert user_is_national_officer(natoff)
    event = event_factory.create(is_national=False)
    event.is_national = True
    event._acting_user = natoff
    # Should not raise for the is_national rule.
    event.clean()
    assert event.is_national is True


@pytest.mark.django_db
def test_national_flag_permission_enforcement_form_rejects_non_officer(user_factory):
    """The form-level validation also rejects is_national for non-officers."""
    from thetatauCMT.events.forms import EventForm

    regular_user = user_factory.create()
    score_type = _evt_score_type()
    form = EventForm(
        data={
            "name": "Nat Event",
            "date": datetime.date.today().isoformat(),
            "type": score_type.pk,
            "description": "desc",
            "members": 1,
            "pledges": 0,
            "alumni": 0,
            "guests": 0,
            "duration": 1,
            "miles": 0,
            "raised": "0.00",
            "is_public": True,
            "is_national": True,
        },
        request_user=regular_user,
    )
    # Field is stripped for non-national officers, so is_national can never be set.
    assert "is_national" not in form.fields


@pytest.mark.django_db
def test_national_flag_form_available_and_valid_for_national_officer(user_factory):
    from thetatauCMT.events.forms import EventForm

    natoff = _national_officer(user_factory)
    score_type = _evt_score_type()
    form = EventForm(
        data={
            "name": "Nat Event",
            "date": datetime.date.today().isoformat(),
            "type": score_type.pk,
            "description": "desc",
            "members": 1,
            "pledges": 0,
            "alumni": 0,
            "guests": 0,
            "duration": 1,
            "miles": 0,
            "raised": "0.00",
            "is_public": True,
            "is_national": True,
        },
        request_user=natoff,
    )
    assert "is_national" in form.fields
    assert form.is_valid(), form.errors
    assert form.cleaned_data["is_national"] is True


# --- sub-event parent linkage ----------------------------------------------


@pytest.mark.django_db
def test_sub_event_parent_linkage(chapter, event_factory):
    parent = event_factory.create(chapter=chapter)
    child = event_factory.create(chapter=chapter, parent_event=parent)
    child.refresh_from_db()
    assert child.parent_event_id == parent.pk
    assert child.is_sub_event is True
    assert parent.is_sub_event is False
    assert child in parent.sub_events.all()
    # Manager helpers
    assert child in Event.objects.sub_events()
    assert parent not in Event.objects.sub_events()
    assert parent in Event.objects.top_level()
    assert child not in Event.objects.top_level()


@pytest.mark.django_db
def test_sub_event_inherits_region_from_parent(chapter, region, event_factory):
    parent = event_factory.create(chapter=chapter, region=region)
    # Child created without an explicit region inherits the parent's region.
    child = event_factory.create(chapter=chapter, parent_event=parent, region=None)
    child.refresh_from_db()
    assert child.region_id == region.pk
    assert child.effective_region == region


@pytest.mark.django_db
def test_sub_event_region_override_not_replaced(chapter, region, region_factory, event_factory):
    other_region = region_factory.create()
    parent = event_factory.create(chapter=chapter, region=region)
    child = event_factory.create(chapter=chapter, parent_event=parent, region=other_region)
    child.refresh_from_db()
    assert child.region_id == other_region.pk


# --- public flag defaults ---------------------------------------------------


@pytest.mark.django_db
def test_public_flag_defaults_non_public_is_approved():
    status = Event.default_approval_status(is_public=False, created_by_national_officer=False)
    assert status == Event.ApprovalStatus.APPROVED


@pytest.mark.django_db
def test_public_flag_defaults_chapter_public_is_pending():
    status = Event.default_approval_status(is_public=True, created_by_national_officer=False)
    assert status == Event.ApprovalStatus.PENDING


@pytest.mark.django_db
def test_public_flag_defaults_national_public_auto_approved_by_default():
    status = Event.default_approval_status(is_public=True, created_by_national_officer=True)
    assert status == Event.ApprovalStatus.APPROVED


@pytest.mark.django_db
@override_settings(EVENTS_AUTO_APPROVE_NATIONAL_PUBLIC=False)
def test_public_flag_defaults_national_public_pending_when_auto_approve_off():
    status = Event.default_approval_status(is_public=True, created_by_national_officer=True)
    assert status == Event.ApprovalStatus.PENDING


# --- manager helpers --------------------------------------------------------


@pytest.mark.django_db
def test_manager_national_and_public_helpers(chapter, event_factory):
    national = event_factory.create(chapter=chapter, is_national=True)
    public = event_factory.create(chapter=chapter, is_public=True)
    plain = event_factory.create(chapter=chapter)
    assert national in Event.objects.national()
    assert public not in Event.objects.national()
    assert public in Event.objects.public()
    assert plain not in Event.objects.public()


@pytest.mark.django_db
def test_manager_cross_chapter_visible_and_visible_to_chapter(chapter, chapter_factory, event_factory):
    other_chapter = _distinct_chapter(chapter_factory, chapter)
    approved_public = event_factory.create(
        chapter=chapter, is_public=True, approval_status=Event.ApprovalStatus.APPROVED
    )
    pending_public = event_factory.create(chapter=chapter, is_public=True, approval_status=Event.ApprovalStatus.PENDING)
    private = event_factory.create(chapter=chapter, is_public=False)

    cross = Event.objects.cross_chapter_visible()
    assert approved_public in cross
    assert pending_public not in cross
    assert private not in cross

    visible_other = Event.objects.visible_to_chapter(other_chapter)
    assert approved_public in visible_other
    assert pending_public not in visible_other
    assert private not in visible_other

    visible_own = Event.objects.visible_to_chapter(chapter)
    assert approved_public in visible_own
    assert pending_public in visible_own
    assert private in visible_own


# ===========================================================================
# WI-2 — Approval workflow (model methods)
# ===========================================================================


@pytest.mark.django_db
def test_event_approve_records_reviewer_and_visibility(chapter, event_factory, user_factory):
    natoff = _national_officer(user_factory)
    event = event_factory.create(chapter=chapter, is_public=True, approval_status=Event.ApprovalStatus.PENDING)
    assert event.is_cross_chapter_visible is False
    event.approve(reviewer=natoff)
    event.refresh_from_db()
    assert event.approval_status == Event.ApprovalStatus.APPROVED
    assert event.reviewed_by_id == natoff.pk
    assert event.reviewed_at is not None
    assert event.is_cross_chapter_visible is True


@pytest.mark.django_db
def test_event_reject_persists_reason_and_hides(chapter, event_factory, user_factory):
    natoff = _national_officer(user_factory)
    event = event_factory.create(chapter=chapter, is_public=True, approval_status=Event.ApprovalStatus.PENDING)
    event.reject(reviewer=natoff, reason="Duplicate of regional event")
    event.refresh_from_db()
    assert event.approval_status == Event.ApprovalStatus.REJECTED
    assert event.rejection_reason == "Duplicate of regional event"
    assert event.reviewed_by_id == natoff.pk
    assert event.is_cross_chapter_visible is False


# ===========================================================================
# National events not tied to a chapter; forced public; auto-approved
# ===========================================================================


@pytest.mark.django_db
def test_national_event_can_have_no_chapter(event_factory):
    """National events are org-wide and may be saved without a chapter."""
    event = event_factory.create(is_national=True, chapter=None)
    event.refresh_from_db()
    assert event.chapter_id is None
    assert event in Event.objects.national()


@pytest.mark.django_db
def test_national_event_forced_public_on_save(event_factory):
    """Saving a national event always marks it public, even if unset."""
    event = event_factory.create(is_national=True, is_public=False, chapter=None)
    event.refresh_from_db()
    assert event.is_public is True


@pytest.mark.django_db
def test_default_approval_status_national_is_approved():
    status = Event.default_approval_status(is_public=False, created_by_national_officer=False, is_national=True)
    assert status == Event.ApprovalStatus.APPROVED


@pytest.mark.django_db
def test_national_sub_event_parent_lookup_is_national(chapter, event_factory):
    """A national event's parent lookup is scoped to national events, not chapters."""
    national_parent = event_factory.create(is_national=True, chapter=None)
    national_child = event_factory.create(is_national=True, chapter=None, parent_event=national_parent)
    national_child.refresh_from_db()
    assert national_child.parent_event_id == national_parent.pk
    assert national_child in Event.objects.national().sub_events()


# ===========================================================================
# Filters: is_public (always) and is_national (natoff)
# ===========================================================================


@pytest.mark.django_db
def test_event_filter_is_public(chapter, event_factory):
    from thetatauCMT.events.filters import EventListFilter

    public = event_factory.create(chapter=chapter, is_public=True)
    private = event_factory.create(chapter=chapter, is_public=False)
    filtered = EventListFilter({"is_public": "True"}, queryset=Event.objects.all())
    assert public in filtered.qs
    assert private not in filtered.qs


@pytest.mark.django_db
def test_event_filter_is_national(chapter, event_factory):
    from thetatauCMT.events.filters import EventListFilter

    national = event_factory.create(is_national=True, chapter=None)
    regular = event_factory.create(chapter=chapter)
    filtered = EventListFilter({"is_national": "True"}, queryset=Event.objects.all(), natoff=True)
    assert national in filtered.qs
    assert regular not in filtered.qs


# ===========================================================================
# Rejected public events cannot be made public again
# ===========================================================================


@pytest.mark.django_db
def test_rejected_event_public_field_disabled_in_form(chapter, event_factory):
    from thetatauCMT.events.forms import EventForm

    event = event_factory.create(chapter=chapter, is_public=True, approval_status=Event.ApprovalStatus.REJECTED)
    form = EventForm(instance=event, request_user=None)
    assert form.fields["is_public"].disabled is True


@pytest.mark.django_db
def test_rejected_event_public_flag_locked_in_clean(chapter, event_factory, user_factory):
    from thetatauCMT.events.forms import EventForm

    officer = user_factory.create()
    event = event_factory.create(chapter=chapter, is_public=True, approval_status=Event.ApprovalStatus.REJECTED)
    # Even if is_public is somehow submitted, clean() keeps the stored value.
    form = EventForm(instance=event, request_user=officer)
    form.cleaned_data = {"is_public": False}
    result = form.clean()
    assert result["is_public"] == event.is_public


# ===========================================================================
# "Open to Other Chapters" relabel (form / table / filter)
# ===========================================================================


@pytest.mark.django_db
def test_event_form_public_label(user_factory):
    from thetatauCMT.events.forms import EventForm

    form = EventForm(request_user=user_factory.create())
    assert form.fields["is_public"].label == "Open to Other Chapters"


def test_event_table_public_column_label():
    from thetatauCMT.events.tables import EventTable

    assert EventTable.base_columns["is_public"].verbose_name == "Open to Other Chapters"


@pytest.mark.django_db
def test_event_table_name_links_to_detail(event):
    from thetatauCMT.events.tables import EventTable

    table = EventTable(data=[event])
    cell = table.rows[0].get_cell("name")
    # The event name links to the detail page, not the edit page.
    assert f'href="{event.get_absolute_url()}"' in cell
    assert event.get_update_url() not in cell


def test_event_filter_public_label():
    from thetatauCMT.events.filters import EventListFilter

    filtered = EventListFilter()
    assert filtered.filters["is_public"].label == "Open to Other Chapters"


# ===========================================================================
# Admin "view on site" uses a host-relative URL (localhost when local)
# ===========================================================================


@pytest.mark.django_db
def test_admin_view_on_site_returns_relative_url(chapter, event_factory):
    from django.contrib.admin.sites import AdminSite

    from thetatauCMT.events.admin import EventAdmin

    event = event_factory.create(chapter=chapter)
    admin_obj = EventAdmin(Event, AdminSite())
    url = admin_obj.view_on_site(event)
    assert url == event.get_absolute_url()
    assert url.startswith("/")
