import datetime
from zoneinfo import ZoneInfo

import factory

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.models import UserRoleChange
from thetatauCMT.users.tests.factories import UserFactory

from ..models import (
    Assignment,
    Competition,
    CriterionScore,
    Entry,
    EntryFile,
    Judge,
    Participant,
    Round,
    RubricCriterion,
    Scorecard,
    SubmissionItem,
)

EASTERN = ZoneInfo("America/New_York")
FAR_FUTURE = datetime.date(2099, 12, 31)


def eastern(year, month, day, hour=0, minute=0, second=0):
    return datetime.datetime(year, month, day, hour, minute, second, tzinfo=EASTERN)


def member(chapter, status="active", **kwargs):
    """A member of ``chapter`` with ``status`` (``pnm``, ``alumni``...).

    The status factory picks a random start date, which can fall after the import-time
    ``TODAY`` when a test freezes the clock later in the year, so the status is set directly.
    """
    user = UserFactory(chapter=chapter, status=status, **kwargs)
    if user.current_status != status:
        user.current_status = status
        user.save(update_fields=["current_status"])
    return user


def give_role(user, role):
    """A current role, such as ``pd chair`` or ``professional development director``.

    Starts long ago, so it is current whatever date a test freezes the clock at.
    """
    UserRoleChange.objects.create(user=user, role=role, start=datetime.date(2020, 1, 1), end=FAR_FUTURE)
    user.refresh_from_db()
    return user


def national_officer(role="regional director", **kwargs):
    """An alumnus holding a National Officer role, so in the ``natoff`` group."""
    return give_role(UserFactory(status="alumni", **kwargs), role)


def set_config(key, value):
    from thetatauCMT.configs.models import Config

    Config.objects.filter(key=key).delete()
    return Config.objects.create(key=key, value=value)


class CompetitionFactory(factory.django.DjangoModelFactory):
    # Far-off years, so a test that also loads this year's fixture never shares a slug.
    year_label = factory.Sequence(lambda n: f"{3000 + n}-{3001 + n}")
    slug = factory.LazyAttribute(lambda o: f"necc-{o.year_label}")
    case_title = "Reduce energy usage in your community"
    is_published = True

    class Meta:
        model = Competition


class RoundFactory(factory.django.DjangoModelFactory):
    competition = factory.SubFactory(CompetitionFactory)
    number = 1
    name = "Proposal"
    opens_at = factory.LazyFunction(lambda: eastern(2026, 12, 4))
    closes_at = factory.LazyFunction(lambda: eastern(2026, 12, 11, 23, 59, 59))
    judging_closes_at = factory.LazyFunction(lambda: eastern(2027, 1, 8, 23, 59, 59))
    advance_per_region = 2
    advance_total = 20

    class Meta:
        model = Round


class RubricCriterionFactory(factory.django.DjangoModelFactory):
    round = factory.SubFactory(RoundFactory)
    name = factory.Sequence(lambda n: f"Criterion {n}")
    order = factory.Sequence(lambda n: n)

    class Meta:
        model = RubricCriterion


class SubmissionItemFactory(factory.django.DjangoModelFactory):
    round = factory.SubFactory(RoundFactory)
    label = factory.Sequence(lambda n: f"Item {n}")
    file_types = factory.LazyFunction(lambda: ["pdf", "powerpoint"])

    class Meta:
        model = SubmissionItem


class ParticipantFactory(factory.django.DjangoModelFactory):
    competition = factory.SubFactory(CompetitionFactory)
    chapter = factory.SubFactory(ChapterFactory)

    class Meta:
        model = Participant


class EntryFactory(factory.django.DjangoModelFactory):
    round = factory.SubFactory(RoundFactory)
    chapter = factory.SubFactory(ChapterFactory)
    title = factory.Faker("sentence", nb_words=4)

    class Meta:
        model = Entry


class EntryFileFactory(factory.django.DjangoModelFactory):
    """A link, so tests write no files; pass ``file=`` (with ``settings.MEDIA_ROOT``) for an upload."""

    entry = factory.SubFactory(EntryFactory)
    item = factory.SubFactory(SubmissionItemFactory, round=factory.SelfAttribute("..entry.round"))
    link = "https://example.com/proposal"

    class Meta:
        model = EntryFile


class JudgeFactory(factory.django.DjangoModelFactory):
    round = factory.SubFactory(RoundFactory)
    user = factory.SubFactory(UserFactory)

    class Meta:
        model = Judge


class AssignmentFactory(factory.django.DjangoModelFactory):
    judge = factory.SubFactory(JudgeFactory)
    entry = factory.SubFactory(EntryFactory, round=factory.SelfAttribute("..judge.round"))

    class Meta:
        model = Assignment


class ScorecardFactory(factory.django.DjangoModelFactory):
    assignment = factory.SubFactory(AssignmentFactory)

    class Meta:
        model = Scorecard


class CriterionScoreFactory(factory.django.DjangoModelFactory):
    scorecard = factory.SubFactory(ScorecardFactory)
    criterion = factory.SubFactory(
        RubricCriterionFactory, round=factory.SelfAttribute("..scorecard.assignment.entry.round")
    )
    points = 4

    class Meta:
        model = CriterionScore
