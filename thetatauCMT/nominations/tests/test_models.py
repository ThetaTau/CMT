import pytest

from thetatauCMT.configs.models import Config
from thetatauCMT.nominations.flows import NominationFlow
from thetatauCMT.nominations.forms import NOT_INTERESTED_MESSAGE, NominationForm
from thetatauCMT.nominations.models import REVIEWER_CENTRAL_OFFICE, REVIEWER_VETTING, Nomination, get_reviewer_for
from thetatauCMT.nominations.tests.factories import NominationFactory
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Acceptance: the process instantiates
# ---------------------------------------------------------------------------
def test_nomination_process_instantiates():
    nomination = NominationFactory.create()
    assert nomination.pk is not None
    # FlowReferenceField round-trips the flow class through Postgres.
    reloaded = Nomination.objects.get(pk=nomination.pk)
    assert reloaded.flow_class is NominationFlow
    assert reloaded.nominator_id is not None
    assert reloaded.consent_status == "pending"
    assert reloaded.consent_token is not None
    assert reloaded.appointed is False
    assert reloaded.not_interested is False


def test_recommended_positions_multiselect_roundtrip():
    nomination = NominationFactory.create(
        recommended_positions=["grand regent", "regional director"],
    )
    reloaded = Nomination.objects.get(pk=nomination.pk)
    assert set(reloaded.recommended_positions) == {"grand regent", "regional director"}


def test_nominee_display_prefers_member_then_name_then_email():
    member = UserFactory.create(name="Ada Member")
    assert NominationFactory.create(nominee=member).nominee_display == "Ada Member"

    non_member = NominationFactory.create(
        nominee=None, nominee_name="Grace Nonmember", nominee_email="grace@example.com"
    )
    assert non_member.nominee_display == "Grace Nonmember"

    email_only = NominationFactory.create(nominee=None, nominee_name="", nominee_email="only@example.com")
    assert email_only.nominee_display == "only@example.com"


# ---------------------------------------------------------------------------
# Acceptance: node owners resolve from config
# ---------------------------------------------------------------------------
def test_get_reviewer_for_resolves_username_from_config():
    reviewer = UserFactory.create(username="vetting.person@example.com")
    Config.objects.create(key=REVIEWER_VETTING, value="vetting.person@example.com", description="Vetting")
    assert get_reviewer_for(REVIEWER_VETTING) == reviewer


def test_get_reviewer_for_resolves_national_role_from_config():
    director = UserFactory.create(current_roles=["regional director"])
    Config.objects.create(key=REVIEWER_VETTING, value="regional director", description="By role")
    assert get_reviewer_for(REVIEWER_VETTING) == director


def test_get_reviewer_for_falls_back_to_central_office():
    central_office = UserFactory.create(username="co@example.com")
    Config.objects.create(key=REVIEWER_CENTRAL_OFFICE, value="co@example.com", description="CO")
    # VettingReviewer is NOT configured -> resolves via the CentralOffice actor.
    assert get_reviewer_for(REVIEWER_VETTING) == central_office


def test_get_reviewer_for_returns_none_when_unresolved(settings):
    settings.EXECUTIVE_DIRECTOR = "nobody-here@example.com"
    assert get_reviewer_for(REVIEWER_VETTING) is None


# ---------------------------------------------------------------------------
# Only a prior "not interested" response blocks future recommendations
# ---------------------------------------------------------------------------
def _recommend(nominee):
    return NominationForm(
        data={
            "nominee": nominee.pk,
            "level": ["national"],
            "reason": "Would be a great volunteer.",
        }
    )


def test_form_blocks_previously_declined_nominee():
    nominee = UserFactory.create()
    NominationFactory.create(nominee=nominee, not_interested=True)
    form = _recommend(nominee)
    assert not form.is_valid()
    assert NOT_INTERESTED_MESSAGE in form.errors["__all__"]


def test_form_allows_nominee_with_prior_non_declined_record():
    # A rejected / denied record (not_interested is False) must NOT block a
    # fresh recommendation -- records are retained for re-review.
    nominee = UserFactory.create()
    NominationFactory.create(nominee=nominee, not_interested=False)
    form = _recommend(nominee)
    assert form.is_valid(), form.errors


def test_form_requires_a_member_nominee():
    # Only existing members can be nominated -- nominee is required.
    form = NominationForm(data={"level": ["national"], "reason": "x"})
    assert not form.is_valid()
    assert "nominee" in form.errors


def test_self_nomination_overrides_prior_not_interested():
    member = UserFactory.create()
    NominationFactory.create(nominee=member, not_interested=True)
    # Nominating themselves (request_user == nominee) overrides the decline.
    form = NominationForm(
        data={"nominee": member.pk, "level": ["national"], "reason": "I'm interested now"},
        request_user=member,
    )
    assert form.is_valid(), form.errors
