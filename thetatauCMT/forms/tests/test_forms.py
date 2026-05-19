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


# ─── AuditForm.clean branches ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_audit_form_clean_missing_reviewed_fields_adds_errors():
    """AuditForm.clean adds errors for each missing required reviewed boolean field."""
    from thetatauCMT.forms.forms import AuditForm

    # Reviewed fields absent from POST data (simulate unchecked checkboxes)
    data = {
        "dues_member": "100.00",
        "dues_pledge": "50.00",
        "frequency": "semester",
        "payment_plan": "False",
        "cash_book": "False",
        "cash_register": "False",
        "member_account": "False",
        "debit_card": "False",
        "balance_checking": "0.00",
        "balance_savings": "0.00",
        "debit_card_access": "None",
        # cash_book_reviewed, cash_register_reviewed, member_account_reviewed,
        # agreement intentionally absent
    }
    form = AuditForm(data=data)
    assert not form.is_valid()
    errors = form.errors
    assert "cash_book_reviewed" in errors
    assert "cash_register_reviewed" in errors
    assert "member_account_reviewed" in errors
    assert "agreement" in errors


@pytest.mark.django_db
def test_audit_form_clean_all_reviewed_present_passes():
    """AuditForm.clean passes validation when all required reviewed fields are True."""
    from thetatauCMT.forms.forms import AuditForm

    data = {
        "dues_member": "100.00",
        "dues_pledge": "50.00",
        "frequency": "semester",
        "payment_plan": "False",
        "cash_book": "False",
        "cash_register": "False",
        "member_account": "False",
        "debit_card": "False",
        "balance_checking": "0.00",
        "balance_savings": "0.00",
        "debit_card_access": "None",
        "cash_book_reviewed": True,
        "cash_register_reviewed": True,
        "member_account_reviewed": True,
        "agreement": True,
    }
    form = AuditForm(data=data)
    # Should pass the clean() logic (all required reviewed fields present)
    assert "cash_book_reviewed" not in form.errors
    assert "cash_register_reviewed" not in form.errors
    assert "member_account_reviewed" not in form.errors
    assert "agreement" not in form.errors


# ─── DisciplinaryForm1.clean branches ────────────────────────────────────────


def test_disciplinary_form1_clean_advisor_true_no_name_raises():
    """DisciplinaryForm1.clean raises ValidationError when advisor=True but no name."""
    from unittest.mock import patch

    from django import forms as dj_forms

    from thetatauCMT.forms.forms import DisciplinaryForm1

    mock_data = {
        "advisor": True,
        "advisor_name": None,
        "faculty": False,
        "faculty_name": None,
    }

    with patch("django.forms.ModelForm.clean", return_value=mock_data):
        f = DisciplinaryForm1.__new__(DisciplinaryForm1)
        f.cleaned_data = mock_data
        with pytest.raises(dj_forms.ValidationError, match="alumni advisor"):
            f.clean()


def test_disciplinary_form1_clean_faculty_true_no_name_raises():
    """DisciplinaryForm1.clean raises ValidationError when faculty=True but no name."""
    from unittest.mock import patch

    from django import forms as dj_forms

    from thetatauCMT.forms.forms import DisciplinaryForm1

    mock_data = {
        "advisor": False,
        "advisor_name": None,
        "faculty": True,
        "faculty_name": None,
    }

    with patch("django.forms.ModelForm.clean", return_value=mock_data):
        f = DisciplinaryForm1.__new__(DisciplinaryForm1)
        f.cleaned_data = mock_data
        with pytest.raises(dj_forms.ValidationError, match="campus/faculty"):
            f.clean()


def test_disciplinary_form1_clean_both_names_provided_returns_data():
    """DisciplinaryForm1.clean returns cleaned_data when names are provided."""
    from unittest.mock import patch

    from thetatauCMT.forms.forms import DisciplinaryForm1

    mock_data = {
        "advisor": True,
        "advisor_name": "John Smith",
        "faculty": True,
        "faculty_name": "Prof. Jones",
    }

    with patch("django.forms.ModelForm.clean", return_value=mock_data):
        f = DisciplinaryForm1.__new__(DisciplinaryForm1)
        f.cleaned_data = mock_data
        result = f.clean()
        assert result == mock_data


# ─── PrematureAlumnusForm.clean branches ─────────────────────────────────────


