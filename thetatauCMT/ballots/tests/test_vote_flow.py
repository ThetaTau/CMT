"""Vote-time behavior: who you are voting as, the chapter attestation, the
submission receipt, and the Grand Regent / Grand Scribe removing a vote.
"""

import datetime
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.core import mail
from django.urls import reverse

from thetatauCMT.ballots.models import CHAPTER_VOTE_RULE, Ballot, BallotComplete
from thetatauCMT.users.tests.factories import UserFactory, UserRoleChangeFactory


def _create_ballot(**kwargs):
    defaults = dict(
        name=f"Vote Flow Ballot {datetime.datetime.now().microsecond}",
        type="other",
        description="A test ballot description",
        due_date=datetime.date.today() + timedelta(days=30),
        voters=["all_chapters"],
    )
    defaults.update(kwargs)
    ballot = Ballot(**defaults)
    ballot.save()
    return ballot


def _make_officer(user, client):
    group, _ = Group.objects.get_or_create(name="officer")
    user.groups.add(group)
    client.force_login(user)


def _make_natoff(user, client):
    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    client.force_login(user)


def _officer(chapter, role):
    user = UserFactory.create(chapter=chapter)
    UserRoleChangeFactory.create(user=user, role=role, current=True, officer=role)
    user.refresh_from_db()
    return user


# ---------------------------------------------------------------------------
# The form says who you are and what you are voting as
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_vote_page_names_the_voter_and_their_chapter_role(auto_login_user):
    client, user = auto_login_user(make_officer="regent")
    _make_officer(user, client)
    ballot = _create_ballot(voters=["all_chapters"])
    response = client.get(reverse("ballots:vote", kwargs={"slug": ballot.slug}))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert f"You are voting as {user.name}, Regent" in body
    assert f"This is the {user.chapter.name} Chapter" in body
    assert "single vote" in body


@pytest.mark.django_db
def test_vote_page_names_a_national_officer_role(auto_login_user):
    client, user = auto_login_user(make_officer="grand regent")
    _make_natoff(user, client)
    ballot = _create_ballot(voters=["grand regent"])
    response = client.get(reverse("ballots:vote", kwargs={"slug": ballot.slug}))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert f"You are voting as {user.name}, Grand Regent" in body
    assert "your own vote as a National Officer" in body


# ---------------------------------------------------------------------------
# The four-fifths / out-of-session attestation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_chapter_vote_form_quotes_the_four_fifths_rule(auto_login_user):
    client, user = auto_login_user(make_officer="regent")
    _make_officer(user, client)
    ballot = _create_ballot(voters=["all_chapters"])
    response = client.get(reverse("ballots:vote", kwargs={"slug": ballot.slug}))
    body = response.content.decode("utf-8")
    assert "four-fifths of the student members" in body
    assert 'value="chapter_vote"' in body
    assert 'value="out_of_session"' in body


@pytest.mark.django_db
def test_scribe_is_not_offered_the_out_of_session_option(auto_login_user):
    """The bylaw gives the out-of-session power to the Regent alone."""
    client, user = auto_login_user(make_officer="scribe")
    _make_officer(user, client)
    ballot = _create_ballot(voters=["all_chapters"])
    response = client.get(reverse("ballots:vote", kwargs={"slug": ballot.slug}))
    body = response.content.decode("utf-8")
    assert 'value="chapter_vote"' in body
    assert 'value="out_of_session"' not in body


@pytest.mark.django_db
def test_scribe_cannot_post_out_of_session(auto_login_user):
    client, user = auto_login_user(make_officer="scribe")
    _make_officer(user, client)
    ballot = _create_ballot(voters=["all_chapters"])
    url = reverse("ballots:vote", kwargs={"slug": ballot.slug})
    response = client.post(url, {"motion": "aye", "authority": "out_of_session"})
    assert response.status_code == 200
    assert not BallotComplete.objects.filter(ballot=ballot).exists()


