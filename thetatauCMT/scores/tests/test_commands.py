import pytest
from django.core.management import call_command

from thetatauCMT.scores.models import ScoreChapter, ScoreType
from thetatauCMT.users.models import UserSemesterServiceHours


@pytest.mark.django_db
def test_score_calculate_extras_does_not_wipe_service_hours(chapter, user_factory):
    """service-hours is type Evt but scored from UserSemesterServiceHours; the
    end-of-year Event/Sub recompute must not overwrite it back to 0."""
    year = 2028
    service_type = ScoreType.objects.get(slug="service-hours")
    # Isolate from any rows leaked by --reuse-db.
    UserSemesterServiceHours.objects.filter(user__chapter=chapter, year=year).delete()
    ScoreChapter.objects.filter(chapter=chapter, type=service_type).delete()

    member = user_factory.create(chapter=chapter)
    UserSemesterServiceHours.objects.create(user=member, year=year, term="fa", service_hours=100)

    call_command("score_calculate_extras", str(year), str(year))

    fall = ScoreChapter.objects.get(chapter=chapter, type=service_type, year=year, term="fa")
    # Before the fix this was overwritten to 0 by the final Evt/Sub recompute.
    assert fall.score > 0