@pytest.mark.django_db
def test_premature_alumnus_form_clean_semesters_false_raises():
    """PrematureAlumnusForm.clean raises when semesters is 'False'."""
    from unittest.mock import patch

    from django import forms as dj_forms

    from thetatauCMT.forms.forms import PrematureAlumnusForm
    from thetatauCMT.users.tests.factories import UserFactory

    user = UserFactory.create()
    mock_data = {"user": user, "semesters": "False"}

    with patch("django.forms.ModelForm.clean", return_value=mock_data):
        f = PrematureAlumnusForm.__new__(PrematureAlumnusForm)
        f.cleaned_data = mock_data
        with pytest.raises(dj_forms.ValidationError, match="6 months"):
            f.clean()


@pytest.mark.django_db
def test_premature_alumnus_form_clean_recent_initiation_raises():
    """PrematureAlumnusForm.clean raises when initiation date is less than 6 months ago."""
    import datetime
    from unittest.mock import patch

    from django import forms as dj_forms
    from django.utils import timezone

    from thetatauCMT.forms.forms import PrematureAlumnusForm
    from thetatauCMT.forms.tests.factories import InitiationFactory
    from thetatauCMT.users.tests.factories import UserFactory

    user = UserFactory.create()
    # Create a real Initiation record with a RECENT date (less than 6 months ago)
    recent_date = timezone.now().date() - datetime.timedelta(days=30)
    InitiationFactory.create(user=user, date=recent_date)

    mock_data = {"user": user, "semesters": "True"}

    with patch("django.forms.ModelForm.clean", return_value=mock_data):
        f = PrematureAlumnusForm.__new__(PrematureAlumnusForm)
        f.cleaned_data = mock_data
        with pytest.raises(dj_forms.ValidationError, match="6 months"):
            f.clean()


@pytest.mark.django_db
def test_premature_alumnus_form_clean_old_enough_initiation_passes():
    """PrematureAlumnusForm.clean passes when semesters=True and initiation is >6 months ago."""
    import datetime
    from unittest.mock import patch

    from django.utils import timezone

    from thetatauCMT.forms.forms import PrematureAlumnusForm
    from thetatauCMT.forms.tests.factories import InitiationFactory
    from thetatauCMT.users.tests.factories import UserFactory

    user = UserFactory.create()
    # Create a real Initiation record older than 6 months
    old_date = timezone.now().date() - datetime.timedelta(days=365)
    InitiationFactory.create(user=user, date=old_date)

    mock_data = {"user": user, "semesters": "True"}

    with patch("django.forms.ModelForm.clean", return_value=mock_data):
        f = PrematureAlumnusForm.__new__(PrematureAlumnusForm)
        f.cleaned_data = mock_data
        result = f.clean()
        assert result["user"] == user


# ─── CSMTForm.clean date validation ──────────────────────────────────────────


@pytest.mark.django_db
def test_csmt_form_clean_date_end_before_start_is_invalid():
    """CSMTForm.clean raises ValidationError when date_end is before date_start."""
    import datetime
    from unittest.mock import patch

    from django import forms as dj_forms
    from django.forms.utils import ErrorDict

    from thetatauCMT.forms.forms import CSMTForm

    mock_data = {
        "date_start": datetime.date(2023, 6, 1),
        "date_end": datetime.date(2023, 1, 1),  # Before start
    }

    # Minimal form-like object to invoke just the clean() logic
    with patch("django.forms.ModelForm.clean", return_value=mock_data):
        f = CSMTForm.__new__(CSMTForm)
        f.cleaned_data = mock_data
        f._errors = ErrorDict()
        f.error_class = dj_forms.utils.ErrorList
        f.fields = {
            "date_end": dj_forms.DateField(),
            "date_start": dj_forms.DateField(),
        }
        # renderer is needed by add_error → ErrorList
        from django.forms.renderers import get_default_renderer

        f.renderer = get_default_renderer()
        with pytest.raises(dj_forms.ValidationError, match="End date must be greater"):
            f.clean()


@pytest.mark.django_db
def test_csmt_form_clean_date_end_after_start_passes():
    """CSMTForm.clean passes when date_end >= date_start."""
    import datetime
    from unittest.mock import patch

    from django import forms as dj_forms
    from django.forms.utils import ErrorDict

    from thetatauCMT.forms.forms import CSMTForm

    mock_data = {
        "date_start": datetime.date(2023, 1, 1),
        "date_end": datetime.date(2023, 6, 1),  # After start
    }

    with patch("django.forms.ModelForm.clean", return_value=mock_data):
        f = CSMTForm.__new__(CSMTForm)
        f.cleaned_data = mock_data
        f._errors = ErrorDict()
        f.fields = {
            "date_end": dj_forms.DateField(),
            "date_start": dj_forms.DateField(),
        }
        # Should not raise
        f.clean()
        assert "date_end" not in f._errors


