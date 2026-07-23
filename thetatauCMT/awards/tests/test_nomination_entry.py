import datetime
import json

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone

from thetatauCMT.awards.forms import ALREADY_NOMINATED_MSG, NOT_ELIGIBLE_NOM_MSG, AwardNominationForm
from thetatauCMT.awards.models import AwardNominationProcess
from thetatauCMT.awards.services import nominatable_award_types
from thetatauCMT.awards.tests._helpers import sign_rmp as _sign_rmp
from thetatauCMT.awards.tests.factories import (
    AwardCycleFactory,
    AwardNominationProcessFactory,
    AwardTypeFactory,
    EligibilityRuleFactory,
)
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def _superuser():
    return UserFactory(is_superuser=True)  # unrestricted scope (service/form level; no middleware)


def _officer():
    user = UserFactory()
    user.groups.add(Group.objects.get_or_create(name="officer")[0])
    return user


def _view_user():
    # natoff-GROUP user (unrestricted scope, not a superuser -> no 2FA middleware), RMP signed.
    user = UserFactory()
    user.groups.add(Group.objects.get_or_create(name="natoff")[0])
    _sign_rmp(user)
    return user


def _nom_award(**kwargs):
    kwargs.setdefault("grant_method", "nomination_workflow")
    kwargs.setdefault("level", "member")
    kwargs.setdefault("nominator_scope", ["member"])
    return AwardTypeFactory(**kwargs)


# ---------------------------------------------------------------------------
# Acceptance: each role sees the correct award list
# ---------------------------------------------------------------------------
def test_award_list_scoped_by_role():
    member_award = _nom_award(nominator_scope=["member"])
    officer_award = _nom_award(nominator_scope=["officer"])
    national_award = _nom_award(nominator_scope=["national"])
    direct_award = AwardTypeFactory(grant_method="direct", nominator_scope=["member"])

    plain_ids = set(nominatable_award_types(UserFactory()).values_list("pk", flat=True))
    assert member_award.pk in plain_ids
    assert officer_award.pk not in plain_ids
    assert national_award.pk not in plain_ids
    assert direct_award.pk not in plain_ids  # direct-grant awards are never nominatable

    officer_ids = set(nominatable_award_types(_officer()).values_list("pk", flat=True))
    assert member_award.pk in officer_ids
    assert officer_award.pk in officer_ids
    assert national_award.pk not in officer_ids

    natoff_ids = set(nominatable_award_types(_superuser()).values_list("pk", flat=True))
    assert {member_award.pk, officer_award.pk, national_award.pk} <= natoff_ids


def test_form_award_out_of_scope_is_rejected():
    national_award = _nom_award(nominator_scope=["national"])
    form = AwardNominationForm(
        data={
            "award_type": national_award.pk,
            "cycle": AwardCycleFactory().pk,
            "recipient_member": UserFactory(status="active").pk,
            "justification": "x",
        },
        request_user=UserFactory(),  # member scope only
    )
    assert not form.is_valid()
    assert "award_type" in form.errors


def test_form_cycle_limited_to_current_periods():
    # Only award periods active today are offered for new nominations (request 1).
    current = AwardCycleFactory(start_date=datetime.date(2000, 1, 1), end_date=None)
    past = AwardCycleFactory(start_date=datetime.date(2000, 1, 1), end_date=datetime.date(2001, 1, 1))
    form = AwardNominationForm(request_user=UserFactory())
    cycle_pks = set(form.fields["cycle"].queryset.values_list("pk", flat=True))
    assert current.pk in cycle_pks
    assert past.pk not in cycle_pks


