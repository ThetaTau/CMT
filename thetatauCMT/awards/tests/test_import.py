import csv
import datetime
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from thetatauCMT.awards.importer import ingest_award_csv
from thetatauCMT.awards.models import AwardCycle, AwardGrant, AwardImportMatchQueueItem
from thetatauCMT.awards.tests._helpers import sign_rmp as _sign_rmp
from thetatauCMT.awards.tests.factories import AwardTypeFactory
from thetatauCMT.chapters.models import GREEK_ABR
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.regions.tests.factories import RegionFactory
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

_NAMES = list(GREEK_ABR.values())


def _csv(header, *rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def _importer():
    return UserFactory()


def _superuser():
    user = UserFactory(is_superuser=True)
    _sign_rmp(user)
    return user


def _staff_non_superuser():
    # A national officer / admin-panel user (is_staff) must STILL be denied.
    user = UserFactory(is_staff=True)
    _sign_rmp(user)
    return user


# ===========================================================================
# Valid rows create backdated import grants
# ===========================================================================
def test_valid_member_row_creates_backdated_import_grant():
    award = AwardTypeFactory(name="Legacy Service Award", level="member")
    member = UserFactory(status="active")
    data = _csv(
        ["award", "member_id", "cycle", "effective_date"],
        ["Legacy Service Award", str(member.pk), "2015", "2015-05-01"],
    )
    result = ingest_award_csv(data, _importer())
    assert result.imported == 1
    grant = AwardGrant.objects.get(award_type=award, recipient_member=member)
    assert grant.source == AwardGrant.Source.IMPORT
    assert grant.effective_date == datetime.date(2015, 5, 1)
    assert grant.cycle.name == "2015"


def test_member_matched_by_email():
    award = AwardTypeFactory(name="Email Match Award", level="member")
    member = UserFactory(status="active")
    data = _csv(["award", "email", "cycle"], ["Email Match Award", member.email, "2016"])
    result = ingest_award_csv(data, _importer())
    assert result.imported == 1
    assert AwardGrant.objects.filter(award_type=award, recipient_member=member, source="import").exists()


def test_missing_cycle_is_created_as_year():
    AwardTypeFactory(name="Create Cycle Award", level="member")
    member = UserFactory(status="active")
    assert not AwardCycle.objects.filter(name="2009").exists()
    ingest_award_csv(_csv(["award", "member_id", "cycle"], ["Create Cycle Award", str(member.pk), "2009"]), _importer())
    cycle = AwardCycle.objects.get(name="2009")
    assert cycle.period_type == AwardCycle.PeriodType.YEAR
    assert cycle.start_date == datetime.date(2009, 1, 1)
    assert cycle.end_date == datetime.date(2009, 12, 31)


def test_award_not_found_is_error_no_grant():
    UserFactory(status="active")
    data = _csv(["award", "email", "cycle"], ["No Such Award", "who@example.com", "2015"])
    result = ingest_award_csv(data, _importer())
    assert result.imported == 0
    assert result.skipped == 1
    assert result.errors
    assert not AwardGrant.objects.exists()


# ===========================================================================
# Chapter / region matching
# ===========================================================================
def test_chapter_recipient_exact_match():
    chapter = ChapterFactory(name=_NAMES[0])
    award = AwardTypeFactory(name="Chapter of the Year", level="chapter")
    data = _csv(["award", "chapter", "cycle"], ["Chapter of the Year", chapter.name, "2018"])
    result = ingest_award_csv(data, _importer())
    assert result.imported == 1
    assert AwardGrant.objects.filter(award_type=award, recipient_chapter=chapter, source="import").exists()


def test_region_recipient_exact_match():
    region = RegionFactory(name="Cascadia")
    award = AwardTypeFactory(name="Region Excellence", level="region")
    data = _csv(["award", "region", "cycle"], ["Region Excellence", "Cascadia", "2019"])
    result = ingest_award_csv(data, _importer())
    assert result.imported == 1
    assert AwardGrant.objects.filter(award_type=award, recipient_region=region, source="import").exists()


# ===========================================================================
# Low-confidence -> match queue
# ===========================================================================
def test_low_confidence_member_routes_to_queue():
    award = AwardTypeFactory(name="Fuzzy Member Award", level="member")
    member = UserFactory(name="Zachariah Longbottom", status="active")
    # A partial name, no id/email/chapter -> below the auto-accept threshold.
    data = _csv(["award", "name", "cycle"], ["Fuzzy Member Award", "Zachariah", "2021"])
    result = ingest_award_csv(data, _importer())
    assert result.queued == 1
    assert not AwardGrant.objects.filter(award_type=award).exists()
    item = AwardImportMatchQueueItem.objects.get(status="pending")
    assert item.recipient_kind == "member"
    assert item.award_type == award
    assert any(candidate["id"] == member.pk for candidate in item.candidate_matches)


def test_resolve_queue_item_creates_import_grant():
    award = AwardTypeFactory(name="Resolve Me Award", level="member")
    member = UserFactory(name="Beatrix Kiddo", status="active")
    admin = _importer()
    ingest_award_csv(_csv(["award", "name", "cycle"], ["Resolve Me Award", "Beatrix", "2021"]), admin)
    item = AwardImportMatchQueueItem.objects.get(status="pending")
    grant = item.resolve_to(member, admin)
    assert grant.source == AwardGrant.Source.IMPORT
    assert grant.award_type == award
    assert grant.recipient_member == member
    item.refresh_from_db()
    assert item.status == AwardImportMatchQueueItem.Status.RESOLVED
    assert item.resolved_grant_id == grant.pk
    assert item.resolved_recipient_member_id == member.pk


def test_skip_queue_item_creates_no_grant():
    award = AwardTypeFactory(name="Skip Me Award", level="member")
    UserFactory(name="Vincent Vega", status="active")
    admin = _importer()
    ingest_award_csv(_csv(["award", "name", "cycle"], ["Skip Me Award", "Vincent", "2021"]), admin)
    item = AwardImportMatchQueueItem.objects.get(status="pending")
    item.skip(admin, note="no match")
    item.refresh_from_db()
    assert item.status == AwardImportMatchQueueItem.Status.SKIPPED
    assert not AwardGrant.objects.filter(award_type=award).exists()


# ===========================================================================
# Idempotent re-import
# ===========================================================================
def test_idempotent_reimport_no_duplicate_grants():
    award = AwardTypeFactory(name="Idempotent Award", level="member")
    member = UserFactory(status="active")
    data = _csv(["award", "member_id", "cycle"], ["Idempotent Award", str(member.pk), "2012"])
    admin = _importer()
    first = ingest_award_csv(data, admin)
    second = ingest_award_csv(data, admin)
    assert first.imported == 1
    assert second.imported == 0
    assert second.duplicates == 1
    assert AwardGrant.objects.filter(award_type=award, recipient_member=member).count() == 1


def test_reimport_after_resolution_is_skipped():
    award = AwardTypeFactory(name="Reimport Award", level="member")
    member = UserFactory(name="Mia Wallace", status="active")
    data = _csv(["award", "name", "cycle"], ["Reimport Award", "Mia", "2013"])
    admin = _importer()
    ingest_award_csv(data, admin)
    AwardImportMatchQueueItem.objects.get(status="pending").resolve_to(member, admin)
    result = ingest_award_csv(data, admin)
    assert result.imported == 0
    assert result.skipped == 1
    assert AwardImportMatchQueueItem.objects.filter(status="pending").count() == 0
    assert AwardGrant.objects.filter(award_type=award).count() == 1


# ===========================================================================
# Admin-only web views
# ===========================================================================
@override_settings(DEBUG=True)  # superusers bypass RequireSuperuser2FAMiddleware only when DEBUG
def test_import_upload_superuser_only(client):
    url = reverse("awards:import_upload")
    assert client.get(url).status_code == 302  # anonymous -> login
    client.force_login(_staff_non_superuser())
    assert client.get(url).status_code == 302  # authed non-superuser (even staff/natoff) -> home
    client.force_login(_superuser())
    assert client.get(url).status_code == 200


@override_settings(DEBUG=True)
def test_import_queue_superuser_only(client):
    url = reverse("awards:import_queue")
    assert client.get(url).status_code == 302
    client.force_login(_staff_non_superuser())
    assert client.get(url).status_code == 302  # even staff/natoff denied
    client.force_login(_superuser())
    assert client.get(url).status_code == 200


@override_settings(DEBUG=True)
def test_import_upload_ingests_csv(client):
    award = AwardTypeFactory(name="Web Import Award", level="member")
    member = UserFactory(status="active")
    csv_bytes = _csv(
        ["award", "member_id", "cycle", "effective_date"],
        ["Web Import Award", str(member.pk), "2016", "2016-03-03"],
    )
    client.force_login(_superuser())
    upload = SimpleUploadedFile("winners.csv", csv_bytes, content_type="text/csv")
    response = client.post(reverse("awards:import_upload"), {"file": upload})
    assert response.status_code == 302  # redirect to queue
    grant = AwardGrant.objects.get(award_type=award, recipient_member=member)
    assert grant.source == AwardGrant.Source.IMPORT
    assert grant.effective_date == datetime.date(2016, 3, 3)


@override_settings(DEBUG=True)
def test_resolve_view_creates_grant(client):
    award = AwardTypeFactory(name="Web Fuzzy Award", level="member")
    member = UserFactory(name="Quentin Tarantino", status="active")
    admin = _superuser()
    ingest_award_csv(_csv(["award", "name", "cycle"], ["Web Fuzzy Award", "Quentin", "2017"]), admin)
    item = AwardImportMatchQueueItem.objects.get(status="pending")
    client.force_login(admin)
    response = client.post(
        reverse("awards:import_resolve"),
        {"item": item.pk, "recipient_id": member.pk, "action": "resolve"},
    )
    assert response.status_code == 302
    item.refresh_from_db()
    assert item.status == AwardImportMatchQueueItem.Status.RESOLVED
    assert AwardGrant.objects.filter(award_type=award, recipient_member=member, source="import").exists()
