import datetime

import factory
from django.utils import timezone

from core.models import CSS_ROLE
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.models import UserRoleChange
from thetatauCMT.users.tests.factories import UserFactory

from ..models import ChapterSupportAssignment, SupportDigestEntry

FAR_FUTURE = datetime.date(2099, 12, 31)


def central_office():
    """The inactive home chapter for non-member CSS accounts; its slug is central-office."""
    return ChapterFactory(name="Central Office", greek="CO", active=False)


def add_totp_device(user):
    """A confirmed two-factor device, which every CSS must have (CSSWI-11)."""
    from django_otp.plugins.otp_totp.models import TOTPDevice

    return TOTPDevice.objects.get_or_create(user=user, name="default", defaults={"confirmed": True})[0]


def give_css_role(user, start=None, end=FAR_FUTURE, two_factor=True):
    start = start or timezone.localdate() - datetime.timedelta(days=30)
    role = UserRoleChange.objects.create(user=user, role=CSS_ROLE, start=start, end=end)
    if two_factor:
        add_totp_device(user)
    return role


def make_css(two_factor=True, **kwargs):
    """A non-member CSS: status ``css``, home chapter Central Office, current CSS role.

    ``two_factor=False`` leaves out the device the two-factor middleware asks for.
    """
    kwargs.setdefault("chapter", central_office())
    user = UserFactory(status="css", **kwargs)
    give_css_role(user, two_factor=two_factor)
    user.refresh_from_db()
    return user


def make_regent(**kwargs):
    """A chapter's current Regent.

    ``UserFactory(make_officer=True)`` first saves a random role, which can put the user in
    the ``natoff`` group, so tests comparing a CSS with a Regent use this instead.
    """
    user = UserFactory(status="active", **kwargs)
    UserRoleChange.objects.create(
        user=user, role="regent", start=timezone.localdate() - datetime.timedelta(days=30), end=FAR_FUTURE
    )
    user.refresh_from_db()
    return user


class ChapterSupportAssignmentFactory(factory.django.DjangoModelFactory):
    user = factory.LazyFunction(make_css)
    chapter = factory.SubFactory(ChapterFactory)
    start = factory.LazyFunction(lambda: timezone.localdate() - datetime.timedelta(days=7))
    end = None

    class Meta:
        model = ChapterSupportAssignment


class SupportDigestEntryFactory(factory.django.DjangoModelFactory):
    user = factory.LazyFunction(make_css)
    chapter = factory.SubFactory(ChapterFactory)
    kind = SupportDigestEntry.Kind.OFFICER_MONTHLY
    subject = factory.Faker("sentence")

    class Meta:
        model = SupportDigestEntry