# ---------------------------------------------------------------------------
# Acceptance: recipient picker populated from eligibility (JSON endpoint)
# ---------------------------------------------------------------------------
def test_eligible_recipients_endpoint_populated_from_eligibility(client):
    award = _nom_award()
    EligibilityRuleFactory(award_type=award, rule_type="member_status", member_status="active")
    cycle = AwardCycleFactory()
    active = UserFactory(status="active")
    alumni = UserFactory(status="alumni")
    client.force_login(_view_user())
    resp = client.get(reverse("awards:eligible_recipients"), {"award_type": award.pk, "cycle": cycle.pk})
    assert resp.status_code == 200
    data = resp.json()
    ids = {row["id"] for row in data["results"]}
    assert data["kind"] == "member"
    assert active.pk in ids
    assert alumni.pk not in ids


def test_eligible_recipients_endpoint_requires_login(client):
    resp = client.get(reverse("awards:eligible_recipients"), {"award_type": 1})
    assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Acceptance: the member picker (autocomplete) is filtered by award eligibility
# ---------------------------------------------------------------------------
def test_recipient_autocomplete_filters_to_alumni_for_alumni_award(client):
    # An alumni-only award must offer only alumni in the nomination member picker.
    award = _nom_award()
    EligibilityRuleFactory(award_type=award, rule_type="member_status", member_status="alumni")
    cycle = AwardCycleFactory()
    alumni = UserFactory(status="alumni")
    active = UserFactory(status="active")
    client.force_login(_view_user())
    resp = client.get(
        reverse("awards:recipient_member_autocomplete"),
        {"forward": json.dumps({"award_type": award.pk, "cycle": cycle.pk})},
    )
    assert resp.status_code == 200
    ids = {str(row["id"]) for row in resp.json()["results"]}
    assert str(alumni.pk) in ids
    assert str(active.pk) not in ids


def test_recipient_autocomplete_empty_without_award(client):
    # Until an award is chosen nothing is offered (the field is hidden anyway).
    UserFactory(status="alumni")
    client.force_login(_view_user())
    resp = client.get(reverse("awards:recipient_member_autocomplete"))
    assert resp.status_code == 200
    assert resp.json()["results"] == []


def test_recipient_autocomplete_requires_login(client):
    resp = client.get(reverse("awards:recipient_member_autocomplete"))
    assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Acceptance: ineligible recipients never selectable (form enforces server-side)
# ---------------------------------------------------------------------------
def test_form_rejects_ineligible_recipient():
    award = _nom_award()
    EligibilityRuleFactory(award_type=award, rule_type="member_status", member_status="active")
    form = AwardNominationForm(
        data={
            "award_type": award.pk,
            "cycle": AwardCycleFactory().pk,
            "recipient_member": UserFactory(status="alumni").pk,
            "justification": "x",
        },
        request_user=_superuser(),
    )
    assert not form.is_valid()
    assert NOT_ELIGIBLE_NOM_MSG in str(form.errors)


