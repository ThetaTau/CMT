from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.urls import reverse

from thetatauCMT.awards.certificates import (
    CERTIFICATE_TEMPLATE,
    certificate_context,
    generate_certificate,
    store_uploaded_artifact,
)
from thetatauCMT.awards.models import GrantArtifact
from thetatauCMT.awards.services import direct_grant
from thetatauCMT.awards.tests._helpers import sign_rmp as _sign_rmp
from thetatauCMT.awards.tests.factories import AwardCycleFactory, AwardGrantFactory, AwardTypeFactory
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

_FAKE_PDF = b"%PDF-1.4 fake certificate"


def _cleanup(grant):
    for artifact in grant.artifacts.all():
        artifact.file.delete(save=False)


def _view_user():
    user = UserFactory()
    user.groups.add(Group.objects.get_or_create(name="natoff")[0])
    _sign_rmp(user)
    return user


# ---------------------------------------------------------------------------
# Acceptance: auto-generate produces a certificate with correct merge data
# ---------------------------------------------------------------------------
def test_certificate_template_merges_recipient_award_and_cycle():
    grant = AwardGrantFactory()
    html = render_to_string(CERTIFICATE_TEMPLATE, certificate_context(grant))
    assert grant.recipient_display in html
    assert grant.award_type.name in html
    assert grant.cycle.name in html
    # The award period is the only time reference; the grant date is never shown.
    assert "Effective" not in html


def test_generate_certificate_creates_generated_artifact():
    grant = AwardGrantFactory()
    with mock.patch("thetatauCMT.awards.certificates.render_to_pdf", return_value=_FAKE_PDF):
        artifact = generate_certificate(grant, created_by=grant.granted_by)
    assert artifact.pk is not None
    assert artifact.artifact_type == GrantArtifact.ArtifactType.GENERATED
    assert artifact.grant == grant
    assert artifact.generated_at is not None
    assert artifact.created_by == grant.granted_by
    assert artifact.file.name.endswith(".pdf")
    with artifact.file.open("rb") as handle:
        assert handle.read().startswith(b"%PDF")
    _cleanup(grant)


# ---------------------------------------------------------------------------
# Acceptance: manual upload stored + linked to grant
# ---------------------------------------------------------------------------
def test_store_uploaded_artifact_linked_to_grant():
    grant = AwardGrantFactory()
    upload = SimpleUploadedFile("letter.pdf", b"%PDF uploaded", content_type="application/pdf")
    artifact = store_uploaded_artifact(grant, upload, created_by=grant.granted_by)
    assert artifact.artifact_type == GrantArtifact.ArtifactType.UPLOADED
    assert artifact.uploaded_at is not None
    assert artifact in grant.artifacts.all()
    _cleanup(grant)


# ---------------------------------------------------------------------------
# Auto-generate hook fires (only) when the award type is configured
# ---------------------------------------------------------------------------
def test_auto_generate_on_grant_when_enabled():
    award = AwardTypeFactory(grant_method="direct", level="member", auto_generate_certificate=True)
    cycle = AwardCycleFactory()
    member = UserFactory(status="active")
    granter = UserFactory(is_superuser=True)
    with mock.patch("thetatauCMT.awards.certificates.render_to_pdf", return_value=_FAKE_PDF):
        grant = direct_grant(award, cycle, member, granter)
    assert grant.artifacts.filter(artifact_type=GrantArtifact.ArtifactType.GENERATED).exists()
    _cleanup(grant)


def test_no_auto_generate_when_disabled():
    award = AwardTypeFactory(grant_method="direct", level="member", auto_generate_certificate=False)
    cycle = AwardCycleFactory()
    member = UserFactory(status="active")
    granter = UserFactory(is_superuser=True)
    grant = direct_grant(award, cycle, member, granter)
    assert not grant.artifacts.exists()


def test_auto_generate_failure_does_not_break_grant():
    award = AwardTypeFactory(grant_method="direct", level="member", auto_generate_certificate=True)
    cycle = AwardCycleFactory()
    member = UserFactory(status="active")
    granter = UserFactory(is_superuser=True)
    with mock.patch("thetatauCMT.awards.certificates.render_to_pdf", side_effect=RuntimeError("boom")):
        grant = direct_grant(award, cycle, member, granter)  # must not raise
    assert grant.pk is not None
    assert not grant.artifacts.exists()


# ---------------------------------------------------------------------------
# Acceptance: download works
# ---------------------------------------------------------------------------
def test_download_view_serves_file(client):
    grant = AwardGrantFactory()
    artifact = store_uploaded_artifact(
        grant, SimpleUploadedFile("l.pdf", b"%PDF download"), created_by=grant.granted_by
    )
    client.force_login(_view_user())
    resp = client.get(reverse("awards:artifact_download", args=[artifact.pk]))
    assert resp.status_code == 200
    content = b"".join(resp.streaming_content)
    assert content.startswith(b"%PDF")
    _cleanup(grant)


def test_download_requires_login(client):
    grant = AwardGrantFactory()
    artifact = store_uploaded_artifact(grant, SimpleUploadedFile("l.pdf", b"%PDF x"), created_by=grant.granted_by)
    resp = client.get(reverse("awards:artifact_download", args=[artifact.pk]))
    assert resp.status_code == 302
    _cleanup(grant)


# ---------------------------------------------------------------------------
# Upload view: officer gating + happy path
# ---------------------------------------------------------------------------
def test_upload_view_stores_artifact(client):
    grant = AwardGrantFactory()
    client.force_login(_view_user())
    resp = client.post(
        reverse("awards:grant_artifacts", args=[grant.pk]),
        {"action": "upload", "file": SimpleUploadedFile("l.pdf", b"%PDF upload")},
    )
    assert resp.status_code == 302
    assert grant.artifacts.filter(artifact_type=GrantArtifact.ArtifactType.UPLOADED).exists()
    _cleanup(grant)


def test_artifact_view_blocks_non_officer(client):
    grant = AwardGrantFactory()
    member = UserFactory()
    _sign_rmp(member)
    client.force_login(member)
    resp = client.get(reverse("awards:grant_artifacts", args=[grant.pk]))
    assert resp.status_code == 302
    assert resp.url == reverse("home")