@pytest.mark.django_db
def test_chapter_vote_requires_the_attestation(auto_login_user):
    client, user = auto_login_user(make_officer="regent")
    _make_officer(user, client)
    ballot = _create_ballot(voters=["all_chapters"])
    url = reverse("ballots:vote", kwargs={"slug": ballot.slug})
    response = client.post(url, {"motion": "aye"})
    assert response.status_code == 200
    assert not BallotComplete.objects.filter(ballot=ballot).exists()


@pytest.mark.django_db
def test_regent_can_vote_out_of_session(auto_login_user):
    client, user = auto_login_user(make_officer="regent")
    _make_officer(user, client)
    ballot = _create_ballot(voters=["all_chapters"])
    url = reverse("ballots:vote", kwargs={"slug": ballot.slug})
    response = client.post(url, {"motion": "nay", "authority": "out_of_session"})
    assert response.status_code == 302
    assert BallotComplete.objects.get(ballot=ballot).authority == "out_of_session"


@pytest.mark.django_db
def test_national_officer_vote_has_no_attestation(auto_login_user):
    client, user = auto_login_user(make_officer="grand regent")
    _make_natoff(user, client)
    ballot = _create_ballot(voters=["grand regent"])
    response = client.get(reverse("ballots:vote", kwargs={"slug": ballot.slug}))
    body = response.content.decode("utf-8")
    assert CHAPTER_VOTE_RULE[:40] not in body
    assert 'value="chapter_vote"' not in body
    response = client.post(reverse("ballots:vote", kwargs={"slug": ballot.slug}), {"motion": "aye"})
    assert response.status_code == 302
    assert BallotComplete.objects.get(ballot=ballot).authority == ""


# ---------------------------------------------------------------------------
# Submission receipt
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_voting_emails_a_receipt_that_omits_the_vote(auto_login_user):
    client, user = auto_login_user(make_officer="regent")
    _make_officer(user, client)
    ballot = _create_ballot(voters=["all_chapters"])
    mail.outbox = []
    client.post(
        reverse("ballots:vote", kwargs={"slug": ballot.slug}),
        {"motion": "aye", "authority": "chapter_vote"},
    )
    assert len(mail.outbox) == 1
    receipt = mail.outbox[0]
    assert receipt.subject == f"Ballot submitted: {ballot.name}"
    assert user.email in receipt.to
    html = receipt.alternatives[0][0]
    assert "submitted by" in html
    assert reverse("ballots:vote", kwargs={"slug": ballot.slug}) in html
    # The receipt must never repeat the motion.
    assert ">Aye<" not in html
    assert "Aye" not in html


@pytest.mark.django_db
def test_chapter_receipt_goes_to_both_the_regent_and_the_scribe(auto_login_user):
    """Both officers were asked for the ballot, so both are told it is in."""
    client, scribe = auto_login_user(make_officer="scribe")
    _make_officer(scribe, client)
    regent = _officer(scribe.chapter, "regent")
    ballot = _create_ballot(voters=["all_chapters"])
    mail.outbox = []
    client.post(
        reverse("ballots:vote", kwargs={"slug": ballot.slug}),
        {"motion": "aye", "authority": "chapter_vote"},
    )
    assert len(mail.outbox) == 1
    recipients = set(mail.outbox[0].to)
    assert scribe.email in recipients
    assert regent.email in recipients
    html = mail.outbox[0].alternatives[0][0]
    assert scribe.name in html
    assert "Both the Regent and the Scribe receive this confirmation" in html


@pytest.mark.django_db
def test_chapter_receipt_uses_the_chapter_generic_addresses(auto_login_user):
    client, user = auto_login_user(make_officer="regent")
    _make_officer(user, client)
    chapter = user.chapter
    chapter.email_scribe = "scribe@example.com"
    chapter.save()
    ballot = _create_ballot(voters=["all_chapters"])
    mail.outbox = []
    client.post(
        reverse("ballots:vote", kwargs={"slug": ballot.slug}),
        {"motion": "aye", "authority": "chapter_vote"},
    )
    assert "scribe@example.com" in mail.outbox[0].to


