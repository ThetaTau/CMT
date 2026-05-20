"""Tests for forms/filters.py."""

import pytest

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.tests.factories import UserFactory


@pytest.mark.django_db
def test_audit_list_filter_no_value_returns_all():
    """filter_chapter with no value returns original queryset."""
    from thetatauCMT.forms.filters import AuditListFilter
    from thetatauCMT.forms.models import Audit

    qs = Audit.objects.all()
    f = AuditListFilter(data={}, queryset=qs)
    assert list(f.qs) == list(qs)


@pytest.mark.django_db
def test_audit_list_filter_by_chapter():
    """filter_chapter method filters by chapter slug when given a value."""
    from thetatauCMT.forms.filters import AuditListFilter
    from thetatauCMT.forms.models import Audit
    from thetatauCMT.forms.tests.factories import AuditFactory

    chapter1 = ChapterFactory.create()
    chapter2 = ChapterFactory.create()
    user1 = UserFactory.create(chapter=chapter1)
    user2 = UserFactory.create(chapter=chapter2)
    audit1 = AuditFactory.create(user=user1)
    audit2 = AuditFactory.create(user=user2)

    # Call filter_chapter directly on the full queryset
    qs = Audit.objects.filter(pk__in=[audit1.pk, audit2.pk])
    f = AuditListFilter(queryset=qs)
    result = f.filter_chapter(qs, "chapter", chapter1.slug)
    result_pks = {a.pk for a in result}
    assert audit1.pk in result_pks
    assert audit2.pk not in result_pks


@pytest.mark.django_db
def test_complete_list_filter_filter_region_national():
    """filter_region with 'national' returns unchanged queryset."""
    from thetatauCMT.forms.filters import CompleteListFilter
    from thetatauCMT.forms.models import PledgeProgram

    qs = PledgeProgram.objects.all()
    f = CompleteListFilter(data={"region": "national"}, queryset=qs)
    # national returns all, no filter applied
    assert list(f.qs) == list(qs)


@pytest.mark.django_db
def test_complete_list_filter_filter_region_candidate_chapter():
    """filter_region with 'candidate_chapter' filters for candidate chapters."""
    from thetatauCMT.forms.filters import CompleteListFilter
    from thetatauCMT.forms.models import PledgeProgram

    qs = PledgeProgram.objects.all()
    f = CompleteListFilter(data={"region": "candidate_chapter"}, queryset=qs)
    for pledge_program in f.qs:
        assert pledge_program.chapter.candidate_chapter


@pytest.mark.django_db
def test_complete_list_filter_filter_region_by_slug():
    """filter_region with a region slug filters by that region."""
    from thetatauCMT.forms.filters import CompleteListFilter
    from thetatauCMT.forms.models import PledgeProgram
    from thetatauCMT.regions.models import Region

    regions = Region.objects.all()
    if not regions.exists():
        pytest.skip("No regions in DB")
    region = regions.first()
    qs = PledgeProgram.objects.all()
    f = CompleteListFilter(data={"region": region.slug}, queryset=qs)
    for pp in f.qs:
        assert pp.chapter.region == region


@pytest.mark.django_db
def test_alumni_exclusion_filter_init():
    """AlumniExclusionListFilter initializes with default regional_director_veto=None."""
    from thetatauCMT.forms.filters import AlumniExclusionListFilter
    from thetatauCMT.forms.models import AlumniExclusion

    qs = AlumniExclusion.objects.all()
    f = AlumniExclusionListFilter(data={}, queryset=qs)
    assert f.form.initial["regional_director_veto"] is None


@pytest.mark.django_db
def test_alumni_exclusion_filter_region_national():
    """AlumniExclusionListFilter filter_region with 'national' returns all."""
    from thetatauCMT.forms.filters import AlumniExclusionListFilter
    from thetatauCMT.forms.models import AlumniExclusion

    qs = AlumniExclusion.objects.all()
    f = AlumniExclusionListFilter(data={"region": "national"}, queryset=qs)
    assert list(f.qs) == list(qs)


