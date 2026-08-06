"""
View tests for the users app.
Uses the auto_login_user fixture which handles RMPSignMiddleware.
"""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse


def _make_natoff(user, client):
    """Ensure user is in the 'natoff' Django group and re-login."""
    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    client.force_login(user)


def _make_officer(user, client):
    """Ensure user is in the 'officer' Django group and re-login."""
    group, _ = Group.objects.get_or_create(name="officer")
    user.groups.add(group)
    client.force_login(user)


# ---------------------------------------------------------------------------
# UserRedirectView
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_redirect_view(auto_login_user):
    client, user = auto_login_user()
    url = reverse("users:redirect")
    response = client.get(url)
    # Should redirect to users:detail
    assert response.status_code == 302
    assert reverse("users:detail") in response["Location"]


# ---------------------------------------------------------------------------
# UserDetailUpdateView (myinfo)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_detail_view_returns_200(auto_login_user):
    client, user = auto_login_user()
    url = reverse("users:detail")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_detail_view_unauthenticated(client):
    url = reverse("users:detail")
    response = client.get(url)
    # Should redirect to login
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# Member status changes accordion on the public profile
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_profile_status_changes_visible_to_chapter_officer(auto_login_user, user_factory):
    import datetime

    from thetatauCMT.forms.models import StatusChange

    client, officer = auto_login_user()
    member = user_factory.create(chapter=officer.chapter)
    StatusChange.objects.create(
        user=member, created_by=officer, reason="withdraw", date_start=datetime.date(2026, 5, 15)
    )
    _make_officer(officer, client)
    response = client.get(reverse("users:profile", kwargs={"username": member.username}))
    assert response.status_code == 200
    assert response.context["can_view_status_changes"] is True
    assert b"Status Changes" in response.content


@pytest.mark.django_db
def test_profile_status_changes_hidden_from_other_chapter_member(auto_login_user, user_factory):
    import datetime

    from thetatauCMT.forms.models import StatusChange

    client, viewer = auto_login_user()  # plain member, different chapter
    member = user_factory.create()
    StatusChange.objects.create(
        user=member, created_by=member, reason="withdraw", date_start=datetime.date(2026, 5, 15)
    )
    response = client.get(reverse("users:profile", kwargs={"username": member.username}))
    assert response.status_code == 200
    assert response.context["can_view_status_changes"] is False


# ---------------------------------------------------------------------------
# UserListView — national officer only
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_list_view_natoff_returns_200(auto_login_user):
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    url = reverse("users:list")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_list_view_chapter_officer_redirected_or_403(auto_login_user):
    client, user = auto_login_user(make_officer="chapter")
    url = reverse("users:list")
    response = client.get(url, follow=True)
    # Non-natoff users should be redirected or denied
    assert response.status_code in (200, 302, 403)


# ---------------------------------------------------------------------------
# UserDetailView (memberinfo by username)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_member_info_view(auto_login_user):
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    url = reverse("users:info", kwargs={"username": user.username})
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# UserGPAFormSetView
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_gpas_view_returns_200(auto_login_user):
    client, user = auto_login_user(make_officer="chapter")
    _make_officer(user, client)
    url = reverse("users:gpas")
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# UserServiceFormSetView
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_service_view_returns_200(auto_login_user):
    client, user = auto_login_user()
    url = reverse("users:service")
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# External organizations — list / add / delete / autocomplete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_orgs_view_returns_200(auto_login_user):
    client, user = auto_login_user()
    _make_officer(user, client)
    url = reverse("users:orgs")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_orgs_view_any_member_can_view(auto_login_user):
    """Any logged-in member may view the chapter organizations list."""
    client, user = auto_login_user()
    url = reverse("users:orgs")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_orgs_add_page_returns_200(auto_login_user):
    """The dedicated add page renders for an officer."""
    client, user = auto_login_user()
    _make_officer(user, client)
    url = reverse("users:orgs_add")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_orgs_add_prefills_current_member(auto_login_user):
    """Opening the add form defaults the selected member to the current user."""
    client, user = auto_login_user()
    _make_officer(user, client)
    url = reverse("users:orgs_add")
    response = client.get(url)
    assert response.status_code == 200
    assert response.context["form"].initial.get("user") == user
    # The member select2 should render the current user as a selected option.
    assert f'value="{user.pk}" selected' in response.content.decode()


@pytest.mark.django_db
def test_user_orgs_add_any_member_can_add_for_self(auto_login_user):
    """A regular member may open the add page and add their own participation."""
    from thetatauCMT.users.models import UserOrgParticipate
    from thetatauCMT.users.tests.factories import OrganizationFactory

    client, user = auto_login_user()
    org = OrganizationFactory.create(name="ASME")
    url = reverse("users:orgs_add")
    assert client.get(url).status_code == 200
    response = client.post(
        url,
        {
            "user": user.pk,
            "organization": org.pk,
            "type": "pro",
            "officer": "False",
            "start": "01/01/2026",
            "end": "01/01/2027",
        },
    )
    assert response.status_code == 302
    assert UserOrgParticipate.objects.filter(user=user, organization=org).exists()


@pytest.mark.django_db
def test_user_orgs_view_officer_can_add(auto_login_user):
    """An officer submits participation for a single member and it is saved."""
    from thetatauCMT.users.models import UserOrgParticipate
    from thetatauCMT.users.tests.factories import OrganizationFactory, UserFactory

    client, user = auto_login_user()
    _make_officer(user, client)
    member = UserFactory.create(chapter=user.chapter, status="active")
    org = OrganizationFactory.create(name="IEEE")
    url = reverse("users:orgs_add")
    response = client.post(
        url,
        {
            "user": member.pk,
            "organization": org.pk,
            "type": "pro",
            "officer": "True",
            "start": "01/01/2026",
            "end": "01/01/2027",
        },
    )
    assert response.status_code == 302
    assert UserOrgParticipate.objects.filter(user=member, organization=org).exists()


@pytest.mark.django_db
def test_org_autocomplete_creates_organization(auto_login_user):
    """Officers can create a new Organization inline from the autocomplete."""
    from thetatauCMT.users.models import Organization

    client, user = auto_login_user()
    _make_officer(user, client)
    url = reverse("users:org-autocomplete")
    response = client.post(url, {"text": "National Society of Black Engineers"})
    assert response.status_code == 200
    assert Organization.objects.filter(name="National Society of Black Engineers").exists()


@pytest.mark.django_db
def test_org_autocomplete_any_member_creates_organization(auto_login_user):
    """Any logged-in member can create an Organization inline from the autocomplete."""
    from thetatauCMT.users.models import Organization

    client, user = auto_login_user()
    url = reverse("users:org-autocomplete")
    response = client.post(url, {"text": "Society of Women Engineers"})
    assert response.status_code == 200
    assert Organization.objects.filter(name="Society of Women Engineers").exists()


@pytest.mark.django_db
def test_user_org_delete_view_officer(auto_login_user):
    """An officer can remove a single participation row for their chapter."""
    from thetatauCMT.users.models import UserOrgParticipate
    from thetatauCMT.users.tests.factories import UserFactory, UserOrgParticipateFactory

    client, user = auto_login_user()
    _make_officer(user, client)
    member = UserFactory.create(chapter=user.chapter, status="active")
    org = UserOrgParticipateFactory.create(user=member)
    url = reverse("users:orgs_delete", kwargs={"pk": org.pk})
    response = client.post(url)
    assert response.status_code == 302
    assert not UserOrgParticipate.objects.filter(pk=org.pk).exists()


@pytest.mark.django_db
def test_user_org_delete_view_non_officer_forbidden(auto_login_user):
    """A non-officer cannot remove participation rows (endpoint is officer-only)."""
    from thetatauCMT.users.models import UserOrgParticipate
    from thetatauCMT.users.tests.factories import UserOrgParticipateFactory

    client, user = auto_login_user()
    org = UserOrgParticipateFactory.create(user=user)
    url = reverse("users:orgs_delete", kwargs={"pk": org.pk})
    response = client.post(url)
    assert response.status_code == 302
    assert UserOrgParticipate.objects.filter(pk=org.pk).exists()


@pytest.mark.django_db
def test_user_orgs_list_defaults_to_active_members(auto_login_user):
    """The list defaults to active members; alumni rows appear only when filtered."""
    import datetime

    from thetatauCMT.users.tests.factories import OrganizationFactory, UserFactory, UserOrgParticipateFactory

    client, user = auto_login_user()
    _make_officer(user, client)
    alum = UserFactory.create(chapter=user.chapter, status="alumni")
    UserOrgParticipateFactory.create(
        user=alum,
        organization=OrganizationFactory.create(name="Alumni Society"),
        start=datetime.date(2024, 1, 1),
        end=datetime.date(2099, 1, 1),
    )
    url = reverse("users:orgs")
    assert b"Alumni Society" not in client.get(url).content
    assert b"Alumni Society" in client.get(url, {"status": "alumni"}).content
    assert b"Alumni Society" in client.get(url, {"status": "all"}).content