@pytest.mark.django_db
def test_national_officer_receipt_goes_only_to_them(auto_login_user):
    client, user = auto_login_user(make_officer="grand regent")
    _make_natoff(user, client)
    ballot = _create_ballot(voters=["grand regent"])
    mail.outbox = []
    client.post(reverse("ballots:vote", kwargs={"slug": ballot.slug}), {"motion": "aye"})
    assert set(mail.outbox[0].to) <= {email for email in user.emails if email}
    html = mail.outbox[0].alternatives[0][0]
    assert "Both the Regent and the Scribe" not in html


@pytest.mark.django_db
def test_receipt_names_the_role_and_chapter(auto_login_user):
    client, user = auto_login_user(make_officer="scribe")
    _make_officer(user, client)
    ballot = _create_ballot(voters=["all_chapters"])
    mail.outbox = []
    client.post(
        reverse("ballots:vote", kwargs={"slug": ballot.slug}),
        {"motion": "abstain", "authority": "chapter_vote"},
    )
    html = mail.outbox[0].alternatives[0][0]
    assert "Scribe" in html
    assert user.chapter.name in html


@pytest.mark.django_db
def test_a_rejected_vote_sends_no_receipt(auto_login_user):
    client, user = auto_login_user(make_officer="treasurer")
    _make_officer(user, client)
    ballot = _create_ballot(voters=["all_chapters"])
    mail.outbox = []
    client.post(
        reverse("ballots:vote", kwargs={"slug": ballot.slug}),
        {"motion": "aye", "authority": "chapter_vote"},
    )
    assert mail.outbox == []


# ---------------------------------------------------------------------------
# Removing a mistaken submission
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_grand_scribe_can_remove_a_submission(auto_login_user):
    client, grand_scribe = auto_login_user(make_officer="grand scribe")
    _make_natoff(grand_scribe, client)
    ballot = _create_ballot(voters=["all_chapters"])
    regent = _officer(UserFactory.create().chapter, "regent")
    vote = BallotComplete(ballot=ballot, user=regent, motion="aye", role="regent", authority="chapter_vote")
    vote.save()
    mail.outbox = []
    response = client.post(reverse("ballots:vote_delete", kwargs={"pk": vote.pk}), {"reason": "Voted too early"})
    assert response.status_code == 302
    assert not BallotComplete.objects.filter(pk=vote.pk).exists()
    assert len(mail.outbox) == 1
    notice = mail.outbox[0]
    assert notice.subject == f"Ballot submission removed: {ballot.name}"
    assert regent.email in notice.to
    assert grand_scribe.email in notice.to
    html = notice.alternatives[0][0]
    assert "Voted too early" in html
    assert "Aye" not in html


@pytest.mark.django_db
def test_removal_notifies_the_chapter_officers(auto_login_user):
    client, grand_regent = auto_login_user(make_officer="grand regent")
    _make_natoff(grand_regent, client)
    ballot = _create_ballot(voters=["all_chapters"])
    regent = _officer(UserFactory.create().chapter, "regent")
    treasurer = _officer(regent.chapter, "treasurer")
    vote = BallotComplete(ballot=ballot, user=regent, motion="aye", role="regent", authority="chapter_vote")
    vote.save()
    mail.outbox = []
    client.post(reverse("ballots:vote_delete", kwargs={"pk": vote.pk}))
    assert treasurer.email in mail.outbox[0].to


