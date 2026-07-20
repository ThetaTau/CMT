"""VWI-7: Training node (manual completion, pluggable provider).

Both trainings required to advance; a single completion does not advance; the
provider hook can mark completion; the mark-complete view is permission-gated.
"""

import pytest
from django.urls import reverse

from thetatauCMT.configs.models import Config
from thetatauCMT.nominations.flows import NominationFlow
from thetatauCMT.nominations.providers import (
    REQUIRED_TRAINING_KEYS,
    TRAINING_CMT,
    TRAINING_VECTOR,
    TRAININGS,
    ManualTrainingProvider,
    get_training_provider,
)
from thetatauCMT.nominations.services import mark_training_complete
from thetatauCMT.users.tests.factories import UserFactory

from ._flow_helpers import active_task, advance_to, start_nomination

pytestmark = pytest.mark.django_db


def _at_training(**kwargs):
    process = start_nomination(**kwargs)
    advance_to(process, "training")
    return process


def test_two_required_trainings_defined():
    assert REQUIRED_TRAINING_KEYS == [TRAINING_CMT, TRAINING_VECTOR]
    labels = dict(TRAININGS)
    assert labels[TRAINING_CMT] == "CMT LMS Volunteer Training"
    assert labels[TRAINING_VECTOR] == "Vector CommunityEdu H&S Training"


def test_single_completion_does_not_advance():
    process = _at_training()
    advanced = mark_training_complete(process, TRAINING_CMT)
    assert advanced is False
    process.refresh_from_db()
    assert process.training_cmt_complete is True
    assert process.training_completed is False
    assert active_task(process, NominationFlow.training) is not None
    assert active_task(process, NominationFlow.confirmation) is None


def test_both_completions_advance_to_confirmation():
    process = _at_training()
    assert mark_training_complete(process, TRAINING_CMT) is False
    assert mark_training_complete(process, TRAINING_VECTOR) is True
    process.refresh_from_db()
    assert process.training_completed is True
    assert active_task(process, NominationFlow.training) is None
    assert active_task(process, NominationFlow.confirmation) is not None


def test_provider_hook_can_mark_complete():
    process = _at_training()
    provider = ManualTrainingProvider()
    provider.mark_complete(process, TRAINING_CMT)
    process.refresh_from_db()
    assert provider.is_complete(process, TRAINING_CMT) is True
    assert provider.all_required_complete(process) is False
    provider.mark_complete(process, TRAINING_VECTOR)
    process.refresh_from_db()
    assert provider.all_required_complete(process) is True


def test_provider_swappable_via_settings(settings):
    settings.NOMINATION_TRAINING_PROVIDER = "thetatauCMT.nominations.providers.ManualTrainingProvider"
    assert isinstance(get_training_provider(), ManualTrainingProvider)


def test_mark_training_complete_uses_injected_provider():
    process = _at_training()
    provider = ManualTrainingProvider()
    assert mark_training_complete(process, TRAINING_CMT, provider=provider) is False
    assert mark_training_complete(process, TRAINING_VECTOR, provider=provider) is True
    assert active_task(process, NominationFlow.confirmation) is not None


def test_training_view_gated_and_marks_complete(auto_login_user):
    admin = UserFactory.create(username="trainer@example.com")
    Config.objects.create(key="TrainingAdministrator", value="trainer@example.com", description="t")
    process = _at_training()
    url = reverse("nominations:training", kwargs={"process_pk": process.pk})

    # A random member cannot access the mark-complete screen.
    client, _other = auto_login_user()
    assert client.get(url).status_code == 403

    # The configured TrainingAdministrator can, and marking both advances.
    client, _ = auto_login_user(user=admin)
    assert client.get(url).status_code == 200
    client.post(url, {"training_key": TRAINING_CMT})
    process.refresh_from_db()
    assert process.training_cmt_complete is True
    assert active_task(process, NominationFlow.confirmation) is None

    client.post(url, {"training_key": TRAINING_VECTOR})
    process.refresh_from_db()
    assert process.training_completed is True
    assert active_task(process, NominationFlow.confirmation) is not None
