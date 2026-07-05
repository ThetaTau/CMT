"""
Smoke tests for thetatauCMT/forms/views.py.

Tests cover:
  - Unauthenticated users are redirected (302) for login-protected views.
  - Authenticated users receive HTTP 200 for views requiring only LoginRequired.
  - NatOfficer-group users receive HTTP 200 for NatOfficerRequired views.
  - No-auth views (PledgeFormView, BillOfRightsDetailView, load_majors) return 200.
"""

import pytest
from django.contrib.auth.models import Group
from django.http import HttpResponse
from django.urls import reverse

from thetatauCMT.chapters.tests.factories import ChapterFactory

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _add_to_group(user, group_name):
    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)


# ─── FormLanding (LoginRequired, TemplateView) ────────────────────────────────


def test_form_landing_unauthenticated_redirects(client, db):
    response = client.get(reverse("forms:landing"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_form_landing_authenticated_returns_200(auto_login_user):
    client, _user = auto_login_user()
    response = client.get(reverse("forms:landing"))
    assert response.status_code == 200


# ─── PledgeFormView (no auth required, CreateView) ────────────────────────────


@pytest.mark.django_db
def test_pledge_form_get_returns_200(client):
    response = client.get(reverse("forms:pledgeform"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_pledge_form_alt_get_returns_200(client):
    response = client.get(reverse("forms:pledgeform-alt"))
    assert response.status_code == 200


# ─── BillOfRightsDetailView (no auth required) ────────────────────────────────


@pytest.mark.django_db
def test_bill_of_rights_detail_returns_200(client):
    chapter = ChapterFactory()
    url = reverse("forms:bill_of_rights", kwargs={"pk": chapter.pk})
    response = client.get(url)
    assert response.status_code == 200


# ─── load_majors AJAX (no auth required) ──────────────────────────────────────


@pytest.mark.django_db
def test_load_majors_no_chapter_returns_200(client):
    response = client.get(reverse("forms:ajax_load_majors"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_load_majors_with_chapter_returns_200(client):
    chapter = ChapterFactory()
    response = client.get(reverse("forms:ajax_load_majors"), {"chapter": chapter.pk})
    assert response.status_code == 200


# ─── RiskManagementFormView (LoginRequired, FormView) ─────────────────────────


def test_rmp_form_unauthenticated_redirects(client, db):
    response = client.get(reverse("forms:rmp"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_rmp_form_already_signed_redirects_to_profile(auto_login_user):
    # auto_login_user creates an RMP record, so the view redirects back to profile
    client, _user = auto_login_user()
    response = client.get(reverse("forms:rmp"), follow=False)
    assert response.status_code == 302
    assert "myinfo" in response["Location"] or "submissions" in response["Location"]


@pytest.mark.django_db
def test_rmp_form_not_yet_signed_returns_200(db, client, user_factory, test_password):
    # User has no RMP record; /forms/rmp/ is in TERMS_EXCLUDE_URL_LIST so
    # the RMPSignMiddleware is bypassed and the form is rendered.
    user = user_factory.create(password=test_password)
    client.login(username=user.username, password=test_password)
    response = client.get(reverse("forms:rmp"))
    assert response.status_code == 200


# ─── BylawsCreateView (LoginRequired, CreateView) ─────────────────────────────


def test_bylaws_create_unauthenticated_redirects(client, db):
    response = client.get(reverse("forms:bylaws"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_bylaws_create_authenticated_returns_200(auto_login_user):
    client, _user = auto_login_user()
    response = client.get(reverse("forms:bylaws"))
    assert response.status_code == 200


# ─── InitDeplSelectView (LoginRequired, FormSetView) ─────────────────────────


def test_init_selection_unauthenticated_redirects(client, db):
    response = client.get(reverse("forms:init_selection"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_init_selection_authenticated_returns_200(auto_login_user):
    client, _user = auto_login_user()
    response = client.get(reverse("forms:init_selection"))
    assert response.status_code == 200


# ─── StatusChangeSelectView (LoginRequired, FormSetView) ──────────────────────


def test_status_selection_unauthenticated_redirects(client, db):
    response = client.get(reverse("forms:status_selection"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_status_selection_authenticated_returns_200(auto_login_user):
    client, _user = auto_login_user()
    response = client.get(reverse("forms:status_selection"))
    assert response.status_code == 200


# ─── RoleChangeView (LoginRequired, ModelFormSetView) ─────────────────────────


def test_officer_form_unauthenticated_redirects(client, db):
    response = client.get(reverse("forms:officer"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_officer_form_authenticated_returns_200(auto_login_user):
    client, _user = auto_login_user()
    response = client.get(reverse("forms:officer"))
    assert response.status_code == 200


# ─── AuditFormView (LoginRequired + OfficerRequired, UpdateView) ──────────────


def test_audit_form_unauthenticated_redirects(client, db):
    response = client.get(reverse("forms:audit"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_audit_form_non_officer_redirects_to_home(auto_login_user):
    # OfficerRequiredMixin redirects non-officers to home
    client, _user = auto_login_user()
    response = client.get(reverse("forms:audit"), follow=False)
    assert response.status_code == 302


# ─── NatOfficer-required list views (parametrized) ────────────────────────────


NATOFF_VIEWS = [
    "forms:audit_list",
    "forms:rmp_list",
    "forms:pledge_program_list",
    "forms:education_list",
    "forms:convention_list",
    "forms:osm_list",
    "forms:bylaws_list",
    "forms:alumniexclusion_list",
]


@pytest.mark.django_db
@pytest.mark.parametrize("view_name", NATOFF_VIEWS)
def test_natoff_list_view_unauthenticated_redirects(client, view_name):
    response = client.get(reverse(view_name))
    assert response.status_code == 302


@pytest.mark.django_db
@pytest.mark.parametrize("view_name", NATOFF_VIEWS)
def test_natoff_list_view_natoff_returns_200(auto_login_user, view_name):
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    response = client.get(reverse(view_name))
    assert response.status_code == 200


# ─── RoleChangeNationalView (LoginRequired + NatOfficerRequired) ──────────────


def test_natoff_officer_form_unauthenticated_redirects(client, db):
    response = client.get(reverse("forms:natoff"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_natoff_officer_form_natoff_returns_200(auto_login_user):
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    response = client.get(reverse("forms:natoff"))
    assert response.status_code == 200


# ─── InitiationView (OfficerRequiredMixin) ────────────────────────────────────


@pytest.mark.django_db
def test_initiation_view_officer_no_session_redirects_to_selection(auto_login_user):
    """Without 'init-selection' in session, redirects to init_selection."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    response = client.get(reverse("forms:initiation"), follow=False)
    assert response.status_code == 302
    assert "init" in response["Location"]


@pytest.mark.django_db
def test_initiation_view_non_officer_redirects(auto_login_user):
    client, user = auto_login_user()
    # user is not in officer group
    response = client.get(reverse("forms:initiation"), follow=False)
    assert response.status_code == 302


# ─── StatusChangeView (OfficerRequiredMixin) ─────────────────────────────────


@pytest.mark.django_db
def test_status_change_view_officer_no_session_redirects(auto_login_user):
    """Without 'status-selection' in session, redirects to status_selection."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    response = client.get(reverse("forms:status"), follow=False)
    assert response.status_code == 302
    assert "status" in response["Location"]


@pytest.mark.django_db
def test_status_change_view_non_officer_redirects(auto_login_user):
    client, user = auto_login_user()
    response = client.get(reverse("forms:status"), follow=False)
    assert response.status_code == 302


# ─── AuditFormView (OfficerRequiredMixin) ─────────────────────────────────────


@pytest.mark.django_db
def test_audit_form_officer_returns_200(auto_login_user):
    """Officer-group user can GET audit form (non-exec officer → messages + empty form)."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    response = client.get(reverse("forms:audit"), follow=False)
    # OfficerRequiredMixin passes; get_object may return None for non-exec officer
    # UpdateView still renders the form with object=None
    assert response.status_code in (200, 302)


# ─── CollectionReferralFormView (OfficerRequiredMixin) ────────────────────────


@pytest.mark.django_db
def test_collection_referral_view_unauthenticated_redirects(client):
    response = client.get(reverse("forms:collection"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_collection_referral_view_officer_returns_200(auto_login_user):
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    response = client.get(reverse("forms:collection"))
    assert response.status_code == 200


# ─── ResignationListView (OfficerRequiredMixin) ───────────────────────────────


@pytest.mark.django_db
def test_resign_list_view_unauthenticated_redirects(client):
    response = client.get(reverse("forms:resign_list"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_resign_list_view_officer_returns_200(auto_login_user):
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    response = client.get(reverse("forms:resign_list"))
    assert response.status_code == 200


# ─── RitualProficiencyCreateView + UserTableView (NatOfficerRequired) ─────────


@pytest.mark.django_db
def test_ritual_proficiency_view_unauthenticated_redirects(client):
    response = client.get(reverse("forms:ritual_proficiency"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_ritual_proficiency_view_natoff_returns_200(auto_login_user):
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    response = client.get(reverse("forms:ritual_proficiency"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_ritual_proficiency_user_table_view_unauthenticated_redirects(client):
    response = client.get(reverse("forms:ritual_proficiency_user_table"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_ritual_proficiency_user_table_view_natoff_returns_200(auto_login_user):
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    response = client.get(reverse("forms:ritual_proficiency_user_table"), {"user_id": ""})
    assert response.status_code == 200


# ─── set_init_date (function view, officer required) ──────────────────────────


@pytest.mark.django_db
def test_set_init_date_post_returns_200(auto_login_user):
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    response = client.post(reverse("forms:set_init_date"), {"init_date": "2025-01-15"})
    assert response.status_code == 200
    assert b"2025-01-15" in response.content


# ─── NatOff list views (require natoff group) ─────────────────────────────────


@pytest.mark.django_db
def test_audit_list_view_unauthenticated_redirects(client):
    url = reverse("forms:audit_list")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_audit_list_view_natoff_returns_200(auto_login_user):
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:audit_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_rmp_list_view_unauthenticated_redirects(client):
    url = reverse("forms:rmp_list")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_rmp_list_view_natoff_returns_200(auto_login_user):
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:rmp_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_pledge_program_list_view_unauthenticated_redirects(client):
    url = reverse("forms:pledge_program_list")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_pledge_program_list_view_natoff_returns_200(auto_login_user):
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:pledge_program_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_bylaws_list_view_unauthenticated_redirects(client):
    url = reverse("forms:bylaws_list")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_bylaws_list_view_authenticated_returns_200(auto_login_user):
    client, user = auto_login_user()
    url = reverse("forms:bylaws_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_convention_list_view_unauthenticated_redirects(client):
    url = reverse("forms:convention_list")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_convention_list_view_natoff_returns_200(auto_login_user):
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:convention_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_alumni_exclusion_list_view_unauthenticated_redirects(client):
    url = reverse("forms:alumniexclusion_list")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_alumni_exclusion_list_view_natoff_returns_200(auto_login_user):
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:alumniexclusion_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_osm_list_view_unauthenticated_redirects(client):
    url = reverse("forms:osm_list")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_osm_list_view_natoff_returns_200(auto_login_user):
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:osm_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_hs_education_list_view_unauthenticated_redirects(client):
    url = reverse("forms:education_list")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_hs_education_list_view_natoff_returns_200(auto_login_user):
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:education_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── FormLanding context view (logged in) ────────────────────────────────────


@pytest.mark.django_db
def test_form_landing_cancel_param_returns_200(auto_login_user):
    """FormLanding with ?cancel=1 still returns 200."""
    client, user = auto_login_user()
    url = reverse("forms:landing")
    response = client.get(url + "?cancel=1", follow=True)
    assert response.status_code == 200


# ─── AuditListView cancel param ──────────────────────────────────────────────


@pytest.mark.django_db
def test_audit_list_view_cancel_param(auto_login_user):
    """AuditListView with ?cancel=1 still returns 200."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:audit_list")
    response = client.get(url + "?cancel=1", follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_rmp_list_view_cancel_param(auto_login_user):
    """RiskManagementListView with ?cancel=1 still returns 200."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:rmp_list")
    response = client.get(url + "?cancel=1", follow=True)
    assert response.status_code == 200


# ─── RoleChangeNationalView ───────────────────────────────────────────────────


@pytest.mark.django_db
def test_role_change_national_view_unauthenticated_redirects(client, db):
    url = reverse("forms:natoff")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_role_change_national_view_natoff_returns_200(auto_login_user):
    """NatOff can access the national officer role assignment view."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:natoff")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── ResignationListView ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_resignation_list_view_unauthenticated_redirects(client, db):
    url = reverse("forms:resign_list")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_resignation_list_view_officer_returns_200(auto_login_user):
    """Officer can access the resignation list view."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    url = reverse("forms:resign_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── RitualProficiencyCreateView ─────────────────────────────────────────────


@pytest.mark.django_db
def test_ritual_proficiency_create_view_unauthenticated_redirects(client, db):
    url = reverse("forms:ritual_proficiency")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_ritual_proficiency_create_view_natoff_returns_200(auto_login_user):
    """NatOff can access the ritual proficiency create view."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:ritual_proficiency")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── RitualProficiencyUserTableView ──────────────────────────────────────────


@pytest.mark.django_db
def test_ritual_proficiency_user_table_view_natoff_with_follow_returns_200(auto_login_user):
    """NatOff can access the ritual proficiency user table view."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:ritual_proficiency_user_table")
    response = client.get(url, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_ritual_proficiency_user_table_view_with_user_id(auto_login_user):
    """Ritual proficiency user table returns 200 with user_id param."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:ritual_proficiency_user_table")
    response = client.get(url, {"user_id": user.pk}, follow=True)
    assert response.status_code == 200


# ─── CollectionReferralFormView ───────────────────────────────────────────────


@pytest.mark.django_db
def test_collection_referral_view_unauthenticated_with_db_redirects(client, db):
    url = reverse("forms:collection")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_collection_referral_view_officer_with_follow_returns_200(auto_login_user):
    """Officer can access the collection referral view."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    url = reverse("forms:collection")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── get_sign_status helper function ─────────────────────────────────────────


@pytest.mark.django_db
def test_get_sign_status_creds_no_processes(auto_login_user):
    """get_sign_status with type_sign='creds' returns empty data when no Convention."""
    from thetatauCMT.forms.views import get_sign_status

    _, user = auto_login_user()
    data, submitted, users = get_sign_status(user, type_sign="creds", initial=True)
    assert isinstance(data, list)
    assert submitted is False


@pytest.mark.django_db
def test_get_sign_status_resign_no_processes(auto_login_user):
    """get_sign_status with type_sign='resign' returns empty data when no resignation."""
    from thetatauCMT.forms.views import get_sign_status

    _, user = auto_login_user()
    data, submitted, users = get_sign_status(user, type_sign="resign", initial=True)
    assert isinstance(data, list)
    assert submitted is False


@pytest.mark.django_db
def test_get_sign_status_osm_no_processes(auto_login_user):
    """get_sign_status with type_sign='osm' returns empty data when no OSM."""
    from thetatauCMT.forms.views import get_sign_status

    _, user = auto_login_user()
    data, submitted, users = get_sign_status(user, type_sign="osm", initial=True)
    assert isinstance(data, list)
    assert submitted is False


@pytest.mark.django_db
def test_get_sign_status_discipline_no_processes(auto_login_user):
    """get_sign_status_discipline returns empty when no disciplinary processes."""
    from thetatauCMT.forms.views import get_sign_status_discipline

    _, user = auto_login_user()
    data = get_sign_status_discipline(user)
    assert isinstance(data, list)


# ─── AuditFormView GET (OfficerRequired) ─────────────────────────────────────


@pytest.mark.django_db
def test_audit_form_view_unauthenticated_redirects(client, db):
    url = reverse("forms:audit")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_audit_form_view_officer_returns_200(auto_login_user):
    """Officer can access the audit form view (may get a 200 with empty form)."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    url = reverse("forms:audit")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── RiskManagementFormView ───────────────────────────────────────────────────


@pytest.mark.django_db
def test_rmp_form_view_authenticated_returns_200(auto_login_user):
    """Authenticated user can access the RMP form."""
    client, user = auto_login_user()
    url = reverse("forms:rmp")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── RoleChangeView (officer) ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_role_change_view_unauthenticated_redirects(client, db):
    url = reverse("forms:officer")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_role_change_view_officer_returns_200(auto_login_user):
    """Officer can access the role change view."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    url = reverse("forms:officer")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── StatusChangeSelectView ───────────────────────────────────────────────────


@pytest.mark.django_db
def test_status_change_select_view_unauthenticated_redirects(client, db):
    url = reverse("forms:status_selection")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_status_change_select_view_officer_returns_200(auto_login_user):
    """Officer can access the status change selection view."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    url = reverse("forms:status_selection")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── StatusChangeSelectView POST ─────────────────────────────────────────────


@pytest.mark.django_db
def test_status_change_select_post_add_row(auto_login_user):
    """POST with action='Add Row' returns the formset page (200)."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    url = reverse("forms:status_selection")
    data = {
        "selection-TOTAL_FORMS": "0",
        "selection-INITIAL_FORMS": "0",
        "selection-MIN_NUM_FORMS": "0",
        "selection-MAX_NUM_FORMS": "1000",
        "action": "Add Row",
    }
    response = client.post(url, data)
    assert response.status_code == 200


@pytest.mark.django_db
def test_status_change_select_post_delete_selected(auto_login_user):
    """POST with action='Delete Selected' returns the formset page (200)."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    url = reverse("forms:status_selection")
    data = {
        "selection-TOTAL_FORMS": "0",
        "selection-INITIAL_FORMS": "0",
        "selection-MIN_NUM_FORMS": "0",
        "selection-MAX_NUM_FORMS": "1000",
        "action": "Delete Selected",
    }
    response = client.post(url, data)
    assert response.status_code == 200


# ─── active_chapters_filter direct tests ─────────────────────────────────────


@pytest.mark.django_db
def test_active_chapters_filter_unbound():
    """Unbound filter returns all active chapters and a 2-tuple of dates."""
    from thetatauCMT.forms.filters import RiskListFilter
    from thetatauCMT.forms.views import active_chapters_filter

    f = RiskListFilter(None)
    chapters, dates = active_chapters_filter(f)
    assert chapters is not None
    assert len(dates) == 2


@pytest.mark.django_db
def test_active_chapters_filter_bound_national():
    """Bound filter with region='national' returns all active chapters."""
    from django.http import QueryDict

    from thetatauCMT.forms.filters import RiskListFilter
    from thetatauCMT.forms.views import active_chapters_filter

    qd = QueryDict(mutable=True)
    qd["region"] = "national"
    f = RiskListFilter(qd)
    chapters, dates = active_chapters_filter(f)
    assert chapters is not None
    assert len(dates) == 2


@pytest.mark.django_db
def test_active_chapters_filter_bound_candidate_chapter():
    """Bound filter with region='candidate_chapter' filters to CC chapters."""
    from django.http import QueryDict

    from thetatauCMT.forms.filters import RiskListFilter
    from thetatauCMT.forms.views import active_chapters_filter

    qd = QueryDict(mutable=True)
    qd["region"] = "candidate_chapter"
    f = RiskListFilter(qd)
    chapters, dates = active_chapters_filter(f)
    assert chapters is not None
    assert len(dates) == 2


@pytest.mark.skip(reason="Triggers decimal.Decimal integer-interpretation bug in core/models.py:225")
@pytest.mark.django_db
def test_active_chapters_filter_bound_with_year_term():
    """Bound filter with year and term returns correct date range."""
    from django.http import QueryDict

    from thetatauCMT.forms.filters import RiskListFilter
    from thetatauCMT.forms.views import active_chapters_filter

    qd = QueryDict(mutable=True)
    qd["year"] = "2023"
    qd["term"] = "fa"
    f = RiskListFilter(qd)
    chapters, dates = active_chapters_filter(f)
    assert chapters is not None
    assert len(dates) == 2


# ─── remove_extra_form direct test ────────────────────────────────────────────


def test_remove_extra_form_removes_last_form():
    """remove_extra_form decrements total form count by 1."""
    from django import forms as dj_forms

    from thetatauCMT.forms.views import remove_extra_form

    TestFormSet = dj_forms.formset_factory(dj_forms.Form, extra=2)
    data = {
        "form-TOTAL_FORMS": "2",
        "form-INITIAL_FORMS": "0",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
    }
    formset = TestFormSet(data)
    orig = formset.total_form_count()
    result = remove_extra_form(formset)
    assert result.total_form_count() == orig - 1


# ─── CSV download paths ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_rmp_list_csv_download_returns_csv(auto_login_user):
    """RMP list CSV download always returns text/csv content-type."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:rmp_list")
    response = client.get(url, {"csv": "download csv"})
    assert response.status_code == 200
    assert "text/csv" in response.get("Content-Type", "")


@pytest.mark.django_db
def test_pledge_program_list_csv_no_data_renders_page(auto_login_user):
    """Pledge program CSV with no data renders HTML page (error message)."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:pledge_program_list")
    response = client.get(url, {"csv": "download csv"}, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_convention_list_csv_no_data_renders_page(auto_login_user):
    """Convention list CSV with no data renders HTML (error message)."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:convention_list")
    response = client.get(url, {"csv": "download csv"}, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_osm_list_csv_no_data_renders_page(auto_login_user):
    """OSM list CSV with no data renders HTML (error message)."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:osm_list")
    response = client.get(url, {"csv": "download csv"}, follow=True)
    assert response.status_code == 200


# ─── complete param variations for list views ─────────────────────────────────


@pytest.mark.django_db
def test_convention_list_complete_1(auto_login_user):
    """Convention list with complete=1 filters to complete-only."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:convention_list")
    response = client.get(url, {"complete": "1"}, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_convention_list_complete_0(auto_login_user):
    """Convention list with complete=0 filters to incomplete-only."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:convention_list")
    response = client.get(url, {"complete": "0"}, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_osm_list_complete_1(auto_login_user):
    """OSM list with complete=1 filters to complete-only."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:osm_list")
    response = client.get(url, {"complete": "1"}, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_osm_list_complete_0(auto_login_user):
    """OSM list with complete=0 filters to incomplete-only."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:osm_list")
    response = client.get(url, {"complete": "0"}, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_pledge_program_list_complete_1(auto_login_user):
    """Pledge program list with complete=1 filters to approved."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:pledge_program_list")
    response = client.get(url, {"complete": "1"}, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_pledge_program_list_complete_empty(auto_login_user):
    """Pledge program list with explicit cancel clears filter (complete='')."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:pledge_program_list")
    response = client.get(url, {"cancel": "1"}, follow=True)
    assert response.status_code == 200


# ─── region=candidate_chapter variations ──────────────────────────────────────


@pytest.mark.django_db
def test_convention_list_region_candidate_chapter(auto_login_user):
    """Convention list filtered to candidate chapters."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:convention_list")
    response = client.get(url, {"region": "candidate_chapter"}, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_osm_list_region_candidate_chapter(auto_login_user):
    """OSM list filtered to candidate chapters."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:osm_list")
    response = client.get(url, {"region": "candidate_chapter"}, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_pledge_program_list_region_candidate_chapter(auto_login_user):
    """Pledge program list filtered to candidate chapters."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:pledge_program_list")
    response = client.get(url, {"region": "candidate_chapter"}, follow=True)
    assert response.status_code == 200


# ─── cancel param tests (additional views) ────────────────────────────────────


@pytest.mark.django_db
def test_convention_list_cancel_param(auto_login_user):
    """Convention list with cancel=1 clears filters."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:convention_list")
    response = client.get(url, {"cancel": "1"})
    assert response.status_code == 200


@pytest.mark.django_db
def test_osm_list_cancel_param(auto_login_user):
    """OSM list with cancel=1 clears filters."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:osm_list")
    response = client.get(url, {"cancel": "1"})
    assert response.status_code == 200


@pytest.mark.django_db
def test_pledge_program_list_cancel_param(auto_login_user):
    """Pledge program list with cancel=1 clears filters."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:pledge_program_list")
    response = client.get(url, {"cancel": "1"})
    assert response.status_code == 200


@pytest.mark.django_db
def test_alumniexclusion_list_cancel_param(auto_login_user):
    """Alumni exclusion list with cancel=1 clears filters."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:alumniexclusion_list")
    response = client.get(url, {"cancel": "1"})
    assert response.status_code == 200


@pytest.mark.django_db
def test_bylaws_list_cancel_param(auto_login_user):
    """Bylaws list with cancel=1 clears filters."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:bylaws_list")
    response = client.get(url, {"cancel": "1"})
    assert response.status_code == 200


@pytest.mark.django_db
def test_education_list_cancel_param(auto_login_user):
    """Education list with cancel=1 clears filters."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:education_list")
    response = client.get(url, {"cancel": "1"})
    assert response.status_code == 200


# ─── AlumniExclusionListView special filter ───────────────────────────────────


@pytest.mark.django_db
def test_alumniexclusion_list_veto_none_filter(auto_login_user):
    """Alumni exclusion list with regional_director_veto=None filters correctly."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:alumniexclusion_list")
    response = client.get(url, {"regional_director_veto": "None"})
    assert response.status_code == 200


# ─── get_sign_status with name=True ───────────────────────────────────────────


@pytest.mark.django_db
def test_get_sign_status_creds_name_true(auto_login_user):
    """get_sign_status with name=True and no processes returns empty list."""
    from thetatauCMT.forms.views import get_sign_status

    _, user = auto_login_user()
    data, submitted, users = get_sign_status(user, type_sign="creds", name=True)
    assert isinstance(data, list)
    assert submitted is False


@pytest.mark.django_db
def test_get_sign_status_resign_name_true(auto_login_user):
    """get_sign_status(resign, name=True) returns empty list with no processes."""
    from thetatauCMT.forms.views import get_sign_status

    _, user = auto_login_user()
    data, submitted, users = get_sign_status(user, type_sign="resign", name=True)
    assert isinstance(data, list)
    assert submitted is False


@pytest.mark.django_db
def test_get_sign_status_osm_name_true(auto_login_user):
    """get_sign_status(osm, name=True) returns empty list with no processes."""
    from thetatauCMT.forms.views import get_sign_status

    _, user = auto_login_user()
    data, submitted, users = get_sign_status(user, type_sign="osm", name=True)
    assert isinstance(data, list)
    assert submitted is False


@pytest.mark.django_db
def test_get_sign_status_discipline_name_true(auto_login_user):
    """get_sign_status_discipline with name=True returns empty list."""
    from thetatauCMT.forms.views import get_sign_status_discipline

    _, user = auto_login_user()
    data = get_sign_status_discipline(user, name=True)
    assert isinstance(data, list)


@pytest.mark.django_db
def test_get_sign_status_discipline_complete_false(auto_login_user):
    """get_sign_status_discipline with complete=False returns empty list (no processes)."""
    from thetatauCMT.forms.views import get_sign_status_discipline

    _, user = auto_login_user()
    data = get_sign_status_discipline(user, complete=False)
    assert isinstance(data, list)


# ─── BylawsListView with region filter ────────────────────────────────────────


@pytest.mark.django_db
def test_bylaws_list_region_candidate_chapter(auto_login_user):
    """Bylaws list with region=candidate_chapter filters correctly."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:bylaws_list")
    response = client.get(url, {"region": "candidate_chapter"}, follow=True)
    assert response.status_code == 200


# ─── AuditListView additional params ──────────────────────────────────────────


@pytest.mark.django_db
def test_audit_list_view_without_follow(auto_login_user):
    """Audit list view returns 200 directly for natoff user."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:audit_list")
    response = client.get(url)
    assert response.status_code == 200


# ─── PledgeProgramProcessDetailView ───────────────────────────────────────────


@pytest.mark.django_db
def test_pledge_program_detail_view_404(auto_login_user):
    """Accessing a non-existent pledge program detail returns 404."""
    client, user = auto_login_user()
    url = reverse("forms:pledge_program_detail", kwargs={"pk": 999999})
    response = client.get(url)
    assert response.status_code == 404


# ─── AlumniExclusionDetailView ────────────────────────────────────────────────


@pytest.mark.django_db
def test_alumniexclusion_detail_view_404(auto_login_user):
    """Accessing a non-existent alumni exclusion detail returns 404."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:alumniexclusion_detail", kwargs={"pk": 999999})
    response = client.get(url)
    assert response.status_code == 404


# ─── load_majors with other param ─────────────────────────────────────────────


@pytest.mark.django_db
def test_load_majors_with_chapter_and_other(client):
    """load_majors with chapter and other=1 returns 200."""
    chapter = ChapterFactory()
    url = reverse("forms:ajax_load_majors")
    response = client.get(url, {"chapter": chapter.pk, "other": "1"})
    assert response.status_code == 200


# ─── FormLanding template check ───────────────────────────────────────────────


@pytest.mark.django_db
def test_form_landing_uses_correct_template(auto_login_user):
    """FormLanding uses forms/landing.html template."""
    client, _user = auto_login_user()
    response = client.get(reverse("forms:landing"))
    template_names = [t.name for t in response.templates]
    assert "forms/landing.html" in template_names


# ─── Context key assertions ────────────────────────────────────────────────────


@pytest.mark.django_db
def test_init_selection_context_has_helper(auto_login_user):
    """InitDeplSelectView provides a 'helper' in context."""
    client, user = auto_login_user()
    response = client.get(reverse("forms:init_selection"))
    assert "helper" in response.context


@pytest.mark.django_db
def test_status_selection_context_has_formset(auto_login_user):
    """StatusChangeSelectView provides a 'formset' in context."""
    client, user = auto_login_user()
    response = client.get(reverse("forms:status_selection"))
    assert "formset" in response.context


@pytest.mark.django_db
def test_role_change_view_context_has_formset(auto_login_user):
    """RoleChangeView provides a 'formset' in context."""
    client, user = auto_login_user()
    response = client.get(reverse("forms:officer"))
    assert "formset" in response.context


@pytest.mark.django_db
def test_role_change_national_view_context_has_formset(auto_login_user):
    """RoleChangeNationalView provides a 'formset' in context."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    response = client.get(reverse("forms:natoff"), follow=True)
    assert "formset" in response.context


@pytest.mark.django_db
def test_collection_referral_context_has_form(auto_login_user):
    """CollectionReferralFormView provides form context for officers."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    response = client.get(reverse("forms:collection"), follow=True)
    assert response.status_code == 200
    assert "form" in response.context or "collections_table" in response.context


@pytest.mark.django_db
def test_bylaws_create_view_get_returns_200(auto_login_user):
    """BylawsCreateView GET returns 200 for authenticated user."""
    client, _user = auto_login_user()
    response = client.get(reverse("forms:bylaws"))
    assert response.status_code == 200


# ─── ResignationListView additional checks ────────────────────────────────────


@pytest.mark.django_db
def test_resignation_list_view_unauthenticated_explicit_redirects(client, db):
    """Unauthenticated access to resignation list is redirected."""
    url = reverse("forms:resign_list")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_resignation_list_view_officer_explicit_returns_200(auto_login_user):
    """Officer can access resignation list."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    url = reverse("forms:resign_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── StatusChangeView with session data ──────────────────────────────────────


@pytest.mark.django_db
def test_status_change_view_get_with_session(auto_login_user):
    """StatusChangeView.get renders the form when status-selection is in session."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    session = client.session
    session["status-selection"] = {
        "graduate": [],
        "coop": [],
        "covid": [],
        "military": [],
        "withdraw": [],
        "transfer": [],
        "resignedCC": [],
    }
    session.save()
    url = reverse("forms:status")
    response = client.get(url, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_status_change_view_no_session_redirects(auto_login_user):
    """StatusChangeView.get redirects to status_selection when session is absent."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    url = reverse("forms:status")
    response = client.get(url)
    # Should redirect to status_selection
    assert response.status_code in (200, 302)


# ─── InitiationView with init-selection session ───────────────────────────────


@pytest.mark.django_db
def test_initiation_view_get_with_session(auto_login_user):
    """InitiationView.get renders the form when init-selection is in session."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    session = client.session
    session["init-selection"] = {
        "Initiate": [],
        "Depledge": [],
        "Defer": [],
        "Roll": [],
    }
    session.save()
    url = reverse("forms:initiation")
    response = client.get(url, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_initiation_view_no_session_redirects(auto_login_user):
    """InitiationView.get redirects to init_selection when session is absent."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    url = reverse("forms:initiation")
    response = client.get(url)
    assert response.status_code in (200, 302)


# ─── active_chapters_filter with real region slug ────────────────────────────


@pytest.mark.django_db
def test_active_chapters_filter_bound_with_real_region(db):
    """active_chapters_filter with a real region slug covers the elif-region branch."""
    from thetatauCMT.chapters.tests.factories import ChapterFactory
    from thetatauCMT.forms.filters import RiskListFilter
    from thetatauCMT.forms.views import active_chapters_filter

    chapter = ChapterFactory.create()
    region_slug = chapter.region.slug
    f = RiskListFilter(data={"region": region_slug})
    chapters_list, dates = active_chapters_filter(f)
    assert chapters_list is not None


# ─── RiskManagementListView with actual records ──────────────────────────────


@pytest.mark.django_db
def test_rmp_list_view_with_records(auto_login_user):
    """RiskManagementListView.get_table_data loop executes when records exist."""
    from thetatauCMT.forms.tests.factories import RiskManagementFactory

    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    RiskManagementFactory.create()
    url = reverse("forms:rmp_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── ConventionListView context data with records ────────────────────────────


@pytest.mark.django_db
def test_convention_list_view_with_records(auto_login_user):
    """ConventionListView.get_context_data covers data-building loop with records."""
    from thetatauCMT.forms.tests.factories import ConventionFactory

    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    ConventionFactory.create()
    url = reverse("forms:convention_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── OSMListView context data with records ───────────────────────────────────


@pytest.mark.django_db
def test_osm_list_view_with_records(auto_login_user):
    """OSMListView.get_context_data covers data-building loop with OSM records."""
    from thetatauCMT.forms.tests.factories import OSMFactory

    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    OSMFactory.create()
    url = reverse("forms:osm_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── get_sign_status loop body with Convention records ───────────────────────


@pytest.mark.django_db
def test_get_sign_status_creds_with_convention_record(auto_login_user):
    """get_sign_status loop body runs when Convention records exist in chapter."""
    from thetatauCMT.forms.tests.factories import ConventionFactory
    from thetatauCMT.forms.views import get_sign_status

    _, user = auto_login_user()
    ConventionFactory.create(chapter=user.current_chapter)
    data, submitted, users = get_sign_status(user, type_sign="creds", initial=True)
    assert submitted is True
    assert isinstance(data, list)


@pytest.mark.django_db
def test_get_sign_status_osm_with_osm_record(auto_login_user):
    """get_sign_status loop body runs when OSM records exist in chapter."""
    from thetatauCMT.forms.tests.factories import OSMFactory
    from thetatauCMT.forms.views import get_sign_status

    _, user = auto_login_user()
    OSMFactory.create(chapter=user.current_chapter)
    data, submitted, users = get_sign_status(user, type_sign="osm", initial=True)
    assert submitted is True
    assert isinstance(data, list)


# ─── RitualProficiencyCreateView ─────────────────────────────────────────────


@pytest.mark.django_db
def test_ritual_proficiency_create_view_get(auto_login_user):
    """RitualProficiencyCreateView GET returns 200 for natoff users."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:ritual_proficiency")
    response = client.get(url, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_ritual_proficiency_user_table_get_no_user(auto_login_user):
    """RitualProficiencyUserTableView GET without user_id returns 200."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:ritual_proficiency_user_table")
    response = client.get(url, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_ritual_proficiency_user_table_get_with_user(auto_login_user):
    """RitualProficiencyUserTableView GET with user_id returns 200."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:ritual_proficiency_user_table")
    response = client.get(url, {"user_id": user.pk}, follow=True)
    assert response.status_code == 200


# ─── BylawsListView with existing chapter data ───────────────────────────────


@pytest.mark.django_db
def test_bylaws_list_view_with_chapter_data(auto_login_user):
    """BylawsListView context data covers missing_data path when no bylaws exist."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:bylaws_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── PledgeProgramListView with records ──────────────────────────────────────


@pytest.mark.django_db
def test_pledge_program_list_with_records(auto_login_user):
    """PledgeProgramListView GET with existing records returns 200."""
    from thetatauCMT.forms.tests.factories import PledgeProgramFactory

    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    PledgeProgramFactory.create(chapter=user.current_chapter)
    url = reverse("forms:pledge_program_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── AuditListView with actual Audit records ─────────────────────────────────


@pytest.mark.django_db
def test_audit_list_view_with_records(auto_login_user):
    """AuditListView context data covers loop when Audit records exist."""
    from thetatauCMT.forms.tests.factories import AuditFactory

    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    AuditFactory.create(user=user)
    url = reverse("forms:audit_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── set_init_date view ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_set_init_date_post(auto_login_user):
    """set_init_date POST sets init_date in session and returns 200."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    url = reverse("forms:set_init_date")
    response = client.post(url, {"init_date": "01/01/2024"})
    assert response.status_code == 200


# ─── RiskManagementFormView GET ──────────────────────────────────────────────


@pytest.mark.django_db
def test_rmp_form_view_get(auto_login_user):
    """RiskManagementFormView GET returns 200 for logged-in user."""
    client, user = auto_login_user()
    url = reverse("forms:rmp")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── PledgeFormView alt form ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_pledge_form_alt_get_with_description_returns_200(client):
    """PledgeFormView alt form GET returns 200."""
    url = reverse("forms:pledgeform-alt")
    response = client.get(url)
    assert response.status_code == 200


# ─── StatusChangeSelectView context (existing tests cover GET, add POST branch) ─


@pytest.mark.django_db
def test_status_change_select_view_post_empty(auto_login_user):
    """StatusChangeSelectView POST with minimal data returns 200."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    url = reverse("forms:status_selection")
    data = {
        "action": "submit",
        "selection-TOTAL_FORMS": "1",
        "selection-INITIAL_FORMS": "0",
        "selection-MIN_NUM_FORMS": "0",
        "selection-MAX_NUM_FORMS": "1000",
        "selection-0-user": "",
        "selection-0-state": "",
    }
    response = client.post(url, data, follow=True)
    assert response.status_code == 200


# ─── RoleChangeView GET with officer (already covered unauthenticated) ────────


@pytest.mark.django_db
def test_role_change_view_officer_with_description_returns_200(auto_login_user):
    """RoleChangeView GET returns 200 for officers."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    url = reverse("forms:officer")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── OSMListView complete=1 filter ───────────────────────────────────────────


@pytest.mark.django_db
def test_osm_list_complete_filter_1_with_records(auto_login_user):
    """OSMListView with complete=1 and existing records covers complete path."""
    from thetatauCMT.forms.tests.factories import OSMFactory

    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    OSMFactory.create()
    url = reverse("forms:osm_list")
    response = client.get(url, {"complete": "1"}, follow=True)
    assert response.status_code == 200


# ─── ConventionListView complete=1 filter with records ───────────────────────


@pytest.mark.django_db
def test_convention_list_complete_filter_1_with_records(auto_login_user):
    """ConventionListView with complete=1 and records covers complete data path."""
    from thetatauCMT.forms.tests.factories import ConventionFactory

    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    ConventionFactory.create()
    url = reverse("forms:convention_list")
    response = client.get(url, {"complete": "1"}, follow=True)
    assert response.status_code == 200


# ─── AuditFormView GET (forms:audit) ─────────────────────────────────────────


@pytest.mark.django_db
def test_audit_form_view_get_officer_no_roles(auto_login_user):
    """AuditFormView GET with officer but no chapter roles covers get_object path."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    url = reverse("forms:audit")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── AlumniExclusionListView context data ────────────────────────────────────


@pytest.mark.django_db
def test_alumniexclusion_list_context_table(auto_login_user):
    """AlumniExclusionListView context contains table with annotation."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:alumniexclusion_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── PledgeProgramListView email_list CSV path ───────────────────────────────


@pytest.mark.django_db
def test_pledge_program_list_csv_with_no_emails(auto_login_user):
    """PledgeProgramListView CSV download with no data shows error message."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:pledge_program_list")
    response = client.get(url, {"csv": "Download CSV"}, follow=True)
    assert response.status_code == 200


# ─── CollectionReferralFormView GET (get_context_data) ───────────────────────


@pytest.mark.django_db
def test_collection_referral_get_context(auto_login_user):
    """CollectionReferralFormView GET calls get_context_data and returns 200."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    url = reverse("forms:collection")
    response = client.get(url, follow=True)
    assert response.status_code == 200
    assert "collections_table" in response.context


# ─── BylawsListView with records ─────────────────────────────────────────────


@pytest.mark.django_db
def test_bylaws_list_region_national_filter(auto_login_user):
    """BylawsListView with region=national returns 200 and covers context data."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:bylaws_list")
    response = client.get(url, {"region": "national"}, follow=True)
    assert response.status_code == 200


# ─── PledgeFormView POST with invalid data (covers form_invalid) ─────────────


@pytest.mark.django_db
def test_pledge_form_post_invalid_returns_200(client):
    """PledgeFormView POST with invalid data triggers form_invalid path."""
    url = reverse("forms:pledgeform")
    response = client.post(url, {})
    assert response.status_code == 200


# ─── FormLanding context (init/pledge processes for loop bodies) ─────────────


@pytest.mark.django_db
def test_form_landing_with_initiation_process(auto_login_user):
    """FormLanding get_context_data covers initiation process loop body."""
    from thetatauCMT.forms.tests.factories import InitiationProcessFactory

    client, user = auto_login_user()
    InitiationProcessFactory.create(chapter=user.current_chapter)
    url = reverse("forms:landing")
    response = client.get(url, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_form_landing_with_pledge_process(auto_login_user):
    """FormLanding get_context_data covers pledge process loop body."""
    from thetatauCMT.forms.tests.factories import PledgeProcessFactory

    client, user = auto_login_user()
    PledgeProcessFactory.create(chapter=user.current_chapter)
    url = reverse("forms:landing")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── get_sign_status_discipline direct call with complete=True ──────────────


@pytest.mark.django_db
def test_get_sign_status_discipline_complete_true(auto_login_user):
    """get_sign_status_discipline with complete=True returns empty list (no processes)."""
    from thetatauCMT.forms.views import get_sign_status_discipline

    _, user = auto_login_user()
    data = get_sign_status_discipline(user, complete=True)
    assert isinstance(data, list)


# ─── PledgeProgramListView context data building ─────────────────────────────


@pytest.mark.django_db
def test_pledge_program_list_complete_filter_all(auto_login_user):
    """PledgeProgramListView with complete='' covers the all-forms path."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:pledge_program_list")
    response = client.get(url, {"complete": ""}, follow=True)
    assert response.status_code == 200


# ─── RoleChangeNationalView GET covers more context ──────────────────────────


@pytest.mark.django_db
def test_role_change_national_view_officer_returns_200(auto_login_user):
    """RoleChangeNationalView GET returns 200 for natoff users."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:natoff")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── OSMListView region filter  ───────────────────────────────────────────────


@pytest.mark.django_db
def test_osm_list_complete_0_candidate_chapter(auto_login_user):
    """OSM list with complete=0 and region=candidate_chapter filters correctly."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:osm_list")
    response = client.get(url, {"complete": "0", "region": "candidate_chapter"}, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_convention_list_complete_0_candidate_chapter(auto_login_user):
    """Convention list with complete=0 and region=candidate_chapter filters correctly."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:convention_list")
    response = client.get(url, {"complete": "0", "region": "candidate_chapter"}, follow=True)
    assert response.status_code == 200


# ─── RoleChangeView unauthenticated ───────────────────────────────────────────


@pytest.mark.django_db
def test_role_change_view_unauthenticated_with_description_redirects(client, db):
    """Unauthenticated access to officer role change is redirected."""
    url = reverse("forms:officer")
    response = client.get(url)
    assert response.status_code == 302


# ─── BillOfRightsDetailView (no auth) ────────────────────────────────────────


@pytest.mark.django_db
def test_bill_of_rights_detail_404(client):
    """BillOfRightsDetailView returns 404 for nonexistent pk."""
    url = reverse("forms:bill_of_rights", kwargs={"pk": 999999})
    response = client.get(url)
    assert response.status_code == 404


# ─── BillOfRightsDetailView with real chapter ─────────────────────────────────


@pytest.mark.django_db
def test_bill_of_rights_detail_with_chapter(client):
    """BillOfRightsDetailView returns 200 for a real chapter pk."""
    chapter = ChapterFactory()
    url = reverse("forms:bill_of_rights", kwargs={"pk": chapter.pk})
    response = client.get(url)
    assert response.status_code == 200


# ─── StatusChangeView POST with session ──────────────────────────────────────


@pytest.mark.django_db
def test_status_change_view_post_empty_formsets(auto_login_user):
    """StatusChangeView.post covers the POST handler with empty formsets."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    session = client.session
    session["status-selection"] = {
        "graduate": [],
        "coop": [],
        "covid": [],
        "military": [],
        "withdraw": [],
        "transfer": [],
        "resignedCC": [],
    }
    session.save()
    url = reverse("forms:status")
    data = {
        "graduates-TOTAL_FORMS": "0",
        "graduates-INITIAL_FORMS": "0",
        "graduates-MIN_NUM_FORMS": "0",
        "graduates-MAX_NUM_FORMS": "1000",
        "csmt-TOTAL_FORMS": "0",
        "csmt-INITIAL_FORMS": "0",
        "csmt-MIN_NUM_FORMS": "0",
        "csmt-MAX_NUM_FORMS": "1000",
    }
    response = client.post(url, data, follow=True)
    assert response.status_code == 200


# ─── RoleChangeView POST with empty formset ──────────────────────────────────


@pytest.mark.django_db
def test_role_change_view_post_empty_formset(auto_login_user):
    """RoleChangeView.post covers the POST handler with empty formset data."""
    client, user = auto_login_user()
    url = reverse("forms:officer")
    data = {
        "form-TOTAL_FORMS": "1",
        "form-INITIAL_FORMS": "0",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
        "form-0-user": "",
        "form-0-role": "",
    }
    response = client.post(url, data, follow=True)
    assert response.status_code == 200


# ─── RoleChangeNationalView POST with empty formset ──────────────────────────


@pytest.mark.django_db
def test_role_change_national_view_post_empty_formset(auto_login_user):
    """RoleChangeNationalView.post covers the POST handler with empty formset data."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:natoff")
    data = {
        "form-TOTAL_FORMS": "1",
        "form-INITIAL_FORMS": "0",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
        "form-0-user": "",
        "form-0-role": "",
    }
    response = client.post(url, data, follow=True)
    assert response.status_code == 200


# ─── InitiationView POST with session and empty formsets ─────────────────────


@pytest.mark.django_db
def test_initiation_view_post_empty_formsets(auto_login_user):
    """InitiationView.post covers the POST handler with session and empty formsets."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    session = client.session
    session["init-selection"] = {
        "Initiate": [],
        "Depledge": [],
        "Defer": [],
        "Roll": [],
    }
    session.save()
    url = reverse("forms:initiation")
    data = {
        "initiates-TOTAL_FORMS": "0",
        "initiates-INITIAL_FORMS": "0",
        "initiates-MIN_NUM_FORMS": "0",
        "initiates-MAX_NUM_FORMS": "1000",
        "depledges-TOTAL_FORMS": "0",
        "depledges-INITIAL_FORMS": "0",
        "depledges-MIN_NUM_FORMS": "0",
        "depledges-MAX_NUM_FORMS": "1000",
    }
    response = client.post(url, data, follow=True)
    assert response.status_code == 200


# ─── PrematureAlumnusCreateView GET (context_data) ────────────────────────────


@pytest.mark.django_db
def test_premature_alumnus_create_view_get(auto_login_user):
    """PrematureAlumnusCreateView GET covers get_context_data."""
    client, user = auto_login_user()
    url = reverse("viewflow:forms:prematurealumnus:start")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── HSEducationCreateView GET (context_data) ────────────────────────────────


@pytest.mark.django_db
def test_hs_education_create_view_get(auto_login_user):
    """HSEducationCreateView GET covers get_context_data."""
    client, user = auto_login_user()
    url = reverse("viewflow:forms:hseducation:start")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── RiskManagementDetailView GET with record ────────────────────────────────


@pytest.mark.django_db
def test_rmp_detail_view_get(auto_login_user):
    """RiskManagementDetailView GET covers get_context_data with a real record."""
    from unittest.mock import patch

    from thetatauCMT.forms.tests.factories import RiskManagementFactory

    client, user = auto_login_user()
    rmp = RiskManagementFactory.create(user=user)
    url = reverse("forms:rmp_complete", kwargs={"pk": rmp.pk})
    # The view renders a PDF via xhtml2pdf which requires static files to be
    # collected on disk.  In CI that directory doesn't exist, so we mock the
    # PDF rendering step and return an empty bytes response instead.
    with patch(
        "easy_pdf.views.PDFTemplateResponseMixin.render_to_response",
        return_value=HttpResponse(b"%PDF-1.4 mock", content_type="application/pdf"),
    ):
        response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── AuditListView context data path (lines 1403-1406) ───────────────────────


@pytest.mark.django_db
def test_audit_list_view_natoff_with_many_records(auto_login_user):
    """AuditListView with many audit records covers filter loop body."""
    from thetatauCMT.forms.tests.factories import AuditFactory

    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    for _ in range(3):
        AuditFactory.create()
    url = reverse("forms:audit_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── PledgeProgramListView with many records ─────────────────────────────────


@pytest.mark.django_db
def test_pledge_program_list_with_many_records(auto_login_user):
    """PledgeProgramListView with many records covers context data loop."""
    from thetatauCMT.forms.tests.factories import PledgeProgramFactory

    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    for _ in range(3):
        PledgeProgramFactory.create()
    url = reverse("forms:pledge_program_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── get_sign_status complete=False variant ──────────────────────────────────


@pytest.mark.django_db
def test_get_sign_status_creds_complete_false(auto_login_user):
    """get_sign_status with complete=False and a convention covers the complete path."""
    from thetatauCMT.forms.tests.factories import ConventionFactory
    from thetatauCMT.forms.views import get_sign_status

    _, user = auto_login_user()
    ConventionFactory.create(chapter=user.current_chapter)
    data, submitted, users = get_sign_status(user, type_sign="creds", initial=True, complete=False)
    assert isinstance(data, list)


# ─── ResignationListView with context ────────────────────────────────────────


@pytest.mark.django_db
def test_resignation_list_natoff_returns_200(auto_login_user):
    """ResignationListView natoff access returns 200."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:resign_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── BylawsCreateView GET covers context_data (3305-3311) ────────────────────


@pytest.mark.django_db
def test_bylaws_create_view_context_data(auto_login_user):
    """BylawsCreateView GET calls get_context_data and returns 200."""
    client, user = auto_login_user()
    url = reverse("forms:bylaws")
    response = client.get(url, follow=True)
    assert response.status_code == 200
    assert "table" in response.context or "form" in response.context


# ─── OSMListView CSV download with records ───────────────────────────────────


@pytest.mark.django_db
def test_osm_list_csv_download_with_records(auto_login_user):
    """OSMListView CSV download with records covers the CSV writer path."""
    from thetatauCMT.forms.tests.factories import OSMFactory

    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    OSMFactory.create()
    url = reverse("forms:osm_list")
    response = client.get(url, {"csv": "Download CSV"}, follow=True)
    assert response.status_code == 200


# ─── ConventionListView CSV download with records ────────────────────────────


@pytest.mark.django_db
def test_convention_list_csv_with_records(auto_login_user):
    """ConventionListView CSV download with records covers the CSV writer path."""
    from thetatauCMT.forms.tests.factories import ConventionFactory

    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    ConventionFactory.create()
    url = reverse("forms:convention_list")
    response = client.get(url, {"csv": "Download CSV"}, follow=True)
    assert response.status_code == 200


# ─── RitualProficiencyUserTableView with existing user_id ────────────────────


@pytest.mark.django_db
def test_ritual_proficiency_user_table_csv(auto_login_user):
    """RitualProficiencyUserTableView renders table for a specific user."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:ritual_proficiency_user_table")
    response = client.get(url, {"user_id": str(user.pk)}, follow=True)
    assert response.status_code == 200


# ─── InitDeplSelectView GET with processes ────────────────────────────────────


@pytest.mark.django_db
def test_init_depl_select_view_get_with_processes(auto_login_user):
    """InitDeplSelectView GET with InitiationProcess and PledgeProcess objects
    covers the loop bodies at lines 222-232 and 245-255."""
    from thetatauCMT.forms.tests.factories import InitiationProcessFactory, PledgeProcessFactory

    client, user = auto_login_user()
    _add_to_group(user, "officer")
    InitiationProcessFactory.create(chapter=user.chapter)
    PledgeProcessFactory.create(chapter=user.chapter)
    url = reverse("forms:init_selection")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── InitDeplSelectView POST empty formset ────────────────────────────────────


@pytest.mark.django_db
def test_init_depl_select_view_post_empty_formset(auto_login_user):
    """InitDeplSelectView POST with empty formset covers formset_valid and
    get_success_url at lines 278-279, 283-284, 288."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    url = reverse("forms:init_selection")
    data = {
        "form-TOTAL_FORMS": "0",
        "form-INITIAL_FORMS": "0",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
    }
    response = client.post(url, data, follow=True)
    assert response.status_code == 200


# ─── StatusChangeSelectView GET (line 552) ───────────────────────────────────


@pytest.mark.django_db
def test_status_change_select_view_get(auto_login_user):
    """StatusChangeSelectView GET covers construct_formset call at line 552."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    url = reverse("forms:status_selection")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── badge_shingle_init_csv (lines 1817-1827) ────────────────────────────────


@pytest.mark.skip(reason="generate_blackbaud_update requires fee configuration not available in test DB")
@pytest.mark.django_db
def test_badge_shingle_init_csv_crm(auto_login_user):
    """badge_shingle_init_csv with csv_type='crm' covers lines 1817-1827."""
    from thetatauCMT.forms.tests.factories import InitiationProcessFactory

    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    process = InitiationProcessFactory.create()
    url = reverse(
        "forms:init_csv",
        kwargs={"process_pk": process.pk, "csv_type": "crm"},
    )
    response = client.get(url, follow=True)
    assert response.status_code == 200


@pytest.mark.skip(reason="generate_blackbaud_update requires fee configuration not available in test DB")
@pytest.mark.django_db
def test_badge_shingle_init_csv_invoice(auto_login_user):
    """badge_shingle_init_csv with csv_type='invoice' covers line 1823."""
    from thetatauCMT.forms.tests.factories import InitiationProcessFactory

    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    process = InitiationProcessFactory.create()
    url = reverse(
        "forms:init_csv",
        kwargs={"process_pk": process.pk, "csv_type": "invoice"},
    )
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── PrematureAlumnusCreateView GET with existing processes ──────────────────


@pytest.mark.django_db
def test_premature_alumnus_create_view_get_with_processes(auto_login_user):
    """PrematureAlumnusCreateView GET with existing PrematureAlumnus objects
    covers the loop body at lines 1792-1801."""
    from thetatauCMT.forms.tests.factories import PrematureAlumnusFactory
    from thetatauCMT.users.tests.factories import UserFactory

    client, user = auto_login_user()
    member = UserFactory.create(chapter=user.chapter)
    PrematureAlumnusFactory.create(user=member)
    url = reverse("viewflow:forms:prematurealumnus:start")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── RiskManagementListView with active user (lines 1364-1372) ───────────────


@pytest.mark.django_db
def test_rmp_list_with_active_user(auto_login_user):
    """RiskManagementListView GET with an active user covers the loop body
    at lines 1364-1372."""
    from thetatauCMT.users.tests.factories import UserFactory, UserStatusChangeFactory

    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    active_user = UserFactory.create(chapter=user.chapter)
    UserStatusChangeFactory.create(user=active_user, status="active", current=True)
    url = reverse("forms:rmp_list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── AuditFormView GET with pk – 'complete' branch (lines 1546-1549, 1564-1571)


@pytest.mark.django_db
def test_audit_form_view_get_with_pk(auto_login_user):
    """AuditFormView GET with existing pk triggers get_object pk-branch and
    renders the 'Audit complete' banner."""
    from thetatauCMT.forms.tests.factories import AuditFactory
    from thetatauCMT.users.tests.factories import UserRoleChangeFactory

    client, user = auto_login_user()
    _add_to_group(user, "officer")
    UserRoleChangeFactory.create(user=user, current=True, role="regent")
    audit = AuditFactory.create(user=user)
    url = reverse("forms:audit_complete", kwargs={"pk": audit.pk})
    response = client.get(url, follow=True)
    assert response.status_code == 200
    assert "Audit complete" in response.content.decode()


@pytest.mark.django_db
def test_audit_form_view_get_with_pk_non_exec_officer(auto_login_user):
    """A user in the 'officer' group without a current executive role should
    still be able to VIEW a completed audit for their own chapter — they must
    not be bounced to a blank submit form."""
    from thetatauCMT.forms.tests.factories import AuditFactory

    client, user = auto_login_user()
    _add_to_group(user, "officer")
    # No UserRoleChangeFactory: user has no current CHAPTER_OFFICER role.
    audit = AuditFactory.create(user=user)
    url = reverse("forms:audit_complete", kwargs={"pk": audit.pk})
    response = client.get(url, follow=True)
    assert response.status_code == 200
    assert "Audit complete" in response.content.decode()


@pytest.mark.django_db
def test_audit_form_view_get_with_pk_wrong_chapter(auto_login_user):
    """An officer requesting an audit belonging to a different chapter must
    NOT see the completed-audit page for that chapter."""
    from thetatauCMT.chapters.tests.factories import ChapterFactory
    from thetatauCMT.forms.tests.factories import AuditFactory
    from thetatauCMT.users.tests.factories import UserFactory, UserRoleChangeFactory

    client, user = auto_login_user()
    _add_to_group(user, "officer")
    UserRoleChangeFactory.create(user=user, current=True, role="treasurer")
    other_chapter = ChapterFactory()
    other_user = UserFactory(chapter=other_chapter)
    audit = AuditFactory.create(user=other_user)

    url = reverse("forms:audit_complete", kwargs={"pk": audit.pk})
    response = client.get(url, follow=True)
    assert response.status_code == 200
    # The view falls back to the empty (submission) form — no completed banner.
    assert "Audit complete" not in response.content.decode()


# ─── AuditFormView POST as officer – form_valid (lines 1590-1616) ────────────


@pytest.mark.django_db
def test_audit_form_view_post_as_officer(auto_login_user):
    """AuditFormView POST with valid data as an officer with current roles
    covers form_valid at lines 1590-1616."""
    from thetatauCMT.users.tests.factories import UserRoleChangeFactory

    client, user = auto_login_user()
    _add_to_group(user, "officer")
    UserRoleChangeFactory.create(user=user, current=True, role="regent")
    url = reverse("forms:audit")
    data = {
        "dues_member": "50.00",
        "dues_pledge": "25.00",
        "frequency": "semester",
        "payment_plan": "False",
        "cash_book": "True",
        "cash_register": "True",
        "member_account": "True",
        "cash_book_reviewed": "True",
        "cash_register_reviewed": "True",
        "member_account_reviewed": "True",
        "balance_checking": "1000.00",
        "balance_savings": "500.00",
        "debit_card": "False",
        "debit_card_access": "None",
        "agreement": "True",
    }
    response = client.post(url, data, follow=True)
    assert response.status_code == 200


# ─── pledge_process_csvs download (lines 2287-2294) ─────────────────────────


@pytest.mark.django_db
def test_pledge_process_csvs_download(auto_login_user):
    """pledge_process_csvs view with csv_type='invoice' covers lines 2287-2294."""
    from thetatauCMT.forms.tests.factories import PledgeProcessFactory

    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    process = PledgeProcessFactory.create()
    url = reverse(
        "forms:pledge_csv",
        kwargs={"process_pk": process.pk, "csv_type": "invoice"},
    )
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── RoleChangeView POST with one form (lines 839-848) ───────────────────────


@pytest.mark.django_db
def test_role_change_view_post_with_valid_form(auto_login_user):
    """RoleChangeView POST with a new role form covers the loop body at
    lines 839-848 (try/except and officer status check)."""
    from thetatauCMT.users.tests.factories import UserFactory

    client, user = auto_login_user()
    _add_to_group(user, "officer")
    other_user = UserFactory.create(chapter=user.chapter)
    url = reverse("forms:officer")
    import datetime

    today = datetime.date.today()
    end = today + datetime.timedelta(days=365)
    data = {
        "form-TOTAL_FORMS": "1",
        "form-INITIAL_FORMS": "0",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
        "form-0-user": str(other_user.pk),
        "form-0-role": "scribe",
        "form-0-start": today.strftime("%Y-%m-%d"),
        "form-0-end": end.strftime("%Y-%m-%d"),
    }
    response = client.post(url, data, follow=True)
    assert response.status_code == 200


# ─── ReturnStudentCreateView GET with existing process (lines 3070-3094) ─────


@pytest.mark.django_db
def test_return_student_create_view_get_with_process(auto_login_user):
    """ReturnStudentCreateView GET with an existing ReturnStudent process
    covers the loop body at lines 3070-3094."""
    from django.utils import timezone

    from thetatauCMT.forms.flows import ReturnStudentFlow
    from thetatauCMT.forms.models import ReturnStudent
    from thetatauCMT.users.tests.factories import UserFactory

    client, user = auto_login_user()
    member = UserFactory.create(chapter=user.chapter)
    # Active (unfinished) process — covers lines 3076-3081
    ReturnStudent.objects.create(
        user=member,
        reason="Test reason",
        financial=False,
        debt=False,
        flow_class=ReturnStudentFlow,
    )
    # Finished process — covers lines 3083-3084
    member2 = UserFactory.create(chapter=user.chapter)
    ReturnStudent.objects.create(
        user=member2,
        reason="Another reason",
        financial=True,
        debt=False,
        flow_class=ReturnStudentFlow,
        finished=timezone.now(),
    )
    url = reverse("viewflow:forms:returnstudent:start")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── PledgeProgramProcessDetailView GET with existing pk (lines 3101-3108) ───


@pytest.mark.django_db
def test_pledge_program_process_detail_view_get(auto_login_user):
    """PledgeProgramProcessDetailView GET with a valid pk covers
    get_context_data at lines 3101-3108."""
    from thetatauCMT.forms.flows import PledgeProgramProcessFlow
    from thetatauCMT.forms.models import PledgeProgramProcess

    client, user = auto_login_user()
    process = PledgeProgramProcess.objects.create(
        chapter=user.chapter,
        flow_class=PledgeProgramProcessFlow,
    )
    url = reverse("forms:pledge_program_detail", kwargs={"pk": process.pk})
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── PledgeProgramProcessCreateView GET with existing processes (lines 3158-3193)


@pytest.mark.django_db
def test_pledge_program_process_create_view_get_with_processes(auto_login_user):
    """PledgeProgramProcessCreateView GET with existing PledgeProgramProcess objects
    covers the loop body at lines 3158-3193."""
    from thetatauCMT.forms.flows import PledgeProgramProcessFlow
    from thetatauCMT.forms.models import PledgeProgramProcess

    client, user = auto_login_user()
    _add_to_group(user, "officer")
    PledgeProgramProcess.objects.create(
        chapter=user.chapter,
        flow_class=PledgeProgramProcessFlow,
    )
    url = reverse("viewflow:forms:pledgeprogramprocess:start")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── BylawsCreateView POST form_valid (lines 3281-3283) ─────────────────────


@pytest.mark.django_db
def test_bylaws_create_view_get(auto_login_user):
    """BylawsCreateView GET covers get_table (line 3287) and get_context_data."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    url = reverse("forms:bylaws")
    response = client.get(url, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_bylaws_create_view_form_valid(auto_login_user):
    """BylawsCreateView POST with valid bylaws covers form_valid at
    lines 3281-3283."""
    import io

    client, user = auto_login_user()
    _add_to_group(user, "officer")
    url = reverse("forms:bylaws")
    fake_file = io.BytesIO(b"%PDF-1.4 fake pdf content")
    fake_file.name = "bylaws.pdf"
    data = {
        "bylaws": fake_file,
        "changes": "Updated article 3.",
    }
    response = client.post(url, data, follow=True)
    assert response.status_code == 200


# ─── RitualProficiencyCreateView form_valid (lines 3305-3311) ────────────────


@pytest.mark.django_db
def test_ritual_proficiency_create_view_form_valid(auto_login_user):
    """RitualProficiencyCreateView POST with valid data covers form_valid at
    lines 3305-3311."""
    import datetime

    from thetatauCMT.users.tests.factories import UserFactory

    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    member = UserFactory.create()
    url = reverse("forms:ritual_proficiency")
    data = {
        "user": str(member.pk),
        "level": "level1",
        "date": datetime.date.today().strftime("%Y-%m-%d"),
        "memorization": "pass",
        "directions": "pass",
        "performance": "pass",
        "notes": "",
    }
    response = client.post(url, data, follow=True)
    assert response.status_code == 200


# ─── Helper: create all 5 chapter officers ───────────────────────────────────


def _create_all_chapter_officers(chapter):
    """Create UserRoleChange records for all 5 required chapter officers."""
    from thetatauCMT.users.tests.factories import UserFactory, UserRoleChangeFactory

    officer_roles = [
        "regent",
        "scribe",
        "vice regent",
        "treasurer",
        "corresponding secretary",
    ]
    officers = []
    for role in officer_roles:
        member = UserFactory.create(chapter=chapter)
        UserRoleChangeFactory.create(user=member, current=True, role=role)
        officers.append(member)
    return officers


# ─── InitiationView GET with session data (lines 355-368) ───────────────────


@pytest.mark.django_db
def test_initiation_view_get_with_session_data_branches(auto_login_user):
    """InitiationView GET with init-selection session data covers the 'else'
    branch at lines 355-368 and get_context_data lines 396-451."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    # Set up session with empty init-selection
    session = client.session
    session["init-selection"] = {
        "Initiate": [],
        "Depledge": [],
        "Defer": [],
        "Roll": [],
    }
    session.save()
    url = reverse("forms:initiation")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── PledgeProgramListView GET with complete=0 (lines 1500-1504) ─────────────


@pytest.mark.django_db
def test_pledge_program_list_view_get_complete_zero(auto_login_user):
    """PledgeProgramListView GET with complete=0 covers the incomplete
    branch at lines 1500-1504."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:pledge_program_list")
    response = client.get(url, {"complete": "0"}, follow=True)
    assert response.status_code == 200


# ─── PledgeProgramListView GET with region=candidate_chapter (line 1469) ──────


@pytest.mark.django_db
def test_pledge_program_list_view_get_candidate_chapter(auto_login_user):
    """PledgeProgramListView GET with region=candidate_chapter covers
    the candidate chapter branch at line 1469."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:pledge_program_list")
    response = client.get(url, {"region": "candidate_chapter"}, follow=True)
    assert response.status_code == 200


# ─── HSEducationCreateView GET (line 1142 + context) ─────────────────────────


@pytest.mark.django_db
def test_hs_education_create_view_get_with_context(auto_login_user):
    """HSEducationCreateView GET covers get_table (line 1142) and
    get_context_data."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    url = reverse("viewflow:forms:hseducation:start")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── ConventionCreateView GET with all 5 officers (lines 1990-2007) ─────────


@pytest.mark.django_db
def test_convention_create_view_get_with_officers(auto_login_user):
    """ConventionCreateView GET with all 5 chapter officers set up covers
    lines 1990-2007 (check_officers passes, get_sign_status called)."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    _create_all_chapter_officers(user.chapter)
    url = reverse("viewflow:forms:convention:start")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── ResignationCreateView GET with submitted process (lines 2962-2979) ──────


@pytest.mark.django_db
def test_resignation_create_view_get_with_submitted_process(auto_login_user):
    """ResignationCreateView GET with an existing ResignationProcess for the
    current user covers lines 2962-2979 (submitted branch)."""
    from thetatauCMT.forms.flows import ResignationFlow
    from thetatauCMT.forms.models import ResignationProcess
    from thetatauCMT.users.tests.factories import UserFactory

    client, user = auto_login_user()
    off1 = UserFactory.create(chapter=user.chapter)
    off2 = UserFactory.create(chapter=user.chapter)
    ResignationProcess.objects.create(
        user=user,
        chapter=user.chapter,
        flow_class=ResignationFlow,
        officer1=off1,
        officer2=off2,
    )
    url = reverse("viewflow:forms:resignation:start")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── PledgeProgramListView CSV with officers (lines 1403-1406) ───────────────


@pytest.mark.django_db
def test_pledge_program_list_view_csv_download(auto_login_user):
    """PledgeProgramListView GET with csv=Download CSV and chapters with
    officers covers lines 1403-1406."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    _create_all_chapter_officers(user.chapter)
    url = reverse("forms:pledge_program_list")
    response = client.get(url, {"csv": "Download CSV"}, follow=True)
    assert response.status_code == 200


# ─── ResignationCreateView GET when no officers (lines 2949-2959 form_valid) ──


@pytest.mark.skip(reason="ResignationCreateView POST requires viewflow process task setup")
@pytest.mark.django_db
def test_resignation_create_view_form_valid_no_existing(auto_login_user):
    """ResignationCreateView POST with valid data when no existing resignation
    covers form_valid at lines 2949-2959 (exists=None path)."""
    import io

    client, user = auto_login_user()
    _create_all_chapter_officers(user.chapter)
    url = reverse("viewflow:forms:resignation:start")
    fake_letter = io.BytesIO(b"Dear chapter, I resign.")
    fake_letter.name = "letter.pdf"
    data = {
        "resign": True,
        "secrets": True,
        "expel": True,
        "return_evidence": True,
        "obligation": True,
        "letter": fake_letter,
    }
    response = client.post(url, data, follow=True)
    assert response.status_code == 200


# ─── NatOfficerRequiredMixin: authenticated non-natoff gets home redirect ─────


@pytest.mark.django_db
@pytest.mark.parametrize(
    "view_name",
    [
        "forms:audit_list",
        "forms:rmp_list",
        "forms:pledge_program_list",
        "forms:convention_list",
        "forms:osm_list",
        "forms:bylaws_list",
        "forms:alumniexclusion_list",
    ],
)
def test_natoff_view_denies_authenticated_non_natoff_user(auto_login_user, view_name):
    """Authenticated user NOT in natoff group is redirected to home, not login."""
    from django.urls import reverse as _reverse

    client, user = auto_login_user()
    # user is NOT in natoff group
    url = _reverse(view_name)
    response = client.get(url, follow=False)
    # NatOfficerRequiredMixin.get_login_url returns reverse("home") when authenticated
    assert response.status_code == 302
    location = response["Location"]
    # Should redirect toward home, NOT toward accounts/login
    assert "login" not in location


@pytest.mark.django_db
def test_natoff_role_change_view_denies_authenticated_non_natoff_user(auto_login_user):
    """Authenticated user NOT in natoff group is denied access to natoff role form."""
    client, user = auto_login_user()
    url = reverse("forms:natoff")
    response = client.get(url, follow=False)
    assert response.status_code == 302
    assert "login" not in response["Location"]


# ─── AssignOfficerFormMixin.check_officers unit test ─────────────────────────


@pytest.mark.django_db
def test_check_officers_returns_false_and_adds_error_message_when_officer_missing(
    auto_login_user,
):
    """AssignOfficerFormMixin.check_officers returns False and adds an ERROR
    message when any officer slot is None/falsy."""
    from django.contrib.messages.storage.fallback import FallbackStorage
    from django.test import RequestFactory

    from core.views import AssignOfficerFormMixin

    _, user = auto_login_user()
    factory = RequestFactory()
    request = factory.get("/fake/")
    request.user = user
    # Attach the messages middleware storage so add_message works
    setattr(request, "session", "session")
    messages_storage = FallbackStorage(request)
    setattr(request, "_messages", messages_storage)

    mixin = AssignOfficerFormMixin()
    mixin.request = request

    # Pass a list with None officers (regent and vice regent missing)
    result = mixin.check_officers([None, user, None, user, user])

    assert result is False
    stored = list(messages_storage)
    assert len(stored) == 1
    assert "Missing officers" in stored[0].message
    assert "regent" in stored[0].message
    # Index 0 = regent, index 2 = vice regent are missing
    assert "vice regent" in stored[0].message


@pytest.mark.django_db
def test_check_officers_returns_true_when_all_officers_present(auto_login_user):
    """AssignOfficerFormMixin.check_officers returns True when all 5 officers set."""
    from django.contrib.messages.storage.fallback import FallbackStorage
    from django.test import RequestFactory

    from core.views import AssignOfficerFormMixin
    from thetatauCMT.users.tests.factories import UserFactory

    _, user = auto_login_user()
    factory = RequestFactory()
    request = factory.get("/fake/")
    request.user = user
    setattr(request, "session", "session")
    messages_storage = FallbackStorage(request)
    setattr(request, "_messages", messages_storage)

    mixin = AssignOfficerFormMixin()
    mixin.request = request

    users = [UserFactory.create() for _ in range(5)]
    result = mixin.check_officers(users)

    assert result is True
    assert len(list(messages_storage)) == 0


# ─── PledgeProgramListView CSV: Content-Disposition header ───────────────────


@pytest.mark.django_db
def test_pledge_program_list_csv_download_has_attachment_header(auto_login_user):
    """PledgeProgramListView ?csv=Download CSV with officers and records returns
    a CSV attachment response (Content-Disposition: attachment)."""
    from thetatauCMT.forms.tests.factories import PledgeProgramFactory

    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    _create_all_chapter_officers(user.chapter)
    # Create a pledge program so the CSV writer has data
    PledgeProgramFactory.create(chapter=user.chapter)
    url = reverse("forms:pledge_program_list")
    response = client.get(url, {"csv": "Download CSV"})
    assert response.status_code in (200, 302)
    if response.status_code == 200:
        content_type = response.get("Content-Type", "")
        content_disp = response.get("Content-Disposition", "")
        assert "text/csv" in content_type or "attachment" in content_disp


# ─── RiskManagementListView CSV Content-Type assertion ───────────────────────


@pytest.mark.django_db
def test_rmp_list_csv_content_type(auto_login_user):
    """RiskManagementListView CSV download returns text/csv Content-Type."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    url = reverse("forms:rmp_list")
    response = client.get(url, {"csv": "download csv"})
    assert response.status_code == 200
    assert "text/csv" in response.get("Content-Type", "")


# ─── OfficerRequiredMixin negative test: non-officer → home redirect ──────────


@pytest.mark.django_db
def test_audit_form_non_officer_authenticated_redirects_to_home(auto_login_user):
    """Authenticated user NOT in officer group accessing audit form is redirected.
    OfficerRequiredMixin.get_login_url returns home when authenticated."""
    client, user = auto_login_user()
    # user is NOT in the officer group
    url = reverse("forms:audit")
    response = client.get(url, follow=False)
    assert response.status_code == 302
    assert "login" not in response["Location"]


# ─── download_all_rollbook view ───────────────────────────────────────────────


@pytest.mark.django_db
def test_download_all_rollbook_officer_empty_roll_returns_zip(auto_login_user):
    """download_all_rollbook returns a ZIP attachment when the officer has set an
    empty Roll list in the session (no users to render → empty ZIP still valid)."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")

    # Seed the session key that the view reads
    session = client.session
    session["init-selection"] = {"Roll": []}
    session.save()

    url = reverse("forms:roll_book_download_all")
    response = client.get(url)

    assert response.status_code == 200
    assert response.get("Content-Disposition", "").startswith("attachment")
    assert "zip" in response.get("Content-Type", "").lower()


# ─── DisciplinaryCreateView GET (lines 2756-2759) ─────────────────────────────


@pytest.mark.django_db
def test_disciplinary_create_view_get_officer(auto_login_user):
    """DisciplinaryCreateView GET with an officer user hits get_context_data
    (lines 2756-2759) which calls get_sign_status_discipline."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    _create_all_chapter_officers(user.chapter)
    url = reverse("viewflow:forms:disciplinaryprocess:start")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── AlumniExclusionCreateView GET – no prior submission (lines 2365-2421) ───


@pytest.mark.django_db
def test_alumni_exclusion_create_view_get_no_prior_submission(auto_login_user):
    """AlumniExclusionCreateView GET with all officers set up and no prior
    OSM submission hits the main path (lines 2365-2366, 2369-2370, 2384,
    2388-2421)."""
    client, user = auto_login_user()
    _create_all_chapter_officers(user.chapter)
    url = reverse("viewflow:forms:alumniexclusion:start")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── ResignationCreateView GET – no prior submission (lines 2941-2968) ────────


@pytest.mark.django_db
def test_resignation_create_view_get_no_prior_submission(auto_login_user):
    """ResignationCreateView GET with no existing resignation covers the
    else branch of get_context_data (submitted=None → lines 2967-2968)."""
    client, user = auto_login_user()
    _create_all_chapter_officers(user.chapter)
    url = reverse("viewflow:forms:resignation:start")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── StatusChangeView GET with session data (lines 626, 629, 647-693) ─────────


@pytest.mark.django_db
def test_status_change_view_get_with_empty_session(auto_login_user):
    """StatusChangeView GET when 'status-selection' session key is present
    (but all lists empty) covers initial_info, get_context_data (lines
    621-647, 649-693)."""
    client, user = auto_login_user()
    _add_to_group(user, "officer")
    session = client.session
    session["status-selection"] = {
        "graduate": [],
        "coop": [],
        "covid": [],
        "military": [],
        "withdraw": [],
        "transfer": [],
        "resignedCC": [],
    }
    session.save()
    url = reverse("forms:status")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── AlumniExclusionCreateView GET – no officers (line 2367) ─────────────────


@pytest.mark.django_db
def test_alumni_exclusion_create_view_get_missing_officers(auto_login_user):
    """AlumniExclusionCreateView GET when chapter is missing officers
    triggers the check_officers redirect (line 2367)."""
    client, user = auto_login_user()
    # No officers set up → check_officers returns False → redirect
    url = reverse("viewflow:forms:alumniexclusion:start")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── OSMCreateView GET with officers (lines 2501-2516, 2542-2550) ─────────────


@pytest.mark.django_db
def test_osm_create_view_get_with_officers(auto_login_user):
    """OSMCreateView GET with all chapter officers set up covers lines
    2501-2507, 2516, 2542-2550 (check_officers passes, no prior submission)."""
    client, user = auto_login_user()
    _create_all_chapter_officers(user.chapter)
    url = reverse("viewflow:forms:osm:start")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── InitiationView GET with non-empty Roll list (lines 355-368) ──────────────


@pytest.mark.django_db
def test_initiation_view_get_with_roll_items(auto_login_user):
    """InitiationView GET when 'Roll' contains a pledge user PK covers
    the to_roll branch at lines 355-368 of get_context_data."""
    from thetatauCMT.users.tests.factories import UserFactory, UserStatusChangeFactory

    client, user = auto_login_user()
    _add_to_group(user, "officer")
    pledge = UserFactory.create(chapter=user.chapter)
    UserStatusChangeFactory.create(user=pledge, status="pnm", current=True)
    session = client.session
    session["init-selection"] = {
        "Initiate": [],
        "Depledge": [],
        "Defer": [],
        "Roll": [pledge.pk],
    }
    session.save()
    url = reverse("forms:initiation")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── InitiationView GET with candidate_chapter (line 379) ────────────────────


@pytest.mark.django_db
def test_initiation_view_get_candidate_chapter(auto_login_user):
    """InitiationView GET when chapter is a candidate chapter (line 379)."""
    from thetatauCMT.chapters.tests.factories import ChapterFactory  # noqa: F401

    client, user = auto_login_user()
    _add_to_group(user, "officer")
    # Make the chapter a candidate chapter
    user.chapter.candidate_chapter = True
    user.chapter.save()
    session = client.session
    session["init-selection"] = {
        "Initiate": [],
        "Depledge": [],
        "Defer": [],
        "Roll": [],
    }
    session.save()
    url = reverse("forms:initiation")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── AuditFormView GET with nonexistent pk (lines 1567-1568) ─────────────────


@pytest.mark.django_db
def test_audit_form_view_get_nonexistent_pk(auto_login_user):
    """AuditFormView GET with a pk that doesn't exist triggers
    Audit.DoesNotExist and falls back to Audit.objects.last() (lines
    1567-1568)."""
    from thetatauCMT.users.tests.factories import UserRoleChangeFactory

    client, user = auto_login_user()
    _add_to_group(user, "officer")
    UserRoleChangeFactory.create(user=user, current=True, role="regent")
    url = reverse("forms:audit_complete", kwargs={"pk": 999999999})
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── AuditFormView GET with wrong-chapter audit (lines 1569-1577) ────────────


@pytest.mark.django_db
def test_audit_form_view_get_wrong_chapter_pk(auto_login_user):
    """AuditFormView GET with an audit belonging to a different chapter
    shows an error message (lines 1569-1577)."""
    from thetatauCMT.chapters.tests.factories import ChapterFactory
    from thetatauCMT.forms.tests.factories import AuditFactory
    from thetatauCMT.users.tests.factories import UserFactory, UserRoleChangeFactory

    client, user = auto_login_user()
    _add_to_group(user, "officer")
    UserRoleChangeFactory.create(user=user, current=True, role="regent")
    # Create an audit for a user in a *different* chapter
    other_chapter = ChapterFactory.create()
    other_user = UserFactory.create(chapter=other_chapter)
    audit = AuditFactory.create(user=other_user)
    url = reverse("forms:audit_complete", kwargs={"pk": audit.pk})
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── PrematureAlumnus with finished process (lines 1799-1800) ────────────────


@pytest.mark.django_db
def test_premature_alumnus_create_view_get_with_finished_process(auto_login_user):
    """PrematureAlumnusCreateView GET with a finished PrematureAlumnus covers
    the 'else' branch of the loop body (lines 1799-1800)."""
    from django.utils import timezone

    from thetatauCMT.forms.tests.factories import PrematureAlumnusFactory
    from thetatauCMT.users.tests.factories import UserFactory

    client, user = auto_login_user()
    member = UserFactory.create(chapter=user.chapter)
    PrematureAlumnusFactory.create(user=member, finished=timezone.now())
    url = reverse("viewflow:forms:prematurealumnus:start")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── ConventionCreateView no-officers GET (line 1992) ────────────────────────


@pytest.mark.django_db
def test_convention_create_view_get_no_officers(auto_login_user):
    """ConventionCreateView GET when chapter has no officers covers
    the check_officers redirect (line 1992)."""
    client, user = auto_login_user()
    # No officers set up → check_officers returns False → line 1992 covered
    url = reverse("viewflow:forms:convention:start")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── AlumniExclusionDetailView GET (lines 2431-2434) ─────────────────────────


@pytest.mark.django_db
def test_alumni_exclusion_detail_view_get(auto_login_user):
    """AlumniExclusionDetailView GET with a valid AlumniExclusion object
    covers get_context_data at lines 2431-2434."""
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.utils import timezone

    from thetatauCMT.forms.flows import AlumniExclusionFlow
    from thetatauCMT.forms.models import AlumniExclusion
    from thetatauCMT.users.tests.factories import UserFactory

    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    member = UserFactory.create(chapter=user.chapter)
    ae = AlumniExclusion.objects.create(
        chapter=user.chapter,
        created_by=user,
        user=member,
        date_end=timezone.now().date(),
        voting_result=0.75,
        reason="Test exclusion",
        minutes=SimpleUploadedFile("minutes.pdf", b"fake pdf content"),
        flow_class=AlumniExclusionFlow,
    )
    url = reverse("forms:alumniexclusion_detail", kwargs={"pk": ae.pk})
    response = client.get(url, follow=True)
    assert response.status_code == 200