@pytest.mark.django_db
def test_removal_lets_the_chapter_vote_again(auto_login_user):
    client, grand_regent = auto_login_user(make_officer="grand regent")
    _make_natoff(grand_regent, client)
    ballot = _create_ballot(voters=["all_chapters"])
    regent = _officer(UserFactory.create().chapter, "regent")
    vote = BallotComplete(ballot=ballot, user=regent, motion="aye", role="regent", authority="chapter_vote")
    vote.save()
    assert ballot.chapter_vote(regent.chapter) is not None
    client.post(reverse("ballots:vote_delete", kwargs={"pk": vote.pk}))
    assert ballot.chapter_vote(regent.chapter) is None
    assert ballot in Ballot.outstanding_for_user(regent)


@pytest.mark.django_db
def test_removal_reopens_the_chapter_task():
    """The chapter's ballot task must not stay ticked once the vote is gone."""
    from thetatauCMT.tasks.models import Task, TaskChapter, TaskDate

    ballot = _create_ballot(voters=["all_chapters"], name="Task Reopen Ballot")
    regent = _officer(UserFactory.create().chapter, "regent")
    vote = BallotComplete(ballot=ballot, user=regent, motion="aye", role="regent", authority="chapter_vote")
    vote.save()
    task = Task.objects.get(name="Task Reopen Ballot")
    task_date = TaskDate.objects.get(task=task, date=ballot.due_date)
    assert TaskChapter.objects.filter(task=task_date, chapter=regent.chapter).exists()
    vote.clear_chapter_task_complete()
    assert not TaskChapter.objects.filter(task=task_date, chapter=regent.chapter).exists()


@pytest.mark.django_db
def test_other_officers_cannot_remove_a_submission(auto_login_user):
    client, user = auto_login_user(make_officer="grand treasurer")
    _make_natoff(user, client)
    ballot = _create_ballot(voters=["all_chapters"])
    regent = _officer(UserFactory.create().chapter, "regent")
    vote = BallotComplete(ballot=ballot, user=regent, motion="aye", role="regent", authority="chapter_vote")
    vote.save()
    mail.outbox = []
    response = client.post(reverse("ballots:vote_delete", kwargs={"pk": vote.pk}))
    assert response.status_code == 302
    assert BallotComplete.objects.filter(pk=vote.pk).exists()
    assert mail.outbox == []


@pytest.mark.django_db
def test_the_voter_cannot_remove_their_own_submission(auto_login_user):
    client, user = auto_login_user(make_officer="regent")
    _make_officer(user, client)
    ballot = _create_ballot(voters=["all_chapters"])
    vote = BallotComplete(ballot=ballot, user=user, motion="aye", role="regent", authority="chapter_vote")
    vote.save()
    response = client.get(reverse("ballots:vote_delete", kwargs={"pk": vote.pk}))
    assert response.status_code == 302
    assert BallotComplete.objects.filter(pk=vote.pk).exists()


@pytest.mark.django_db
def test_remove_link_only_shown_to_the_grand_officers(auto_login_user):
    client, user = auto_login_user(make_officer="treasurer")
    _make_officer(user, client)
    ballot = _create_ballot(voters=["all_chapters"])
    regent = _officer(UserFactory.create().chapter, "regent")
    vote = BallotComplete(ballot=ballot, user=regent, motion="aye", role="regent", authority="chapter_vote")
    vote.save()
    body = client.get(reverse("ballots:detail", kwargs={"slug": ballot.slug})).content.decode("utf-8")
    assert "vote/delete" not in body
    assert "Decided By" not in body


@pytest.mark.django_db
def test_grand_regent_sees_the_remove_link_and_authority(auto_login_user):
    client, user = auto_login_user(make_officer="grand regent")
    _make_natoff(user, client)
    ballot = _create_ballot(voters=["all_chapters"])
    regent = _officer(UserFactory.create().chapter, "regent")
    vote = BallotComplete(ballot=ballot, user=regent, motion="aye", role="regent", authority="out_of_session")
    vote.save()
    body = client.get(reverse("ballots:detail", kwargs={"slug": ballot.slug})).content.decode("utf-8")
    assert reverse("ballots:vote_delete", kwargs={"pk": vote.pk}) in body
    assert "Decided By" in body
    assert "out of session" in body.lower()