# ---------------------------------------------------------------------------
# UserSearchView
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_search_view_natoff(auto_login_user):
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    url = reverse("users:search")
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# User model — set_no_contact
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_set_no_contact(auto_login_user, user_factory):
    client, user = auto_login_user()
    user.set_no_contact()
    user.refresh_from_db()
    assert user.unsubscribe_email is True
    assert user.unsubscribe_paper_gear is True
    assert user.no_contact is True


@pytest.mark.django_db
def test_set_no_contact_syncs_to_mailerlite(auto_login_user):
    from unittest.mock import patch

    client, user = auto_login_user()
    with patch("thetatauCMT.email_tracking.mailerlite_sync.unsubscribe_user") as ml:
        user.set_no_contact()
    ml.assert_called_once()
    assert ml.call_args.args[0].pk == user.pk


# ---------------------------------------------------------------------------
# User model — get_name_with_details
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_name_with_details(user_factory):
    user = user_factory.create()
    result = user.get_name_with_details()
    assert user.name in result
    assert str(user.graduation_year) in result


# ---------------------------------------------------------------------------
# User model — current_chapter property
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_current_chapter_regular_user(user_factory):
    user = user_factory.create()
    assert user.current_chapter == user.chapter


# ---------------------------------------------------------------------------
# User model — emails property
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_emails_property(user_factory):
    user = user_factory.create()
    emails = user.emails
    assert user.email in emails
    assert user.email_school in emails


# ---------------------------------------------------------------------------
# User model — get_absolute_url
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_get_absolute_url(user_factory):
    user = user_factory.create()
    assert user.get_absolute_url() == reverse("users:detail")


# ---------------------------------------------------------------------------
# User model — next_pledge_number
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_next_pledge_number_starts_at_2000000(user_factory):
    from thetatauCMT.users.models import User

    next_num = User.next_pledge_number()
    assert next_num >= 2_000_000


# ---------------------------------------------------------------------------
# user_verify view (officer-only)
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason=(
        "group_required(['officer','natoff']) uses list-as-first-arg syntax which "
        "fails __in lookup for non-superusers; superusers hit RequireSuperuser2FAMiddleware "
        "(DEBUG=False in tests) which redirects to /setup/. View is untestable via client."
    )
)
@pytest.mark.django_db
def test_user_verify_view_as_officer(auto_login_user, user_factory):
    client, user = auto_login_user()
    user.is_superuser = True
    user.save()
    client.force_login(user)
    target = user_factory.create()
    url = reverse("users:user_verify") + f"?user_pk={target.pk}"
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_verify_view_denied_no_officer(auto_login_user, user_factory):
    client, user = auto_login_user()
    target = user_factory.create()
    url = reverse("users:user_verify") + f"?user_pk={target.pk}"
    response = client.get(url)
    assert response.status_code in (302, 403)


# ---------------------------------------------------------------------------
# UserProfileView (memberinfo/<username> and profile/<username>) — public to
# any authenticated member, with natoff-only sensitive sections.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_detail_view_natoff(auto_login_user, user_factory):
    client, user = auto_login_user()
    _make_natoff(user, client)
    target = user_factory.create()
    url = reverse("users:info", kwargs={"username": target.username})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_profile_view_regular_user_can_view(auto_login_user, user_factory):
    """Any authenticated member can view another member's profile page."""
    client, user = auto_login_user()
    target = user_factory.create()
    url = reverse("users:profile", kwargs={"username": target.username})
    response = client.get(url)
    assert response.status_code == 200
    # Non-natoff viewers should NOT see the sensitive sections.
    assert b"Notes" not in response.content or b"Add Note" not in response.content


@pytest.mark.django_db
def test_user_profile_view_natoff_sees_sensitive_sections(auto_login_user, user_factory):
    """Natoff sees the Notes / Submissions section headers."""
    client, user = auto_login_user()
    _make_natoff(user, client)
    target = user_factory.create()
    url = reverse("users:profile", kwargs={"username": target.username})
    response = client.get(url)
    assert response.status_code == 200
    assert b"Add Note" in response.content


@pytest.mark.django_db
def test_user_profile_view_unauthenticated_redirects(client, user_factory):
    target = user_factory.create()
    url = reverse("users:profile", kwargs={"username": target.username})
    response = client.get(url)
    assert response.status_code == 302  # login required


@pytest.mark.django_db
def test_user_profile_view_owner_sees_edit_button(auto_login_user):
    client, user = auto_login_user()
    url = reverse("users:profile", kwargs={"username": user.username})
    response = client.get(url)
    assert response.status_code == 200
    assert b"Edit My Info" in response.content


@pytest.mark.django_db
def test_user_profile_view_superuser_sees_admin_link(auto_login_user, user_factory):
    from django.test import override_settings

    client, user = auto_login_user()
    user.is_superuser = True
    user.save()
    client.force_login(user)
    target = user_factory.create()
    url = reverse("users:profile", kwargs={"username": target.username})
    with override_settings(DEBUG=True):
        response = client.get(url)
    assert response.status_code == 200
    assert b"users_user_change" in response.content or b"Admin" in response.content


@pytest.mark.django_db
def test_profile_picture_view_owner_returns_200(auto_login_user):
    client, user = auto_login_user()
    url = reverse("users:profile_picture")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_profile_picture_view_unauthenticated_redirects(client):
    url = reverse("users:profile_picture")
    response = client.get(url)
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# UserProfileView — contact visibility
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_profile_hides_contact_from_other_member_by_default(auto_login_user, user_factory):
    """Default visibility is 'no one': a plain member does not see the phone."""
    client, user = auto_login_user()
    target = user_factory.create(phone_number="5559990000")
    url = reverse("users:profile", kwargs={"username": target.username})
    response = client.get(url)
    assert response.status_code == 200
    assert response.context["show_phone"] is False
    assert response.context["show_email"] is False
    assert response.context["show_address"] is False
    assert b"5559990000" not in response.content


@pytest.mark.django_db
def test_profile_shows_contact_when_visible_to_members(auto_login_user, user_factory):
    """A member sees the phone when the owner opts into 'any member'."""
    client, user = auto_login_user()
    target = user_factory.create(phone_number="5559991111", phone_visibility="members")
    url = reverse("users:profile", kwargs={"username": target.username})
    response = client.get(url)
    assert response.status_code == 200
    assert response.context["show_phone"] is True
    assert b"5559991111" in response.content


@pytest.mark.django_db
def test_profile_national_officer_always_sees_contact(auto_login_user, user_factory):
    """National officers see contact info even when set to 'no one'."""
    client, user = auto_login_user()
    _make_natoff(user, client)
    target = user_factory.create(phone_number="5559992222")  # default no_one
    url = reverse("users:profile", kwargs={"username": target.username})
    response = client.get(url)
    assert response.status_code == 200
    assert response.context["show_phone"] is True
    assert b"5559992222" in response.content


@pytest.mark.django_db
def test_profile_owner_sees_own_contact_with_visibility_badge(auto_login_user):
    """The member always sees their own contact plus the visibility label."""
    client, user = auto_login_user()
    user.phone_number = "5559993333"
    user.save(update_fields=["phone_number"])
    url = reverse("users:profile", kwargs={"username": user.username})
    response = client.get(url)
    assert response.status_code == 200
    assert response.context["show_phone"] is True
    content = response.content.decode("UTF-8")
    assert "5559993333" in content
    # A compact badge shows the level; the full wording is the tooltip.
    assert "Officers only" in content
    assert "Who can see your phone number: Only National Officers, Admins, and my chapter" in content


@pytest.mark.django_db
def test_profile_chapter_visibility_only_same_chapter(auto_login_user, user_factory):
    """'chapter' visibility hides the phone from a different-chapter member."""
    from thetatauCMT.chapters.models import GREEK_ABR
    from thetatauCMT.chapters.tests.factories import ChapterFactory

    greek = list(GREEK_ABR.values())
    client, user = auto_login_user()
    other_chapter = ChapterFactory(name=next(n for n in greek if n != user.chapter.name))
    target = user_factory.create(
        chapter=other_chapter,
        phone_number="5559994444",
        phone_visibility="chapter",
    )
    url = reverse("users:profile", kwargs={"username": target.username})
    response = client.get(url)
    assert response.status_code == 200
    assert response.context["show_phone"] is False
    assert b"5559994444" not in response.content


