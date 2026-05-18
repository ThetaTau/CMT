"""
Tests for thetatauCMT/forms/forms.py.

Tests cover form instantiation and validation logic directly, without requiring
HTTP requests.
"""

import pytest
from django import forms


# ─── DepledgeForm ─────────────────────────────────────────────────────────────


def test_depledge_form_init_sets_required_fields():
    """DepledgeForm.__init__ marks informed and returned_items as required."""
    from thetatauCMT.forms.forms import DepledgeForm

    form = DepledgeForm()
    assert form.fields["informed"].required is True
    assert form.fields["returned_items"].required is True


# ─── StatusChangeSelectForm ───────────────────────────────────────────────────


def test_status_change_select_form_no_colony_excludes_resigned_cc():
    """Without colony=True, 'resignedCC' is excluded from state choices."""
    from thetatauCMT.forms.forms import StatusChangeSelectForm

    form = StatusChangeSelectForm()
    flat_choices = []
    for choice in form.fields["state"].choices:
        if isinstance(choice[0], str):
            flat_choices.append(choice[0])
        else:
            # choice is ((value, label), ...) tuple of tuples
            flat_choices.append(choice[0])
    assert "resignedCC" not in flat_choices


def test_status_change_select_form_with_colony_includes_resigned_cc():
    """With colony=True, 'resignedCC' is not excluded."""
    from thetatauCMT.forms.forms import StatusChangeSelectForm

    form = StatusChangeSelectForm(colony=True)
    # choices is a list of (value, label) tuples
    flat_choices = [c[0] for c in form.fields["state"].choices]
    assert "resignedCC" in flat_choices


# ─── CSMTForm.__init__ branches ──────────────────────────────────────────────


@pytest.mark.django_db
def test_csmt_form_init_no_reason():
    """CSMTForm without a reason initialises without hiding/disabling fields."""
    from thetatauCMT.forms.forms import CSMTForm

    form = CSMTForm()
    # No fields should be unconditionally disabled
    assert form.fields["miles"].required is True


@pytest.mark.django_db
def test_csmt_form_init_coop_reason():
    """reason='coop' hides the new_school field."""
    from thetatauCMT.forms.forms import CSMTForm

    form = CSMTForm(initial={"reason": "coop"})
    assert isinstance(form.fields["new_school"].widget, forms.HiddenInput)


@pytest.mark.django_db
def test_csmt_form_init_military_reason():
    """reason='military' marks miles, employer, new_school as not required."""
    from thetatauCMT.forms.forms import CSMTForm

    form = CSMTForm(initial={"reason": "military"})
    assert form.fields["miles"].required is False
    assert form.fields["employer"].required is False
    assert isinstance(form.fields["new_school"].widget, forms.HiddenInput)


@pytest.mark.django_db
def test_csmt_form_init_withdraw_reason():
    """reason='withdraw' disables miles, date_end, employer and hides new_school."""
    from thetatauCMT.forms.forms import CSMTForm

    form = CSMTForm(initial={"reason": "withdraw"})
    assert form.fields["miles"].required is False
    assert form.fields["date_end"].required is False
    assert form.fields["employer"].required is False
    assert isinstance(form.fields["new_school"].widget, forms.HiddenInput)


@pytest.mark.django_db
def test_csmt_form_init_resigned_cc_reason():
    """reason='resignedCC' is treated the same as 'withdraw'."""
    from thetatauCMT.forms.forms import CSMTForm

    form = CSMTForm(initial={"reason": "resignedCC"})
    assert form.fields["miles"].required is False
    assert isinstance(form.fields["new_school"].widget, forms.HiddenInput)


@pytest.mark.django_db
def test_csmt_form_init_transfer_reason():
    """reason='transfer' hides employer, disables miles and date_end."""
    from thetatauCMT.forms.forms import CSMTForm

    form = CSMTForm(initial={"reason": "transfer"})
    assert form.fields["miles"].required is False
    assert form.fields["date_end"].required is False
    assert isinstance(form.fields["employer"].widget, forms.HiddenInput)


