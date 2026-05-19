"""
Unit tests for thetatauCMT/users/flows.py – MemberUpdateFlow.

Covers:
- Smoke / process_class assertion
- Transition guard conditions (check_user, check_approval, check_manual_outcome)
- get_updated classmethod (no changes, changed field, no user, perform_update)
- Handler functions: email_delay_func, deny_notify_func, update_func
"""

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Smoke: import and process_class
# ---------------------------------------------------------------------------


def test_member_update_flow_imports():
    """MemberUpdateFlow can be imported without errors."""
    from thetatauCMT.users.flows import MemberUpdateFlow

    assert MemberUpdateFlow is not None


def test_member_update_flow_process_class():
    """MemberUpdateFlow.process_class is MemberUpdate."""
    from thetatauCMT.users.flows import MemberUpdateFlow
    from thetatauCMT.users.models import MemberUpdate

    assert MemberUpdateFlow.process_class is MemberUpdate


# ---------------------------------------------------------------------------
# Transition guards – check_user condition
# ---------------------------------------------------------------------------


def test_check_user_condition_true_when_user_set():
    """check_user: condition returns True when process.user is not None."""
    from thetatauCMT.users.flows import MemberUpdateFlow

    cond = MemberUpdateFlow.check_user._condition
    act = MagicMock()
    act.process.user = object()
    assert cond(act) is True


def test_check_user_condition_false_when_user_none():
    """check_user: condition returns False when process.user is None."""
    from thetatauCMT.users.flows import MemberUpdateFlow

    cond = MemberUpdateFlow.check_user._condition
    act = MagicMock()
    act.process.user = None
    assert cond(act) is False


# ---------------------------------------------------------------------------
# Transition guards – check_approval condition
# ---------------------------------------------------------------------------


def test_check_approval_condition_true():
    """check_approval: condition returns True when process.approved is True."""
    from thetatauCMT.users.flows import MemberUpdateFlow

    cond = MemberUpdateFlow.check_approval._condition
    act = MagicMock()
    act.process.approved = True
    assert cond(act) is True


def test_check_approval_condition_false():
    """check_approval: condition returns False when process.approved is False."""
    from thetatauCMT.users.flows import MemberUpdateFlow

    cond = MemberUpdateFlow.check_approval._condition
    act = MagicMock()
    act.process.approved = False
    assert cond(act) is False


# ---------------------------------------------------------------------------
# Transition guards – check_manual_outcome Switch branches
# ---------------------------------------------------------------------------


def test_check_manual_outcome_matched_case():
    """check_manual_outcome 'matched' case is True only when outcome == 'matched'."""
    act = MagicMock()

    def cond(a):
        return a.process.outcome == "matched"

    act.process.outcome = "matched"
    assert cond(act) is True
    act.process.outcome = "created"
    assert cond(act) is False


def test_check_manual_outcome_created_case():
    """check_manual_outcome 'created' case is True only when outcome == 'created'."""
    act = MagicMock()

    def cond(a):
        return a.process.outcome == "created"

    act.process.outcome = "created"
    assert cond(act) is True
    act.process.outcome = "denied"
    assert cond(act) is False


def test_check_manual_outcome_denied_case():
    """check_manual_outcome 'denied' case is True only when outcome == 'denied'."""
    act = MagicMock()

    def cond(a):
        return a.process.outcome == "denied"

    act.process.outcome = "denied"
    assert cond(act) is True
    act.process.outcome = "matched"
    assert cond(act) is False


# ---------------------------------------------------------------------------
# get_updated classmethod
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_updated_no_changes_returns_empty(user_factory):
    """get_updated returns {} when no MemberUpdate fields differ from the user."""
    from thetatauCMT.users.flows import MemberUpdateFlow
    from thetatauCMT.users.models import MemberUpdate

    user = user_factory.create()
    process = MemberUpdate(user=user)
    result = MemberUpdateFlow.get_updated(process, perform_update=False)
    assert result == {}


@pytest.mark.django_db
def test_get_updated_detects_changed_email(user_factory):
    """get_updated returns the 'email' key when process.email differs from user.email."""
    from thetatauCMT.users.flows import MemberUpdateFlow
    from thetatauCMT.users.models import MemberUpdate

    user = user_factory.create()
    process = MemberUpdate(user=user, email="changed@example.com")
    result = MemberUpdateFlow.get_updated(process, perform_update=False)
    assert "email" in result
    assert result["email"] == "changed@example.com"