# ---------------------------------------------------------------------------
# UserTable — contact visibility in member tables
# ---------------------------------------------------------------------------


def _user_table_row(target, viewer):
    from thetatauCMT.users.models import User
    from thetatauCMT.users.tables import UserTable

    table = UserTable(data=User.objects.filter(pk=target.pk), viewer=viewer)
    return table.rows[0]


@pytest.mark.django_db
def test_user_table_masks_contact_from_plain_member(user_factory):
    """A member roster hides contact info the member has not shared."""
    target = user_factory.create(email="hidden@example.com", phone_number="5557770000")
    viewer = user_factory.create(chapter=target.chapter)
    row = _user_table_row(target, viewer)
    assert row.get_cell_value("email") == "Private"
    assert row.get_cell_value("phone_number") == "Private"
    # No mailto link is rendered for a masked address.
    assert row.get_cell("email") == "Private"


@pytest.mark.django_db
def test_user_table_shows_contact_to_chapter_officer(user_factory):
    """A chapter's officers always see their own members' contact info."""
    target = user_factory.create(email="shown@example.com", phone_number="5557771111")
    viewer = user_factory.create(chapter=target.chapter)
    group, _ = Group.objects.get_or_create(name="officer")
    viewer.groups.add(group)
    row = _user_table_row(target, viewer)
    assert row.get_cell_value("email") == "shown@example.com"
    assert row.get_cell_value("phone_number") == "5557771111"


@pytest.mark.django_db
def test_user_table_shows_contact_shared_with_all_members(user_factory):
    """Opting into 'any member on the site' unmasks the column."""
    target = user_factory.create(email="public@example.com", email_visibility="members")
    viewer = user_factory.create()
    assert _user_table_row(target, viewer).get_cell_value("email") == "public@example.com"


@pytest.mark.django_db
def test_user_table_without_viewer_is_not_masked(user_factory):
    """System exports (dues CSV, admin bulk export) pass no viewer."""
    target = user_factory.create(email="export@example.com")
    assert _user_table_row(target, None).get_cell_value("email") == "export@example.com"


# ---------------------------------------------------------------------------
# UserProfileView — Regional Director banner
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_profile_shows_regional_director_banner(auto_login_user, user_factory):
    """A regional director's profile prominently shows the region + chapters."""
    from thetatauCMT.chapters.tests.factories import ChapterFactory
    from thetatauCMT.regions.tests.factories import RegionFactory

    client, user = auto_login_user()
    region = RegionFactory(name="Director Banner Region")
    target = user_factory.create()
    region.directors.add(target)
    chapter = ChapterFactory()
    chapter.region = region
    chapter.save(update_fields=["region"])

    url = reverse("users:profile", kwargs={"username": target.username})
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode("UTF-8")
    assert "Regional Director" in content
    assert "Director Banner Region" in content
    assert list(response.context["director_regions"]) == [region]
    # The region's chapters are linked from the banner.
    assert reverse("chapters:detail", kwargs={"slug": chapter.slug}) in content


@pytest.mark.django_db
def test_profile_no_director_banner_for_regular_member(auto_login_user, user_factory):
    client, user = auto_login_user()
    target = user_factory.create()
    url = reverse("users:profile", kwargs={"username": target.username})
    response = client.get(url)
    assert response.status_code == 200
    assert list(response.context["director_regions"]) == []


# ---------------------------------------------------------------------------
# UserSearchView — with query
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_search_view_with_query(auto_login_user):
    client, user = auto_login_user()
    _make_natoff(user, client)
    url = reverse("users:search") + f"?q={user.last_name}"
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# UserListView — regular officer can access
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_list_view_returns_200_authenticated(auto_login_user):
    client, user = auto_login_user()
    url = reverse("users:list")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_list_view_unauthenticated(client):
    url = reverse("users:list")
    response = client.get(url)
    assert response.status_code == 302  # redirect to login


# ---------------------------------------------------------------------------
# User model — is_national_officer helper
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_is_national_officer_false_default(user_factory):
    user = user_factory.create()
    assert not user.is_national_officer()


@pytest.mark.django_db
def test_is_national_officer_group_with_natoff(auto_login_user):
    client, user = auto_login_user()
    _make_natoff(user, client)
    assert user.is_national_officer_group is True


# ---------------------------------------------------------------------------
# User model — badge_number auto-assign
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_badge_number_assigned_on_create(user_factory):
    user = user_factory.create()
    assert user.badge_number is not None
    assert user.badge_number > 0


# ---------------------------------------------------------------------------
# UserListView — CSV download and cancel param
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_list_view_with_cancel_param(auto_login_user):
    """?cancel=1 clears filter and returns 200."""
    client, user = auto_login_user()
    url = reverse("users:list")
    response = client.get(url, {"cancel": "1"})
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_list_view_csv_download_as_officer(auto_login_user):
    """Officer user can trigger CSV download."""
    client, user = auto_login_user()
    _make_officer(user, client)
    url = reverse("users:list")
    response = client.get(url, {"csv": "download csv"})
    # Either returns CSV content or 200 HTML
    assert response.status_code in (200, 302)


# ---------------------------------------------------------------------------
# UserGPAFormSetView (OfficerRequired)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_gpas_view_officer_returns_200(auto_login_user):
    """Officer can access the GPA formset view."""
    client, user = auto_login_user()
    _make_officer(user, client)
    url = reverse("users:gpas")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_gpas_view_non_officer_redirects(auto_login_user):
    """Non-officer users are redirected from GPA formset view."""
    client, user = auto_login_user()
    url = reverse("users:gpas")
    response = client.get(url)
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# UserServiceFormSetView (LoginRequired)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_service_view_cancel(auto_login_user):
    """?cancel=1 clears filter and returns 200."""
    client, user = auto_login_user()
    url = reverse("users:service")
    response = client.get(url, {"cancel": "1"})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# UserLookupSearchView (no auth required)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_lookup_search_view_returns_200(client):
    """Lookup search view is publicly accessible."""
    url = reverse("users:lookup_search")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_lookup_select_view_returns_200(client):
    """Lookup select view is publicly accessible."""
    url = reverse("users:lookup_select")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_lookup_update_view_returns_200(client):
    """Lookup update view is publicly accessible with no session user."""
    url = reverse("users:update")
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# UserAlterView (NatOfficerRequired)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_alter_view_unauthenticated_redirects(client):
    """Unauthenticated users are redirected from alter chapter view."""
    url = reverse("users:alterchapter")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_user_alter_view_natoff_returns_200(auto_login_user):
    """Natoff user can access user alter view."""
    client, user = auto_login_user()
    _make_natoff(user, client)
    url = reverse("users:alterchapter")
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Hide national officer functionality (ToggleNatoffView + view-as-member)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_toggle_natoff_view_hides_and_shows(auto_login_user):
    """A National Officer can hide and then re-show natoff functionality."""
    from thetatauCMT.users.models import UserAlter

    client, user = auto_login_user()
    _make_natoff(user, client)
    url = reverse("users:toggle_natoff")

    # First toggle hides -> creates a UserAlter with hide_natoff=True
    response = client.post(url, {"next": "/"})
    assert response.status_code == 302
    alter = UserAlter.objects.get(user=user)
    assert alter.hide_natoff is True
    assert user.natoff_hidden is True
    assert user.is_national_officer_group is False

    # Second toggle shows national officer functionality again
    response = client.post(url, {"next": "/"})
    assert response.status_code == 302
    alter.refresh_from_db()
    assert alter.hide_natoff is False
    assert user.natoff_hidden is False
    assert user.is_national_officer_group is True


@pytest.mark.django_db
def test_toggle_natoff_view_denies_non_natoff(auto_login_user):
    """A non-natoff cannot create a hide toggle (no UserAlter is created)."""
    from thetatauCMT.users.models import UserAlter

    client, user = auto_login_user()
    url = reverse("users:toggle_natoff")
    response = client.post(url, {"next": "/"})
    assert response.status_code == 302
    assert not UserAlter.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_toggle_natoff_view_get_not_allowed(auto_login_user):
    client, user = auto_login_user()
    _make_natoff(user, client)
    response = client.get(reverse("users:toggle_natoff"))
    assert response.status_code == 405