def test_form_valid_for_eligible_in_scope():
    award = _nom_award()
    member = UserFactory(status="active")
    form = AwardNominationForm(
        data={
            "award_type": award.pk,
            "cycle": AwardCycleFactory().pk,
            "recipient_member": member.pk,
            "justification": "Great work",
        },
        request_user=_superuser(),
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["recipient"] == member


def test_form_requires_matching_recipient_kind():
    award = _nom_award(level="member")
    # supply a chapter recipient for a member-kind award -> invalid
    from thetatauCMT.chapters.tests.factories import ChapterFactory

    form = AwardNominationForm(
        data={
            "award_type": award.pk,
            "cycle": AwardCycleFactory().pk,
            "recipient_chapter": ChapterFactory().pk,
            "justification": "x",
        },
        request_user=_superuser(),
    )
    assert not form.is_valid()


# ---------------------------------------------------------------------------
# Acceptance: multiple-nomination rule enforced per award/cycle
# ---------------------------------------------------------------------------
def test_multi_nomination_blocked_when_not_allowed():
    award = _nom_award(allow_multiple_nominations=False)
    cycle = AwardCycleFactory()
    member = UserFactory(status="active")
    AwardNominationProcessFactory(award_type=award, cycle=cycle, recipient_member=member)
    form = AwardNominationForm(
        data={"award_type": award.pk, "cycle": cycle.pk, "recipient_member": member.pk, "justification": "x"},
        request_user=_superuser(),
    )
    assert not form.is_valid()
    assert ALREADY_NOMINATED_MSG in str(form.errors)


def test_multi_nomination_allowed_when_configured():
    award = _nom_award(allow_multiple_nominations=True)
    cycle = AwardCycleFactory()
    member = UserFactory(status="active")
    AwardNominationProcessFactory(award_type=award, cycle=cycle, recipient_member=member)
    form = AwardNominationForm(
        data={"award_type": award.pk, "cycle": cycle.pk, "recipient_member": member.pk, "justification": "x"},
        request_user=_superuser(),
    )
    assert form.is_valid(), form.errors


def test_rejected_nomination_does_not_block_renomination():
    award = _nom_award(allow_multiple_nominations=False)
    cycle = AwardCycleFactory()
    member = UserFactory(status="active")
    AwardNominationProcessFactory(
        award_type=award, cycle=cycle, recipient_member=member, result=AwardNominationProcess.Result.REJECTED
    )
    form = AwardNominationForm(
        data={"award_type": award.pk, "cycle": cycle.pk, "recipient_member": member.pk, "justification": "x"},
        request_user=_superuser(),
    )
    assert form.is_valid(), form.errors


# ---------------------------------------------------------------------------
# Viewflow Start integration: submitting the entry creates a process
# ---------------------------------------------------------------------------
def test_nomination_start_view_creates_process(client):
    award = _nom_award()
    cycle = AwardCycleFactory()
    member = UserFactory(status="active")
    natoff = _view_user()
    client.force_login(natoff)
    url = reverse("viewflow:awards:awardnomination:start")
    resp = client.post(
        url,
        {
            "award_type": award.pk,
            "cycle": cycle.pk,
            "recipient_member": member.pk,
            "justification": "Great work",
            "_viewflow_activation-started": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    assert resp.status_code == 302
    nomination = AwardNominationProcess.objects.get(award_type=award, recipient_member=member)
    assert nomination.nominator == natoff
    assert nomination.justification == "Great work"


def test_nomination_start_view_prefills_from_query_params(client):
    # The profile / chapter / award-page "Nominate" buttons pass the recipient,
    # award, and cycle as query params; the start form pre-fills them.
    award = _nom_award()
    cycle = AwardCycleFactory()
    member = UserFactory(status="active")
    client.force_login(_view_user())
    resp = client.get(
        reverse("viewflow:awards:awardnomination:start"),
        {"award_type": award.pk, "cycle": cycle.pk, "recipient_member": member.pk},
    )
    assert resp.status_code == 200
    initial = resp.context["form"].initial
    assert initial.get("recipient_member") == str(member.pk)
    assert initial.get("award_type") == str(award.pk)
    assert initial.get("cycle") == str(cycle.pk)


def test_nomination_form_exposes_award_recipient_kinds(client):
    # The form reveals only the recipient field matching the selected award's kind;
    # the template JS reads this award_pk -> kind map.
    member_award = _nom_award(level="member")
    chapter_award = _nom_award(level="chapter", nominator_scope=["national"])
    client.force_login(_view_user())
    resp = client.get(reverse("viewflow:awards:awardnomination:start"))
    assert resp.status_code == 200
    kinds = resp.context["award_kinds"]
    assert kinds[str(member_award.pk)] == "member"
    assert kinds[str(chapter_award.pk)] == "chapter"


def test_osm_award_excluded_from_nominatable():
    # The Outstanding Student Member award is granted only through the forms-app
    # OSM flow; it must never appear in the awards nomination list, even when
    # configured as a nomination-workflow award with the widest nominator scope.
    from thetatauCMT.awards.services import OSM_AWARD_NAME

    osm_award = _nom_award(name=OSM_AWARD_NAME, nominator_scope=["member", "officer", "national"])
    ids = set(nominatable_award_types(_superuser()).values_list("pk", flat=True))
    assert osm_award.pk not in ids