@pytest.mark.django_db
def test_alumni_exclusion_filter_region_candidate_chapter():
    """AlumniExclusionListFilter filters for candidate chapters."""
    from thetatauCMT.forms.filters import AlumniExclusionListFilter
    from thetatauCMT.forms.models import AlumniExclusion

    qs = AlumniExclusion.objects.all()
    f = AlumniExclusionListFilter(data={"region": "candidate_chapter"}, queryset=qs)
    for ae in f.qs:
        assert ae.chapter.candidate_chapter


@pytest.mark.django_db
def test_alumni_exclusion_filter_region_by_slug():
    """AlumniExclusionListFilter filters by a specific region slug."""
    from thetatauCMT.forms.filters import AlumniExclusionListFilter
    from thetatauCMT.forms.models import AlumniExclusion
    from thetatauCMT.regions.models import Region

    regions = Region.objects.all()
    if not regions.exists():
        pytest.skip("No regions in DB")
    region = regions.first()
    qs = AlumniExclusion.objects.all()
    f = AlumniExclusionListFilter(data={"region": region.slug}, queryset=qs)
    for ae in f.qs:
        assert ae.chapter.region == region


@pytest.mark.django_db
def test_education_list_filter_region_national():
    """EducationListFilter filter_region with 'national' returns all."""
    from thetatauCMT.forms.filters import EducationListFilter
    from thetatauCMT.forms.models import HSEducation

    qs = HSEducation.objects.all()
    f = EducationListFilter(data={"region": "national"}, queryset=qs)
    assert list(f.qs) == list(qs)


@pytest.mark.django_db
def test_education_list_filter_region_candidate_chapter():
    """EducationListFilter filters for candidate chapters."""
    from thetatauCMT.forms.filters import EducationListFilter
    from thetatauCMT.forms.models import HSEducation

    qs = HSEducation.objects.all()
    f = EducationListFilter(data={"region": "candidate_chapter"}, queryset=qs)
    for hs in f.qs:
        assert hs.chapter.candidate_chapter


@pytest.mark.django_db
def test_education_list_filter_region_by_slug():
    """EducationListFilter filters by region slug."""
    from thetatauCMT.forms.filters import EducationListFilter
    from thetatauCMT.forms.models import HSEducation
    from thetatauCMT.regions.models import Region

    regions = Region.objects.all()
    if not regions.exists():
        pytest.skip("No regions in DB")
    region = regions.first()
    qs = HSEducation.objects.all()
    f = EducationListFilter(data={"region": region.slug}, queryset=qs)
    for hs in f.qs:
        assert hs.chapter.region == region


@pytest.mark.django_db
def test_bylaws_list_filter_region_national():
    """BylawsListFilter filter_region with 'national' returns all."""
    from thetatauCMT.forms.filters import BylawsListFilter
    from thetatauCMT.forms.models import Bylaws

    qs = Bylaws.objects.all()
    f = BylawsListFilter(data={"region": "national"}, queryset=qs)
    assert list(f.qs) == list(qs)


@pytest.mark.django_db
def test_bylaws_list_filter_region_candidate_chapter():
    """BylawsListFilter filters for candidate chapters."""
    from thetatauCMT.forms.filters import BylawsListFilter
    from thetatauCMT.forms.models import Bylaws

    qs = Bylaws.objects.all()
    f = BylawsListFilter(data={"region": "candidate_chapter"}, queryset=qs)
    for bylaw in f.qs:
        assert bylaw.chapter.candidate_chapter


@pytest.mark.django_db
def test_bylaws_list_filter_region_by_slug():
    """BylawsListFilter filters by region slug."""
    from thetatauCMT.forms.filters import BylawsListFilter
    from thetatauCMT.forms.models import Bylaws
    from thetatauCMT.regions.models import Region

    regions = Region.objects.all()
    if not regions.exists():
        pytest.skip("No regions in DB")
    region = regions.first()
    qs = Bylaws.objects.all()
    f = BylawsListFilter(data={"region": region.slug}, queryset=qs)
    for bylaw in f.qs:
        assert bylaw.chapter.region == region