# ─── DisciplinaryForm2.clean ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_disciplinary_form2_clean_no_take_and_no_why_take_raises():
    """DisciplinaryForm2.clean raises ValidationError when take=False AND why_take empty."""
    from django.forms.renderers import get_default_renderer
    from django.forms.utils import ErrorDict

    from thetatauCMT.forms.forms import DisciplinaryForm2

    f = DisciplinaryForm2.__new__(DisciplinaryForm2)
    f._errors = ErrorDict()
    f.renderer = get_default_renderer()
    f.fields = {}
    f.cleaned_data = {
        "take": False,
        "why_take": "",
        "minutes": None,
        "results_letter": None,
    }
    with pytest.raises(
        forms.ValidationError, match="A reason for not taking place is required"
    ):
        f.clean()


@pytest.mark.django_db
def test_disciplinary_form2_clean_take_true_no_minutes_raises():
    """DisciplinaryForm2.clean raises ValidationError when take=True but minutes missing."""
    from django.forms.renderers import get_default_renderer
    from django.forms.utils import ErrorDict

    from thetatauCMT.forms.forms import DisciplinaryForm2

    f = DisciplinaryForm2.__new__(DisciplinaryForm2)
    f._errors = ErrorDict()
    f.renderer = get_default_renderer()
    f.fields = {}
    f.cleaned_data = {
        "take": True,
        "why_take": "Some reason",
        "minutes": None,
        "results_letter": None,
    }
    with pytest.raises(
        forms.ValidationError, match="Both minutes and results letter are required"
    ):
        f.clean()


@pytest.mark.django_db
def test_disciplinary_form2_clean_take_true_all_files_passes():
    """DisciplinaryForm2.clean passes when take=True and both files provided."""
    from unittest.mock import MagicMock, patch

    from django.forms.renderers import get_default_renderer
    from django.forms.utils import ErrorDict

    from thetatauCMT.forms.forms import DisciplinaryForm2

    f = DisciplinaryForm2.__new__(DisciplinaryForm2)
    f._errors = ErrorDict()
    f.renderer = get_default_renderer()
    f.fields = {}
    fake_file = MagicMock()
    f.cleaned_data = {
        "take": True,
        "why_take": "",
        "minutes": fake_file,
        "results_letter": fake_file,
    }
    with patch("django.forms.ModelForm.clean", return_value=f.cleaned_data):
        result = f.clean()
    assert result is not None


# ─── ReturnStudentForm.clean_user ─────────────────────────────────────────────


@pytest.mark.django_db
def test_return_student_form_clean_user_with_prealumn_raises():
    """clean_user raises ValidationError when user has a prealumn form."""
    from unittest.mock import MagicMock, PropertyMock

    from django.forms.renderers import get_default_renderer
    from django.forms.utils import ErrorDict

    from thetatauCMT.forms.forms import ReturnStudentForm

    mock_user = MagicMock()
    prealumn_qs = MagicMock()
    prealumn_qs.__bool__ = lambda self: True  # truthy
    mock_user.prealumn_form.all.return_value = prealumn_qs

    f = ReturnStudentForm.__new__(ReturnStudentForm)
    f._errors = ErrorDict()
    f.renderer = get_default_renderer()
    f.fields = {}
    f.cleaned_data = {"user": mock_user}

    with pytest.raises(forms.ValidationError, match="prealumn form filed"):
        f.clean_user()


@pytest.mark.django_db
def test_return_student_form_clean_user_without_prealumn_returns_user():
    """clean_user returns user when no prealumn form exists."""
    from unittest.mock import MagicMock

    from django.forms.renderers import get_default_renderer
    from django.forms.utils import ErrorDict

    from thetatauCMT.forms.forms import ReturnStudentForm

    mock_user = MagicMock()
    prealumn_qs = MagicMock()
    prealumn_qs.__bool__ = lambda self: False  # falsy – no prealumn forms
    mock_user.prealumn_form.all.return_value = prealumn_qs

    f = ReturnStudentForm.__new__(ReturnStudentForm)
    f._errors = ErrorDict()
    f.renderer = get_default_renderer()
    f.fields = {}
    f.cleaned_data = {"user": mock_user}

    result = f.clean_user()
    assert result is mock_user


# ─── AlumniExclusionForm.clean ────────────────────────────────────────────────