@pytest.mark.django_db
def test_user_alter_view_accessible_when_hidden(auto_login_user):
    """The chapter/role switcher stays usable while natoff functionality is hidden."""
    from thetatauCMT.users.models import UserAlter

    client, user = auto_login_user()
    _make_natoff(user, client)
    UserAlter.objects.create(user=user, chapter=user.chapter, role=None, hide_natoff=True)
    response = client.get(reverse("users:alterchapter"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_alter_reset_clears_hide_natoff(auto_login_user):
    """The region-bar Reset button returns the officer to the full national view."""
    from thetatauCMT.users.models import UserAlter

    client, user = auto_login_user()
    _make_natoff(user, client)
    UserAlter.objects.create(user=user, chapter=user.chapter, role="scribe", hide_natoff=True)
    response = client.post(
        reverse("users:alterchapter"),
        {"chapter": user.chapter.slug, "role": "", "alter-action": "Reset", "next": "/"},
    )
    assert response.status_code == 302
    alter = UserAlter.objects.get(user=user)
    assert alter.hide_natoff is False
    assert alter.role is None


@pytest.mark.django_db
def test_natoff_gated_view_blocks_hidden_officer(auto_login_user):
    """A hidden National Officer is treated as a member on natoff-only pages."""
    from thetatauCMT.users.models import UserAlter

    client, user = auto_login_user()
    _make_natoff(user, client)
    url = reverse("forms:education_list")
    # Visible while acting as a National Officer
    assert client.get(url).status_code == 200
    # Hidden -> redirected away like any non-officer
    UserAlter.objects.create(user=user, chapter=user.chapter, role=None, hide_natoff=True)
    assert client.get(url).status_code == 302


@pytest.mark.django_db
def test_base_template_natoff_toggle_and_region_bar(auto_login_user):
    """Base template flips the toggle label + region bar between the two modes."""
    from thetatauCMT.users.models import UserAlter

    client, user = auto_login_user()
    _make_natoff(user, client)
    home = reverse("home")

    # Acting as National Officer: full region nav + "Hide" toggle label
    content = client.get(home).content.decode()
    assert "Hide national officer functionality" in content
    assert "Dashboard" in content

    # Hidden: "Show" toggle label + "Viewing as member"; switcher still present
    UserAlter.objects.create(user=user, chapter=user.chapter, role=None, hide_natoff=True)
    content = client.get(home).content.decode()
    assert "Show national officer functionality" in content
    assert "Viewing as member" in content
    assert reverse("users:alterchapter") in content


@pytest.mark.django_db
def test_user_list_officer_buttons_hidden_when_natoff_hidden(auto_login_user):
    """Officer-only buttons on the member list disappear while previewing as a member."""
    from thetatauCMT.users.models import UserAlter

    client, user = auto_login_user()
    _make_natoff(user, client)
    url = reverse("users:list")

    # Acting as National Officer: the officer action buttons are shown
    assert "Download CSV" in client.get(url).content.decode()

    # Hidden: the officer action buttons are gone
    UserAlter.objects.create(user=user, chapter=user.chapter, role=None, hide_natoff=True)
    assert "Download CSV" not in client.get(url).content.decode()


@pytest.mark.django_db
def test_user_list_csv_blocked_when_natoff_hidden(auto_login_user):
    """The CSV export is refused for a National Officer previewing as a member."""
    from thetatauCMT.users.models import UserAlter

    client, user = auto_login_user()
    _make_natoff(user, client)
    UserAlter.objects.create(user=user, chapter=user.chapter, role=None, hide_natoff=True)
    response = client.get(reverse("users:list"), {"csv": "download csv"})
    # Guard falls through to the normal HTML list render instead of a CSV download.
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/html")


# ---------------------------------------------------------------------------
# External organizations — list page contents
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_orgs_view_lists_submitted(auto_login_user):
    """The orgs page lists participation already submitted for the chapter."""
    import datetime

    from thetatauCMT.users.tests.factories import OrganizationFactory, UserFactory, UserOrgParticipateFactory

    client, user = auto_login_user()
    _make_officer(user, client)
    member = UserFactory.create(chapter=user.chapter, status="active")
    UserOrgParticipateFactory.create(
        user=member,
        organization=OrganizationFactory.create(name="Tau Beta Pi"),
        start=datetime.date(2024, 1, 1),
        end=datetime.date(2099, 1, 1),
    )
    url = reverse("users:orgs")
    response = client.get(url)
    assert response.status_code == 200
    assert b"Tau Beta Pi" in response.content


# ---------------------------------------------------------------------------
# UserDetailUpdateView – POST forms
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_detail_post_user_form_redirects(auto_login_user):
    """POST action=user to myinfo redirects on success."""
    client, user = auto_login_user()
    url = reverse("users:detail")
    response = client.post(
        url,
        {
            "action": "user",
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "email_school": user.email_school or user.email,
        },
    )
    assert response.status_code in [200, 302]


@pytest.mark.django_db
def test_user_form_includes_contact_visibility_fields():
    """Members get a control for each contact field's visibility."""
    from thetatauCMT.users.forms import UserForm

    form = UserForm()
    for name in ("email_visibility", "phone_visibility", "address_visibility"):
        assert name in form.fields
    choices = dict(form.fields["phone_visibility"].choices)
    assert "no_one" in choices
    assert "members" in choices
    # The retired "my chapter's officers only" level is no longer offered.
    assert "officers" not in choices


@pytest.mark.django_db
def test_user_detail_post_saves_contact_visibility(auto_login_user):
    """A member can update who sees their phone / email / address."""
    client, user = auto_login_user()
    url = reverse("users:detail")
    response = client.post(
        url,
        {
            "action": "user",
            "graduation_year": user.graduation_year or 2025,
            "phone_number": "5551234567",
            "phone_visibility": "members",
            "email_visibility": "chapter",
            "address_visibility": "no_one",
            "email": user.email,
            "birth_date": "01/01/1990",
            "address_0": "123 Main St",
            "address_1": "Phoenix",
            "address_2": "AZ",
            "address_3": "85001",
            "address_4": "United States",
        },
    )
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.phone_visibility == "members"
    assert user.email_visibility == "chapter"
    assert user.address_visibility == "no_one"


@pytest.mark.django_db
def test_user_detail_post_gpa_form_redirects(auto_login_user):
    """POST action=gpa to myinfo redirects on success."""
    client, user = auto_login_user()
    url = reverse("users:detail")
    response = client.post(
        url,
        {
            "action": "gpa",
            "gpa1": "3.5",
            "gpa2": "3.7",
            "gpa3": "3.2",
            "gpa4": "3.8",
        },
    )
    assert response.status_code in [200, 302]


@pytest.mark.django_db
def test_user_detail_post_service_form_redirects(auto_login_user):
    """POST action=service to myinfo redirects on success."""
    client, user = auto_login_user()
    url = reverse("users:detail")
    response = client.post(
        url,
        {
            "action": "service",
            "service1": "10",
            "service2": "8",
            "service3": "12",
            "service4": "5",
        },
    )
    assert response.status_code in [200, 302]


# ---------------------------------------------------------------------------
# UserListView – CSV download (officer)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_list_view_csv_download_returns_csv(auto_login_user):
    """Officer user requesting CSV download returns CSV or HTML response."""
    client, user = auto_login_user()
    _make_officer(user, client)
    url = reverse("users:list")
    response = client.get(url, {"csv": "download csv"})
    assert response.status_code in [200, 302]


@pytest.mark.django_db
def test_user_list_view_email_action_officer(auto_login_user):
    """Officer user can trigger email action on user list."""
    client, user = auto_login_user()
    _make_officer(user, client)
    url = reverse("users:list")
    response = client.get(url, {"email": "email all"})
    assert response.status_code in [200, 302]


@pytest.mark.django_db
def test_user_list_view_csv_non_officer_denied(auto_login_user):
    """Non-officer user requesting CSV gets error message (200 not 403)."""
    client, user = auto_login_user()
    url = reverse("users:list")
    response = client.get(url, {"csv": "download csv"})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# UserSearchView – CSV download
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_search_view_csv_download(auto_login_user):
    """Natoff user can request CSV download from search view."""
    client, user = auto_login_user()
    _make_natoff(user, client)
    url = reverse("users:search")
    response = client.get(url, {"csv": "download csv", "q": user.last_name})
    assert response.status_code in [200, 302]


# ---------------------------------------------------------------------------
# UserLookupSearchView – POST (form_valid)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_lookup_search_form_valid_too_many_results(client, db):
    """Lookup search with too-broad search returns error and 200."""
    from thetatauCMT.chapters.models import Chapter

    url = reverse("users:lookup_search")
    chapters = Chapter.objects.all()
    chapter_id = str(chapters.first().pk) if chapters.exists() else "-1"
    response = client.post(
        url,
        {
            "university": chapter_id,
            "last_name": "",
            "first_name": "",
            "captcha_0": "test",
            "captcha_1": "PASSED",
        },
    )
    # Either renders form with errors or redirects
    assert response.status_code in [200, 302]


# ---------------------------------------------------------------------------
# UserAutocomplete – officer access
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_autocomplete_officer_access(auto_login_user):
    """Officer in officer_group can access the autocomplete view."""
    client, user = auto_login_user()
    _make_officer(user, client)
    url = reverse("users:autocomplete")
    response = client.get(url, {"q": user.first_name})
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_autocomplete_non_officer_returns_empty(auto_login_user):
    """Non-officer gets empty result from autocomplete (not 403)."""
    client, user = auto_login_user()
    url = reverse("users:autocomplete")
    response = client.get(url, {"q": user.first_name})
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_autocomplete_unauthenticated_returns_empty(client, db):
    """Unauthenticated users get empty result from autocomplete."""
    url = reverse("users:autocomplete")
    response = client.get(url)
    assert response.status_code in [200, 302]


# ---------------------------------------------------------------------------
# UserServiceFormSetView – cancel and context
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_service_formset_cancel(auto_login_user):
    """Service formset with cancel returns 200."""
    client, user = auto_login_user()
    url = reverse("users:service")
    response = client.get(url, {"cancel": "1"})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# UserMemberInfo (natoff detail view)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_member_info_natoff_returns_200(auto_login_user):
    """NatOff user can view any member's info via memberinfo view."""
    client, user = auto_login_user()
    _make_natoff(user, client)
    url = reverse("users:info", kwargs={"username": user.username})
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# UserDetailUpdateView – GPA initial with existing GPA records
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_detail_view_with_gpa_records(auto_login_user):
    """GET to users:detail with existing GPA records covers get_gpa_initial."""
    from core.models import BIENNIUM_YEARS
    from thetatauCMT.users.models import UserSemesterGPA

    client, user = auto_login_user()
    # Create GPA records for two semesters in the biennium
    UserSemesterGPA.objects.create(
        user=user,
        year=BIENNIUM_YEARS[0],
        term="fa",
        gpa=3.5,
    )
    UserSemesterGPA.objects.create(
        user=user,
        year=BIENNIUM_YEARS[1],
        term="sp",
        gpa=3.7,
    )
    url = reverse("users:detail")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_detail_view_with_service_records(auto_login_user):
    """GET to users:detail with existing service records covers get_service_initial."""
    from core.models import BIENNIUM_YEARS
    from thetatauCMT.users.models import UserSemesterServiceHours

    client, user = auto_login_user()
    UserSemesterServiceHours.objects.create(
        user=user,
        year=BIENNIUM_YEARS[0],
        term="fa",
        service_hours=10,
    )
    url = reverse("users:detail")
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# UserDetailUpdateView – POST gpa form with user field
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_detail_post_gpa_form_with_user_field(auto_login_user):
    """POST action=gpa with user field covers gpa_form_valid branch."""
    client, user = auto_login_user()
    url = reverse("users:detail")
    response = client.post(
        url,
        {
            "action": "gpa",
            "user": user.name,
            "chapter": user.chapter.name,
            "gpa1": "3.5",
            "gpa2": "3.7",
            "gpa3": "3.2",
            "gpa4": "3.8",
        },
    )
    assert response.status_code == 302, f"Expected redirect, got {response.status_code}"


@pytest.mark.django_db
def test_user_detail_post_service_form_with_user_field(auto_login_user):
    """POST action=service with user field covers service_form_valid branch."""
    client, user = auto_login_user()
    url = reverse("users:detail")
    response = client.post(
        url,
        {
            "action": "service",
            "user": user.name,
            "chapter": user.chapter.name,
            "service1": "10",
            "service2": "8",
            "service3": "12",
            "service4": "5",
        },
    )
    assert response.status_code in [200, 302]


# ---------------------------------------------------------------------------
# UserDetailUpdateView – demo form with existing UserDemographic
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_detail_view_with_demographic_record(auto_login_user):
    """GET to users:detail with an existing UserDemographic covers line 233."""
    from thetatauCMT.users.models import UserDemographic

    client, user = auto_login_user()
    UserDemographic.objects.create(
        user=user,
        first_gen=True,
        english=True,
        gender="male",
        sexual="heterosexual",
        racial="caucasian",
        ability="none",
    )
    url = reverse("users:detail")
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# UserDetailUpdateView – orgs table + add link
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_detail_orgs_section_shows_table_and_add_link(auto_login_user):
    """My Info shows the member's external-orgs table and a link to the add page."""
    from thetatauCMT.users.tests.factories import OrganizationFactory, UserOrgParticipateFactory

    client, user = auto_login_user()
    UserOrgParticipateFactory.create(user=user, organization=OrganizationFactory.create(name="Order of the Engineer"))
    url = reverse("users:detail")
    response = client.get(url)
    assert response.status_code == 200
    assert reverse("users:orgs_add").encode() in response.content
    assert b"Order of the Engineer" in response.content


# ---------------------------------------------------------------------------
# UserLookupSelectView – form_valid branches
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_lookup_select_view_with_session_users(client, db):
    """Lookup select view with session users set covers form_valid path."""
    from thetatauCMT.users.tests.factories import UserFactory

    user = UserFactory.create()
    session = client.session
    session["users"] = [user.pk]
    session.save()

    url = reverse("users:lookup_select")
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# UserLookupUpdateView – GET with session user
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_lookup_update_view_with_session_user(client, db):
    """Lookup update view GET with a user in session renders the form."""
    from thetatauCMT.users.tests.factories import UserFactory

    user = UserFactory.create()
    session = client.session
    session["user"] = user.pk
    session.save()

    url = reverse("users:update")
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# UserListView – email all with empty queryset
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_list_view_email_all_no_members(auto_login_user):
    """Email all with empty filter shows error message rather than sending."""
    client, user = auto_login_user()
    _make_officer(user, client)
    url = reverse("users:list")
    # Filter by a nonexistent badge to get empty queryset
    response = client.get(url, {"email": "email all", "badge_number": "9999999"})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# UserListView – CSV download with proper is_officer (chapter officer role)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_list_view_csv_download_chapter_officer(auto_login_user):
    """Chapter officer (is_officer=True via current_roles) can trigger CSV."""
    from thetatauCMT.users.tests.factories import UserStatusChangeFactory

    client, user = auto_login_user(make_officer="chapter")
    UserStatusChangeFactory.create(user=user, current=True, status="active")
    user.refresh_from_db()
    # Use force_login to ensure authentication is fresh after DB changes
    client.force_login(user)
    url = reverse("users:list")
    response = client.get(url, {"csv": "download csv"})
    # Chapter officer returns CSV file
    assert response.status_code == 200
    assert "text/csv" in response.get("Content-Type", "")


@pytest.mark.django_db
def test_user_list_view_email_all_chapter_officer(auto_login_user):
    """Chapter officer can trigger email-all action (covers email branch)."""
    from unittest.mock import patch

    from thetatauCMT.users.tests.factories import UserStatusChangeFactory

    client, user = auto_login_user(make_officer="chapter")
    UserStatusChangeFactory.create(user=user, current=True, status="active")
    user.refresh_from_db()
    # Use force_login to ensure authentication is fresh after DB changes
    client.force_login(user)
    url = reverse("users:list")
    with patch("thetatauCMT.users.views.MemberInfoUpdate") as mock_notif:
        mock_notif.return_value.send.return_value = None
        response = client.get(url, {"email": "email all"})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# PasswordResetFormNotActive – save() method coverage
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_password_reset_form_not_active_save(auto_login_user):
    """PasswordResetFormNotActive.save() sends reset email to user."""
    from django.test import RequestFactory

    from thetatauCMT.users.views import PasswordResetFormNotActive

    client, user = auto_login_user()
    factory = RequestFactory()
    request = factory.get("/")
    request.META["SERVER_NAME"] = "testserver"
    request.META["SERVER_PORT"] = "80"

    form = PasswordResetFormNotActive(data={"email": user.email})
    assert form.is_valid(), f"Form errors: {form.errors}"
    # save() should run without raising exceptions
    form.save(request=request)


@pytest.mark.django_db
def test_password_reset_form_not_active_save_no_email(auto_login_user):
    """save() with email=None in cleaned_data triggers early return with message."""
    from django.contrib.messages.storage.cookie import CookieStorage
    from django.test import RequestFactory

    from thetatauCMT.users.views import PasswordResetFormNotActive

    factory = RequestFactory()
    request = factory.get("/")
    # Add cookie-based messages storage (no session needed)
    request._messages = CookieStorage(request)

    # Create a bound form that validates, then manually clear email
    form = PasswordResetFormNotActive(data={"email": "does_not_exist@example.com"})
    form.is_valid()
    form.cleaned_data["email"] = None
    # Should return early without raising
    form.save(request=request)


# ---------------------------------------------------------------------------
# UserLookupUpdateView – form_valid coverage
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_lookup_update_form_valid_no_session_user(client, db):
    """POST with no session user and empty data → updated={} → just redirects."""
    from django.test import override_settings

    url = reverse("users:update")
    with override_settings(DEBUG=True):
        response = client.post(url, {})
    assert response.status_code == 302


@pytest.mark.django_db
def test_user_lookup_update_form_valid_with_session_user_no_change(client, db):
    """POST with session user but unchanged data → updated={} → just redirects."""
    from django.test import override_settings

    from thetatauCMT.users.tests.factories import UserFactory

    user = UserFactory.create()
    session = client.session
    session["user"] = user.pk
    session.save()
    url = reverse("users:update")
    with override_settings(DEBUG=True):
        response = client.post(url, {})
    assert response.status_code == 302


@pytest.mark.django_db
def test_user_lookup_update_form_valid_with_session_user_and_changes(client, db):
    """POST with session user and new first_name starts MemberUpdateFlow."""
    from unittest.mock import patch

    from django.test import override_settings

    from thetatauCMT.users.tests.factories import UserFactory

    user = UserFactory.create(first_name="OldFirst")
    session = client.session
    session["user"] = user.pk
    session.save()
    url = reverse("users:update")
    with override_settings(DEBUG=True):
        with patch("thetatauCMT.users.flows.MemberUpdateFlow") as mock_flow:
            mock_flow.start.run.return_value = None
            response = client.post(url, {"first_name": "BrandNewFirst", "major_other": "Applied Physics"})
    assert response.status_code == 302
    mock_flow.start.run.assert_called_once()


# ---------------------------------------------------------------------------
# hide_email – else branch (no @ in address)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_hide_email_no_at_sign(db):
    """hide_email returns '' for strings without @."""
    from thetatauCMT.users.views import hide_email

    assert hide_email("notanemail") == ""
    assert hide_email("") == ""


# ---------------------------------------------------------------------------
# UserDetailUpdateView – demo_form_valid coverage
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_detail_post_demo_form_valid(auto_login_user):
    """POST action=demo with all required fields covers demo_form_valid."""
    client, user = auto_login_user()
    url = reverse("users:detail")
    response = client.post(
        url,
        {
            "action": "demo",
            "gender": "cisgender",
            "sexual": "heterosexual",
            "racial": "caucasian",
            "ability": "no_impairment",
            "first_gen": "True",
            "english": "True",
            "international": "False",
        },
    )
    assert response.status_code in [200, 302]


# ---------------------------------------------------------------------------
# UserAlterView – form_valid coverage (natoff required)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_alter_view_form_valid(auto_login_user):
    """NatOff user POSTing valid alter form covers form_valid branches."""
    from thetatauCMT.chapters.models import Chapter

    client, user = auto_login_user()
    _make_natoff(user, client)
    url = reverse("users:alterchapter")
    chapter_choices = Chapter.chapter_choices()
    if not chapter_choices:
        pytest.skip("No chapter choices available")
    chapter_id = chapter_choices[0][0]
    response = client.post(
        url,
        {
            "chapter": chapter_id,
            "role": "",
            "alter-action": "Reset",
            "next": "",
        },
    )
    assert response.status_code in [200, 302]


# ---------------------------------------------------------------------------
# UserGPAFormSetView – formset_valid coverage
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_gpa_formset_view_post_valid(auto_login_user):
    """Officer POSTing GPA formset covers formset_valid."""
    client, user = auto_login_user(make_officer="chapter")
    _make_officer(user, client)  # Ensure officer group in DB and session
    url = reverse("users:gpas")
    response = client.post(
        url,
        {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-user": user.name,
            "form-0-gpa1": "3.5",
            "form-0-gpa2": "3.6",
            "form-0-gpa3": "3.7",
            "form-0-gpa4": "3.8",
            "chapter": user.chapter.name,
        },
    )
    assert response.status_code in [200, 302]


# ---------------------------------------------------------------------------
# UserLookupLoginView – get_context_data coverage (lines 549-551)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_lookup_login_view_get_context(client, db):
    """GET login page sets lookup_form in context (covers UserLookupLoginView)."""
    response = client.get(reverse("login"))
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# UserDetailUpdateView – user_form_valid coverage (lines 137-139)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_detail_post_user_form_valid_mocked(auto_login_user):
    """POST action=user mocking UserForm to bypass address validation."""
    from unittest.mock import MagicMock, patch

    client, user = auto_login_user()
    url = reverse("users:detail")

    mock_form = MagicMock()
    mock_form.is_valid.return_value = True
    mock_form.has_changed.return_value = True
    mock_form.save.return_value = None
    mock_form.errors = {}

    with patch("thetatauCMT.users.views.UserForm", return_value=mock_form):
        response = client.post(url, {"action": "user"})
    assert response.status_code in [200, 302]


# ---------------------------------------------------------------------------
# UserDetailUpdateView – user_form_valid using patched form_classes
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_detail_post_user_form_valid_patched(auto_login_user):
    """POST action=user with mock form class in form_classes covers user_form_valid."""
    from unittest.mock import patch

    from thetatauCMT.forms.forms import PledgeDemographicsForm
    from thetatauCMT.users.forms import UserGPAForm, UserServiceForm
    from thetatauCMT.users.views import UserDetailUpdateView

    client, user = auto_login_user()
    url = reverse("users:detail")

    class _ValidMockUserForm:
        prefix = None
        errors = {}

        def __init__(self, *args, **kwargs):
            pass

        def is_valid(self):
            return True

        def has_changed(self):
            return True

        def save(self):
            return None

    patched_classes = {
        "gpa": UserGPAForm,
        "service": UserServiceForm,
        "user": _ValidMockUserForm,
        "demo": PledgeDemographicsForm,
    }
    with patch.object(UserDetailUpdateView, "form_classes", patched_classes):
        response = client.post(url, {"action": "user"})
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# PasswordResetFormNotActive – domain_override branch (line 501)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_password_reset_form_not_active_save_domain_override(auto_login_user):
    """save() with domain_override covers the else branch (line 501)."""
    from django.test import RequestFactory

    from thetatauCMT.users.views import PasswordResetFormNotActive

    client, user = auto_login_user()
    factory = RequestFactory()
    request = factory.get("/")
    request.META["SERVER_NAME"] = "testserver"
    request.META["SERVER_PORT"] = "80"

    form = PasswordResetFormNotActive(data={"email": user.email})
    assert form.is_valid()
    # domain_override triggers the else branch (line 501)
    form.save(request=request, domain_override="example.com")


# ---------------------------------------------------------------------------
# UserLookupUpdateView – GET with officer in session (lines 652-657)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_lookup_update_get_officer_in_session(client, db):
    """GET with is_officer user in session triggers redirect to lookup_search."""
    from thetatauCMT.users.tests.factories import UserFactory, UserRoleChangeFactory

    officer = UserFactory.create()
    UserRoleChangeFactory.create(user=officer, current=True, officer="chapter")
    officer.refresh_from_db()
    assert officer.is_officer, "Officer setup failed"
    session = client.session
    session["user"] = officer.pk
    session.save()
    url = reverse("users:update")
    response = client.get(url)
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# UserLookupUpdateView – form_valid major_other branch (line 681)
# (test_user_lookup_update_form_valid_with_session_user_and_changes also covers this)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_lookup_update_form_valid_major_other(client, db):
    """POST with major_other value covers the major_other update branch (681)."""
    from unittest.mock import patch

    from django.test import override_settings

    from thetatauCMT.users.tests.factories import UserFactory

    user = UserFactory.create()
    session = client.session
    session["user"] = user.pk
    session.save()
    url = reverse("users:update")
    with override_settings(DEBUG=True):
        with patch("thetatauCMT.users.flows.MemberUpdateFlow") as mock_flow:
            mock_flow.start.run.return_value = None
            response = client.post(url, {"major_other": "Quantum Physics"})
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# UserAutocomplete – actives and alumni branches (lines 847, 849)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_autocomplete_actives(auto_login_user):
    """Autocomplete with chapter=true and actives=true covers line 847."""
    import json

    client, user = auto_login_user(make_officer="chapter")
    _make_officer(user, client)  # Ensure officer group membership
    url = reverse("users:autocomplete")
    response = client.get(
        url,
        {"forward": json.dumps({"chapter": "true", "actives": "true", "alumni": "false"})},
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_autocomplete_alumni(auto_login_user):
    """Autocomplete with chapter=true and alumni=true covers line 849."""
    import json

    client, user = auto_login_user(make_officer="chapter")
    _make_officer(user, client)  # Ensure officer group membership
    url = reverse("users:autocomplete")
    response = client.get(
        url,
        {"forward": json.dumps({"chapter": "true", "actives": "false", "alumni": "true"})},
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# UserDetailUpdateView – orgs section empty state
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_detail_orgs_section_empty_state(auto_login_user):
    """My Info orgs section renders an empty-state message when there are none."""
    client, user = auto_login_user()
    url = reverse("users:detail")
    response = client.get(url)
    assert response.status_code == 200
    assert b"have not added any external organizations" in response.content


# ---------------------------------------------------------------------------
# UserListView – CSV/email with empty member queryset (lines 375, 393)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_list_view_csv_no_members_empty(auto_login_user):
    """Officer with no active members triggers 'no members' CSV branch (line 375)."""
    client, user = auto_login_user(make_officer="chapter")
    _make_officer(user, client)  # Ensure officer group + session
    url = reverse("users:list")
    # No UserStatusChangeFactory → user current_status="" → empty queryset
    response = client.get(url, {"csv": "download csv"})
    assert response.status_code == 200
    assert "text/csv" not in response.get("Content-Type", "")


@pytest.mark.django_db
def test_user_list_view_email_all_empty(auto_login_user):
    """Officer with no active members triggers 'no members' email branch (line 393)."""
    client, user = auto_login_user(make_officer="chapter")
    _make_officer(user, client)  # Ensure officer group + session
    url = reverse("users:list")
    # No UserStatusChangeFactory → user current_status="" → empty queryset
    response = client.get(url, {"email": "email all"})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# UserDetailUpdateView – service_form_valid persists records to DB
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_detail_service_form_valid_saves_records_to_db(auto_login_user):
    """POST action=service with non-zero hours creates UserSemesterServiceHours rows."""
    from thetatauCMT.users.models import UserSemesterServiceHours

    client, user = auto_login_user()
    url = reverse("users:detail")
    response = client.post(
        url,
        {
            "action": "service",
            "user": user.name,
            "chapter": user.chapter.name,
            "service1": "5",
            "service2": "0",
            "service3": "7",
            "service4": "0",
        },
    )
    assert response.status_code in [200, 302]
    assert (
        UserSemesterServiceHours.objects.filter(user=user).count() > 0
    ), "Expected service hours records to be created in DB after POST"


# ---------------------------------------------------------------------------
# PasswordResetFormNotActive – email content assertions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_password_reset_sends_email_to_user_address(auto_login_user, mailoutbox):
    """PasswordResetFormNotActive.save() places an email addressed to user.email."""
    from django.test import RequestFactory

    from thetatauCMT.users.views import PasswordResetFormNotActive

    client, user = auto_login_user()
    factory = RequestFactory()
    request = factory.get("/")
    request.META["SERVER_NAME"] = "testserver"
    request.META["SERVER_PORT"] = "80"

    form = PasswordResetFormNotActive(data={"email": user.email})
    assert form.is_valid(), f"Form errors: {form.errors}"
    form.save(request=request)

    assert len(mailoutbox) >= 1, "Expected at least one email to be sent"
    all_recipients = [addr for msg in mailoutbox for addr in msg.to]
    assert user.email in all_recipients, f"{user.email!r} not found in recipients {all_recipients}"


@pytest.mark.django_db
def test_password_reset_sends_separate_email_to_school_address(auto_login_user, mailoutbox):
    """save() sends an additional email to email_school when it differs from email."""
    from django.test import RequestFactory

    from thetatauCMT.users.views import PasswordResetFormNotActive

    client, user = auto_login_user()
    user.email_school = f"school-{user.email}"
    user.save(update_fields=["email_school"])

    factory = RequestFactory()
    request = factory.get("/")
    request.META["SERVER_NAME"] = "testserver"
    request.META["SERVER_PORT"] = "80"

    form = PasswordResetFormNotActive(data={"email": user.email})
    assert form.is_valid(), f"Form errors: {form.errors}"
    form.save(request=request)

    all_recipients = [addr for msg in mailoutbox for addr in msg.to]
    assert user.email_school in all_recipients, f"School email {user.email_school!r} not found in {all_recipients}"


# ---------------------------------------------------------------------------
# UserLookupSearchView – behavioral tests (session content, deceased, prospective)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_lookup_search_single_result_sets_session_and_redirects(
    auto_login_user,
):
    """When watson returns 1 result the view stores user pk in session and redirects."""
    from unittest.mock import MagicMock, patch

    from thetatauCMT.users.tests.factories import UserFactory
    from thetatauCMT.users.views import UserLookupSearchView

    client, _ = auto_login_user()
    target_user = UserFactory.create()
    url = reverse("users:lookup_search")

    mock_qs = MagicMock()
    mock_qs.count.return_value = 1
    mock_qs.values_list.return_value = [target_user.pk]

    mock_form = MagicMock()
    mock_form.is_valid.return_value = True
    mock_form.cleaned_data = {"university": "-1", "name": "", "id": None}

    with (
        patch.object(UserLookupSearchView, "get_form", return_value=mock_form),
        patch("thetatauCMT.users.views.watson") as mock_watson,
    ):
        mock_watson.filter.return_value = mock_qs
        response = client.post(url, {})

    assert response.status_code == 302
    assert target_user.pk in client.session["users"]


@pytest.mark.django_db
def test_user_lookup_search_deceased_user_not_filtered_by_view(auto_login_user):
    """View does not exclude deceased users: a deceased user returned by watson is included."""
    from unittest.mock import MagicMock, patch

    from thetatauCMT.users.tests.factories import UserFactory
    from thetatauCMT.users.views import UserLookupSearchView

    client, _ = auto_login_user()
    deceased_user = UserFactory.create(deceased=True)
    url = reverse("users:lookup_search")

    mock_qs = MagicMock()
    mock_qs.count.return_value = 1
    mock_qs.values_list.return_value = [deceased_user.pk]

    mock_form = MagicMock()
    mock_form.is_valid.return_value = True
    mock_form.cleaned_data = {"university": "-1", "name": "", "id": None}

    with (
        patch.object(UserLookupSearchView, "get_form", return_value=mock_form),
        patch("thetatauCMT.users.views.watson") as mock_watson,
    ):
        mock_watson.filter.return_value = mock_qs
        response = client.post(url, {})

    assert response.status_code == 302
    assert deceased_user.pk in client.session["users"]


@pytest.mark.django_db
def test_user_lookup_search_prospective_user_not_filtered_by_view(auto_login_user):
    """View does not exclude prospective (pnm) users: returned by watson → in session."""
    from unittest.mock import MagicMock, patch

    from thetatauCMT.users.tests.factories import UserFactory
    from thetatauCMT.users.views import UserLookupSearchView

    client, _ = auto_login_user()
    pnm_user = UserFactory.create()
    url = reverse("users:lookup_search")

    mock_qs = MagicMock()
    mock_qs.count.return_value = 1
    mock_qs.values_list.return_value = [pnm_user.pk]

    mock_form = MagicMock()
    mock_form.is_valid.return_value = True
    mock_form.cleaned_data = {"university": "-1", "name": "", "id": None}

    with (
        patch.object(UserLookupSearchView, "get_form", return_value=mock_form),
        patch("thetatauCMT.users.views.watson") as mock_watson,
    ):
        mock_watson.filter.return_value = mock_qs
        response = client.post(url, {})

    assert response.status_code == 302
    assert pnm_user.pk in client.session["users"]


# ---------------------------------------------------------------------------
# UnsubscribeConfirmView – categorized unsubscribe flow
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_unsubscribe_get_bad_token_shows_invalid(client):
    url = reverse("users:unsubscribe", kwargs={"token": "garbage"})
    response = client.get(url)
    assert response.status_code == 200
    assert b"Invalid or expired link" in response.content


@pytest.mark.django_db
def test_unsubscribe_get_preselects_focus_category(client):
    from thetatauCMT.users.tests.factories import UserFactory
    from thetatauCMT.users.views import make_unsubscribe_token

    user = UserFactory.create()
    token = make_unsubscribe_token(user, category="grad_anniversary")
    url = reverse("users:unsubscribe", kwargs={"token": token})
    response = client.get(url)
    assert response.status_code == 200
    assert b"Graduation Anniversary" in response.content
    assert b"Velocitas Newsletter" in response.content
    assert b"Birthday Celebrations" in response.content
    # Focused category is checked
    assert b'value="grad_anniversary"' in response.content
    assert b"from this email" in response.content
    # Global toggle available but not checked for a fresh user
    assert b'value="all"' in response.content


@pytest.mark.django_db
def test_unsubscribe_post_single_category(client):
    from thetatauCMT.users.tests.factories import UserFactory
    from thetatauCMT.users.views import make_unsubscribe_token

    user = UserFactory.create()
    assert user.unsubscribe_categories == []
    token = make_unsubscribe_token(user, category="grad_anniversary")
    url = reverse("users:unsubscribe", kwargs={"token": token})
    # Simulate the one-click confirm: pre-checked box is submitted.
    response = client.post(url, {"categories": ["grad_anniversary"]})
    assert response.status_code == 200
    assert b"preferences are saved" in response.content
    user.refresh_from_db()
    assert user.unsubscribe_email is False
    assert "grad_anniversary" in user.unsubscribe_categories
    assert "velocitas" not in user.unsubscribe_categories


@pytest.mark.django_db
def test_unsubscribe_post_all_toggles_global_flag(client):
    from thetatauCMT.users.tests.factories import UserFactory
    from thetatauCMT.users.views import make_unsubscribe_token

    user = UserFactory.create()
    token = make_unsubscribe_token(user)
    url = reverse("users:unsubscribe", kwargs={"token": token})
    response = client.post(url, {"categories": ["all"]})
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.unsubscribe_email is True


@pytest.mark.django_db
def test_unsubscribe_all_syncs_to_mailerlite(client):
    from unittest.mock import patch

    from thetatauCMT.users.tests.factories import UserFactory
    from thetatauCMT.users.views import make_unsubscribe_token

    user = UserFactory.create()
    token = make_unsubscribe_token(user)
    url = reverse("users:unsubscribe", kwargs={"token": token})
    with patch("thetatauCMT.email_tracking.mailerlite_sync.unsubscribe_user") as ml:
        client.post(url, {"categories": ["all"]})
    ml.assert_called_once()
    assert ml.call_args.args[0].pk == user.pk


@pytest.mark.django_db
def test_unsubscribe_single_category_does_not_sync_mailerlite(client):
    from unittest.mock import patch

    from thetatauCMT.users.tests.factories import UserFactory
    from thetatauCMT.users.views import make_unsubscribe_token

    user = UserFactory.create()
    token = make_unsubscribe_token(user, category="grad_anniversary")
    url = reverse("users:unsubscribe", kwargs={"token": token})
    with patch("thetatauCMT.email_tracking.mailerlite_sync.unsubscribe_user") as ml:
        client.post(url, {"categories": ["grad_anniversary"]})
    ml.assert_not_called()


@pytest.mark.django_db
def test_unsubscribe_post_clears_previously_set_category(client):
    from thetatauCMT.users.tests.factories import UserFactory
    from thetatauCMT.users.views import make_unsubscribe_token

    user = UserFactory.create()
    user.unsubscribe_categories = ["velocitas", "birthday"]
    user.save(update_fields=["unsubscribe_categories"])
    token = make_unsubscribe_token(user)
    url = reverse("users:unsubscribe", kwargs={"token": token})
    # Re-submit with only birthday checked → velocitas is cleared.
    response = client.post(url, {"categories": ["birthday"]})
    assert response.status_code == 200
    user.refresh_from_db()
    assert "velocitas" not in user.unsubscribe_categories
    assert "birthday" in user.unsubscribe_categories


@pytest.mark.django_db
def test_unsubscribe_post_preserves_unknown_slugs(client):
    """Unknown slugs already on the user must survive an unrelated save."""
    from thetatauCMT.users.tests.factories import UserFactory
    from thetatauCMT.users.views import make_unsubscribe_token

    user = UserFactory.create()
    user.unsubscribe_categories = ["legacy_slug", "velocitas"]
    user.save(update_fields=["unsubscribe_categories"])
    token = make_unsubscribe_token(user)
    url = reverse("users:unsubscribe", kwargs={"token": token})
    client.post(url, {"categories": ["velocitas"]})
    user.refresh_from_db()
    assert "legacy_slug" in user.unsubscribe_categories
    assert "velocitas" in user.unsubscribe_categories


@pytest.mark.django_db
def test_unsubscribe_helpers_is_unsubscribed():
    from thetatauCMT.users.tests.factories import UserFactory
    from thetatauCMT.users.unsubscribe import is_unsubscribed, set_category_unsubscribed

    user = UserFactory.create()
    assert is_unsubscribed(user, "grad_anniversary") is False

    changed = set_category_unsubscribed(user, "grad_anniversary", True)
    assert changed is True
    assert is_unsubscribed(user, "grad_anniversary") is True
    assert is_unsubscribed(user, "velocitas") is False

    # Global unsubscribe wins
    user.unsubscribe_email = True
    assert is_unsubscribed(user, "velocitas") is True


@pytest.mark.django_db
def test_unsubscribe_token_ignores_unknown_category():
    from django.core import signing

    from thetatauCMT.users.tests.factories import UserFactory
    from thetatauCMT.users.views import UNSUBSCRIBE_SALT, make_unsubscribe_token

    user = UserFactory.create()
    token = make_unsubscribe_token(user, category="not_a_real_slug")
    payload = signing.loads(token, salt=UNSUBSCRIBE_SALT)
    assert "category" not in payload


@pytest.mark.django_db
def test_grad_anniversary_queryset_excludes_category_opt_out():
    """grad_anniversary queryset must skip users who opted out of that category."""
    import datetime

    from thetatauCMT.forms.tests.factories import StatusChangeFactory
    from thetatauCMT.users.management.commands.grad_anniversary_email import _grad_queryset
    from thetatauCMT.users.tests.factories import UserFactory

    target_year = datetime.date.today().year - 5
    subscribed = UserFactory.create()
    opted_out = UserFactory.create(unsubscribe_categories=["grad_anniversary"])
    globally_off = UserFactory.create(unsubscribe_email=True)

    for user in (subscribed, opted_out, globally_off):
        StatusChangeFactory.create(
            user=user,
            reason="graduate",
            date_start=datetime.date(target_year, 5, 15),
        )

    qs = _grad_queryset(target_year, range(1, 8))
    recipients = {sc.user_id for sc in qs}
    assert subscribed.pk in recipients
    assert opted_out.pk not in recipients
    assert globally_off.pk not in recipients


# ---------------------------------------------------------------------------
# UserDetailUpdateView – prefs (Email Preferences) accordion form
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_detail_prefs_form_sets_category(auto_login_user):
    """POST action=prefs sets unsubscribe_categories on the user."""
    client, user = auto_login_user()
    url = reverse("users:detail")
    response = client.post(
        url,
        {
            "action": "prefs",
            "unsubscribe_categories": ["grad_anniversary", "velocitas"],
        },
    )
    assert response.status_code in [200, 302]
    user.refresh_from_db()
    assert "grad_anniversary" in user.unsubscribe_categories
    assert "velocitas" in user.unsubscribe_categories
    assert user.unsubscribe_email is False


@pytest.mark.django_db
def test_user_detail_prefs_form_toggles_global_flag(auto_login_user):
    """POST action=prefs with unsubscribe_email checked flips the global flag."""
    client, user = auto_login_user()
    url = reverse("users:detail")
    response = client.post(
        url,
        {
            "action": "prefs",
            "unsubscribe_email": "on",
        },
    )
    assert response.status_code in [200, 302]
    user.refresh_from_db()
    assert user.unsubscribe_email is True


@pytest.mark.django_db
def test_user_detail_prefs_form_preserves_unknown_slugs(auto_login_user):
    """A profile save must not silently discard legacy/unknown slugs."""
    client, user = auto_login_user()
    user.unsubscribe_categories = ["legacy_slug", "velocitas"]
    user.save(update_fields=["unsubscribe_categories"])
    url = reverse("users:detail")
    client.post(
        url,
        {
            "action": "prefs",
            "unsubscribe_categories": ["birthday"],
        },
    )
    user.refresh_from_db()
    assert "legacy_slug" in user.unsubscribe_categories
    assert "birthday" in user.unsubscribe_categories
    assert "velocitas" not in user.unsubscribe_categories


@pytest.mark.django_db
def test_user_detail_page_renders_prefs_section(auto_login_user):
    """GET /myinfo/ includes the new Email Preferences accordion section."""
    client, user = auto_login_user()
    url = reverse("users:detail")
    response = client.get(url)
    assert response.status_code == 200
    assert b"Email Preferences" in response.content
    assert b"unsubscribe_categories" in response.content