@pytest.mark.django_db
def test_get_updated_no_user_returns_all_set_fields():
    """get_updated with user=None returns all non-falsy process fields."""
    from thetatauCMT.users.flows import MemberUpdateFlow
    from thetatauCMT.users.models import MemberUpdate

    process = MemberUpdate(user=None, first_name="Alice", last_name="Smith")
    result = MemberUpdateFlow.get_updated(process, perform_update=False)
    assert "first_name" in result
    assert "last_name" in result
    assert result["first_name"] == "Alice"


@pytest.mark.django_db
def test_get_updated_perform_update_true_saves_user(user_factory):
    """get_updated with perform_update=True applies changed fields to the user in the DB."""
    from thetatauCMT.users.flows import MemberUpdateFlow
    from thetatauCMT.users.models import MemberUpdate

    user = user_factory.create()
    new_email = "newaddr@example.com"
    process = MemberUpdate(user=user, email=new_email)
    MemberUpdateFlow.get_updated(process, perform_update=True)
    user.refresh_from_db()
    assert user.email == new_email


# ---------------------------------------------------------------------------
# email_delay_func handler
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_email_delay_func_sends_email(user_factory):
    """email_delay_func calls EmailProcessUpdate().send() for the process user."""
    from thetatauCMT.users.flows import MemberUpdateFlow

    user = user_factory.create()
    activation = MagicMock()
    activation.process.user = user
    activation.process.pk = 1

    with patch("thetatauCMT.users.flows.EmailProcessUpdate") as MockEmail:
        mock_instance = MagicMock()
        MockEmail.return_value = mock_instance
        with patch.object(MemberUpdateFlow, "get_updated", return_value={"email": "x@x.com"}):
            flow_instance = MemberUpdateFlow()
            flow_instance.email_delay_func(activation)
    mock_instance.send.assert_called_once()


# ---------------------------------------------------------------------------
# deny_notify_func handler
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_deny_notify_func_sets_approved_false_and_saves():
    """deny_notify_func sets process.approved = False and persists via save()."""
    from thetatauCMT.users.flows import MemberUpdateFlow

    activation = MagicMock()
    activation.process.email = "deny@example.com"
    activation.process.first_name = "Den"
    activation.process.last_name = "User"

    with patch("thetatauCMT.users.flows.EmailProcessUpdate") as MockEmail:
        MockEmail.return_value = MagicMock()
        with patch.object(MemberUpdateFlow, "get_updated", return_value={}):
            flow_instance = MemberUpdateFlow()
            flow_instance.deny_notify_func(activation)

    assert activation.process.approved is False
    activation.process.save.assert_called()


@pytest.mark.django_db
def test_deny_notify_func_sends_email():
    """deny_notify_func calls EmailProcessUpdate().send()."""
    from thetatauCMT.users.flows import MemberUpdateFlow

    activation = MagicMock()
    activation.process.email = "deny@example.com"
    activation.process.first_name = "Den"
    activation.process.last_name = "User"

    with patch("thetatauCMT.users.flows.EmailProcessUpdate") as MockEmail:
        mock_instance = MagicMock()
        MockEmail.return_value = mock_instance
        with patch.object(MemberUpdateFlow, "get_updated", return_value={}):
            flow_instance = MemberUpdateFlow()
            flow_instance.deny_notify_func(activation)
    mock_instance.send.assert_called_once()


# ---------------------------------------------------------------------------
# update_func handler
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_update_func_sends_email_when_user_exists(user_factory):
    """update_func calls EmailProcessUpdate().send() when process.user is set."""
    from thetatauCMT.users.flows import MemberUpdateFlow

    user = user_factory.create()
    activation = MagicMock()
    activation.process.user = user
    activation.process.outcome = "matched"

    with patch("thetatauCMT.users.flows.EmailProcessUpdate") as MockEmail:
        mock_instance = MagicMock()
        MockEmail.return_value = mock_instance
        with patch.object(MemberUpdateFlow, "get_updated", return_value={"email": "x@x.com"}):
            flow_instance = MemberUpdateFlow()
            flow_instance.update_func(activation)
    mock_instance.send.assert_called_once()


@pytest.mark.django_db
def test_update_func_no_email_when_user_is_none():
    """update_func does NOT call EmailProcessUpdate when process.user is None."""
    from thetatauCMT.users.flows import MemberUpdateFlow

    activation = MagicMock()
    activation.process.user = None
    activation.process.outcome = "matched"

    with patch("thetatauCMT.users.flows.EmailProcessUpdate") as MockEmail:
        with patch.object(MemberUpdateFlow, "get_updated", return_value={}):
            flow_instance = MemberUpdateFlow()
            flow_instance.update_func(activation)

    MockEmail.assert_not_called()