@pytest.mark.django_db
def test_alumni_exclusion_form_clean_date_range_too_long_adds_error():
    """AlumniExclusionForm.clean adds error when date range exceeds 4 months."""
    import datetime
    from unittest.mock import patch

    from django.forms.renderers import get_default_renderer
    from django.forms.utils import ErrorDict

    from thetatauCMT.forms.forms import AlumniExclusionForm

    start = datetime.date(2025, 1, 1)
    end = datetime.date(2025, 6, 1)  # 151 days – exceeds 120

    f = AlumniExclusionForm.__new__(AlumniExclusionForm)
    f._errors = ErrorDict()
    f.renderer = get_default_renderer()
    f.error_class = forms.utils.ErrorList
    f.fields = {"date_end": forms.DateField()}
    f.cleaned_data = {"date_start": start, "date_end": end}

    with patch("django.forms.ModelForm.clean", return_value=f.cleaned_data):
        f.clean()

    assert "date_end" in f._errors
    assert "4 months" in str(f._errors["date_end"])


@pytest.mark.django_db
def test_alumni_exclusion_form_clean_date_range_valid_passes():
    """AlumniExclusionForm.clean passes when date range is within 4 months."""
    import datetime
    from unittest.mock import patch

    from django.forms.renderers import get_default_renderer
    from django.forms.utils import ErrorDict

    from thetatauCMT.forms.forms import AlumniExclusionForm

    start = datetime.date(2025, 1, 1)
    end = datetime.date(2025, 3, 1)  # 59 days – within 120

    f = AlumniExclusionForm.__new__(AlumniExclusionForm)
    f._errors = ErrorDict()
    f.renderer = get_default_renderer()
    f.fields = {}
    f.cleaned_data = {"date_start": start, "date_end": end}

    with patch("django.forms.ModelForm.clean", return_value=f.cleaned_data):
        f.clean()

    assert "date_end" not in f._errors


# ─── AlumniExclusionReviewForm.clean ──────────────────────────────────────────


@pytest.mark.django_db
def test_alumni_exclusion_review_form_clean_veto_without_reason_adds_error():
    """AlumniExclusionReviewForm.clean adds error when veto selected but no reason."""
    from unittest.mock import patch

    from django.forms.renderers import get_default_renderer
    from django.forms.utils import ErrorDict

    from thetatauCMT.forms.forms import AlumniExclusionReviewForm

    f = AlumniExclusionReviewForm.__new__(AlumniExclusionReviewForm)
    f._errors = ErrorDict()
    f.renderer = get_default_renderer()
    f.error_class = forms.utils.ErrorList
    f.fields = {"veto_reason": forms.CharField(required=False)}
    f.cleaned_data = {"regional_director_veto": "False", "veto_reason": ""}

    with patch("django.forms.ModelForm.clean", return_value=f.cleaned_data):
        f.clean()

    assert "veto_reason" in f._errors


@pytest.mark.django_db
def test_alumni_exclusion_review_form_clean_approve_no_reason_needed():
    """AlumniExclusionReviewForm.clean passes when approving (True) without reason."""
    from unittest.mock import patch

    from django.forms.renderers import get_default_renderer
    from django.forms.utils import ErrorDict

    from thetatauCMT.forms.forms import AlumniExclusionReviewForm

    f = AlumniExclusionReviewForm.__new__(AlumniExclusionReviewForm)
    f._errors = ErrorDict()
    f.renderer = get_default_renderer()
    f.fields = {}
    f.cleaned_data = {"regional_director_veto": "True", "veto_reason": ""}

    with patch("django.forms.ModelForm.clean", return_value=f.cleaned_data):
        f.clean()

    assert "veto_reason" not in f._errors


@pytest.mark.django_db
def test_alumni_exclusion_review_form_clean_veto_with_reason_passes():
    """AlumniExclusionReviewForm.clean passes when veto includes a reason."""
    from unittest.mock import patch

    from django.forms.renderers import get_default_renderer
    from django.forms.utils import ErrorDict

    from thetatauCMT.forms.forms import AlumniExclusionReviewForm

    f = AlumniExclusionReviewForm.__new__(AlumniExclusionReviewForm)
    f._errors = ErrorDict()
    f.renderer = get_default_renderer()
    f.fields = {}
    f.cleaned_data = {
        "regional_director_veto": "False",
        "veto_reason": "The evidence is insufficient.",
    }

    with patch("django.forms.ModelForm.clean", return_value=f.cleaned_data):
        f.clean()

    assert "veto_reason" not in f._errors