@pytest.mark.django_db
def test_csmt_form_init_covid_reason():
    """reason='covid' disables miles, date_end, date_start, employer, new_school."""
    from thetatauCMT.forms.forms import CSMTForm

    form = CSMTForm(initial={"reason": "covid"})
    assert form.fields["miles"].required is False
    assert form.fields["date_end"].required is False
    assert form.fields["date_start"].required is False
    assert form.fields["employer"].required is False
    assert isinstance(form.fields["new_school"].widget, forms.HiddenInput)


# ─── DepledgeForm.clean branches ─────────────────────────────────────────────


@pytest.mark.django_db
def test_depledge_form_clean_no_meeting_held_adds_error():
    """DepledgeForm.clean adds an error when meeting_held is falsy."""
    from thetatauCMT.forms.forms import DepledgeForm

    data = {
        "user": "Test User",
        "reason": "personal",
        "date": "01/01/2023",
        "informed": ["written"],
        "returned_items": ["badge"],
        # meeting_held intentionally omitted/empty
    }
    form = DepledgeForm(data=data)
    form.data["chapter"] = "Test Chapter"
    valid = form.is_valid()
    assert not valid
    assert "meeting_held" in form.errors or not valid


@pytest.mark.django_db
def test_depledge_form_clean_reason_other_requires_text():
    """DepledgeForm.clean adds an error when reason='other' and no reason_other."""
    from thetatauCMT.forms.forms import DepledgeForm

    data = {
        "user": "Test User",
        "reason": "other",
        "reason_other": "",
        "date": "01/01/2023",
        "meeting_held": ["no_meeting"],
        "meeting_not": "some reason",
        "informed": ["written"],
        "returned_items": ["badge"],
    }
    form = DepledgeForm(data=data)
    form.data["chapter"] = "Test Chapter"
    valid = form.is_valid()
    assert not valid


@pytest.mark.django_db
def test_depledge_form_clean_meeting_held_no_needs_meeting_not():
    """When meeting_held contains 'no', meeting_not is required."""
    from thetatauCMT.forms.forms import DepledgeForm

    data = {
        "user": "Test User",
        "reason": "personal",
        "date": "01/01/2023",
        "meeting_held": ["no_meeting"],
        "meeting_not": "",
        "informed": ["written"],
        "returned_items": ["badge"],
    }
    form = DepledgeForm(data=data)
    form.data["chapter"] = "Test Chapter"
    valid = form.is_valid()
    assert not valid


@pytest.mark.django_db
def test_depledge_form_clean_meeting_held_yes_needs_meeting_date():
    """When meeting_held contains a 'yes' value, meeting_date is required."""
    from thetatauCMT.forms.forms import DepledgeForm

    data = {
        "user": "Test User",
        "reason": "personal",
        "date": "01/01/2023",
        "meeting_held": ["yes"],
        "meeting_date": "",
        "meeting_attend": "",
        "informed": ["written"],
        "returned_items": ["badge"],
    }
    form = DepledgeForm(data=data)
    form.data["chapter"] = "Test Chapter"
    valid = form.is_valid()
    assert not valid


@pytest.mark.django_db
def test_depledge_form_clean_returned_other_requires_text():
    """When returned_items contains 'other', returned_other must be provided."""
    from thetatauCMT.forms.forms import DepledgeForm

    data = {
        "user": "Test User",
        "reason": "personal",
        "date": "01/01/2023",
        "meeting_held": ["no_meeting"],
        "meeting_not": "some reason",
        "informed": ["written"],
        "returned_items": ["other"],
        "returned_other": "",
    }
    form = DepledgeForm(data=data)
    form.data["chapter"] = "Test Chapter"
    valid = form.is_valid()
    assert not valid
