"""Tests for the reusable admin "merge selected records" action.

Exercises both relation kinds the merge must repoint: a reverse foreign key
(``Organization`` <- ``UserOrgParticipate.organization``) and a reverse
many-to-many (``UserTag`` <- ``User.tags``).
"""

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory


def _merge_request(user, canonical_pk):
    request = RequestFactory().post("/admin/merge/", {"merge": "1", "canonical": str(canonical_pk)})
    request.user = user
    setattr(request, "session", {})
    setattr(request, "_messages", FallbackStorage(request))
    return request


@pytest.mark.django_db
def test_merge_organizations_repoints_foreign_keys():
    from thetatauCMT.users.admin import OrganizationAdmin
    from thetatauCMT.users.models import Organization
    from thetatauCMT.users.tests.factories import UserFactory, UserOrgParticipateFactory

    keep = Organization.objects.create(name="IEEE")
    dup = Organization.objects.create(name="I.E.E.E.")
    participation = UserOrgParticipateFactory.create(organization=dup)

    model_admin = OrganizationAdmin(Organization, AdminSite())
    queryset = Organization.objects.filter(pk__in=[keep.pk, dup.pk])
    model_admin.merge_selected_records(_merge_request(UserFactory.create(), keep.pk), queryset)

    participation.refresh_from_db()
    assert participation.organization_id == keep.pk
    assert not Organization.objects.filter(pk=dup.pk).exists()
    assert Organization.objects.filter(pk=keep.pk).exists()


@pytest.mark.django_db
def test_merge_user_tags_repoints_many_to_many():
    from thetatauCMT.users.admin import UserTagAdmin
    from thetatauCMT.users.models import UserTag
    from thetatauCMT.users.tests.factories import UserFactory

    keep = UserTag.objects.create(name="Trustee")
    dup = UserTag.objects.create(name="trustee")
    member = UserFactory.create()
    member.tags.add(dup)

    model_admin = UserTagAdmin(UserTag, AdminSite())
    queryset = UserTag.objects.filter(pk__in=[keep.pk, dup.pk])
    model_admin.merge_selected_records(_merge_request(member, keep.pk), queryset)

    assert list(member.tags.values_list("name", flat=True)) == ["Trustee"]
    assert not UserTag.objects.filter(pk=dup.pk).exists()


@pytest.mark.django_db
def test_merge_requires_two_records():
    from thetatauCMT.users.admin import OrganizationAdmin
    from thetatauCMT.users.models import Organization
    from thetatauCMT.users.tests.factories import UserFactory

    only = Organization.objects.create(name="Only One")
    model_admin = OrganizationAdmin(Organization, AdminSite())
    queryset = Organization.objects.filter(pk=only.pk)
    # Fewer than two selected -> no-op, the record survives.
    model_admin.merge_selected_records(_merge_request(UserFactory.create(), only.pk), queryset)
    assert Organization.objects.filter(pk=only.pk).exists()


@pytest.mark.django_db
def test_merge_confirmation_page_renders():
    """Without ``merge`` in POST the action returns the confirmation page."""
    from thetatauCMT.users.admin import OrganizationAdmin
    from thetatauCMT.users.models import Organization
    from thetatauCMT.users.tests.factories import UserFactory

    a = Organization.objects.create(name="Alpha")
    b = Organization.objects.create(name="Beta")
    model_admin = OrganizationAdmin(Organization, AdminSite())
    request = RequestFactory().post("/admin/merge/", {})
    request.user = UserFactory.create(is_staff=True, is_superuser=True)
    setattr(request, "session", {})
    setattr(request, "_messages", FallbackStorage(request))
    queryset = Organization.objects.filter(pk__in=[a.pk, b.pk])
    response = model_admin.merge_selected_records(request, queryset)
    response.render()
    assert response.status_code == 200
    assert b"Alpha" in response.content and b"Beta" in response.content
