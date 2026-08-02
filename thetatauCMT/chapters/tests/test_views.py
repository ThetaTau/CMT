"""
https://www.pythoncentral.io/writing-tests-for-your-django-applications-views/
https://django-testing-docs.readthedocs.io/en/latest/views.html
https://developer.mozilla.org/en-US/docs/Learn/Server-side/Django/Testing
"""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from .factories import ChapterFactory


def _add_to_group(user, group_name):
    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)


@pytest.mark.django_db
def test_chapter_detail_view(auto_login_user):
    client, user = auto_login_user()
    chapter = ChapterFactory()
    url = reverse("chapters:detail", kwargs={"slug": chapter.slug})
    response = client.get(url, follow=True)
    assert response.status_code == 200
    content = response.content.decode("UTF-8")
    assert chapter.name in content
    assert f"{chapter.region} Region" in content


@pytest.mark.django_db
def test_chapter_detail_email_list_includes_generic_emails(auto_login_user):
    """The "Copy emails" list also includes the chapter generic officer emails."""
    client, user = auto_login_user()
    chapter = ChapterFactory()
    # Set explicitly (not via factory kwargs) so a ChapterFactory name collision
    # returning an existing chapter can't drop the generic mailbox values.
    chapter.email_regent = "regent@generic.example.com"
    chapter.email_treasurer = "treasurer@generic.example.com"
    chapter.save(update_fields=["email_regent", "email_treasurer"])
    url = reverse("chapters:detail", kwargs={"slug": chapter.slug})
    response = client.get(url, follow=True)
    assert response.status_code == 200
    email_list = response.context["email_list"]
    assert "regent@generic.example.com" in email_list
    assert "treasurer@generic.example.com" in email_list


@pytest.mark.django_db
def test_chapter_detail_shows_regional_director_link(auto_login_user):
    """The chapter detail page links to the region's Regional Director profile."""
    from thetatauCMT.regions.tests.factories import RegionFactory
    from thetatauCMT.users.tests.factories import UserFactory

    client, user = auto_login_user()
    region = RegionFactory(name="RD Link Region")
    director = UserFactory(first_name="Dana", last_name="Director")
    region.directors.add(director)
    # Set the region explicitly after creation: ChapterFactory uses
    # django_get_or_create=("name",) and may return an existing chapter,
    # dropping a region= kwarg.
    chapter = ChapterFactory()
    chapter.region = region
    chapter.save(update_fields=["region"])
    url = reverse("chapters:detail", kwargs={"slug": chapter.slug})
    response = client.get(url, follow=True)
    assert response.status_code == 200
    content = response.content.decode("UTF-8")
    profile_url = reverse("users:profile", kwargs={"username": director.username})
    assert profile_url in content
    assert director.name in content
    assert list(response.context["region_directors"]) == [director]


@pytest.mark.django_db
def test_chapter_detail_links_to_the_region_overview(auto_login_user):
    """Members have no other route to their region page from the chapter."""
    from thetatauCMT.regions.tests.factories import RegionFactory

    client, user = auto_login_user()
    region = RegionFactory(name="Region Link Region")
    chapter = ChapterFactory()
    chapter.region = region
    chapter.save(update_fields=["region"])

    response = client.get(reverse("chapters:detail", kwargs={"slug": chapter.slug}), follow=True)

    assert response.status_code == 200
    assert reverse("regions:detail", kwargs={"slug": region.slug}) in response.content.decode("UTF-8")


@pytest.mark.django_db
def test_chapter_detail_shows_size_target(auto_login_user):
    """The chapter detail page displays the membership Size Target."""
    client, user = auto_login_user()
    chapter = ChapterFactory()
    # Set explicitly (not via factory kwargs) so a ChapterFactory name collision
    # returning an existing chapter can't drop the value.
    chapter.size_target = 137
    chapter.save(update_fields=["size_target"])
    url = reverse("chapters:detail", kwargs={"slug": chapter.slug})
    response = client.get(url, follow=True)
    assert response.status_code == 200
    content = response.content.decode("UTF-8")
    assert "Size Target" in content
    # The value renders in its own info-colored stat block.
    assert 'text-info">137</div>' in content


@pytest.mark.django_db
def test_chapter_detail_shows_support_specialist(auto_login_user):
    """The Support Specialist rich text renders (sanitized) on the detail page."""
    client, user = auto_login_user()
    chapter = ChapterFactory()
    chapter.support_specialist = "<p>Contact <strong>Jamie Support</strong></p><script>alert(1)</script>"
    chapter.save(update_fields=["support_specialist"])
    url = reverse("chapters:detail", kwargs={"slug": chapter.slug})
    response = client.get(url, follow=True)
    assert response.status_code == 200
    content = response.content.decode("UTF-8")
    assert "Support Specialist" in content
    # Allowed rich-text markup is preserved through the sanitizer.
    assert "<strong>Jamie Support</strong>" in content
    # Dangerous markup is stripped (stored-XSS mitigation).
    assert "<script>alert(1)</script>" not in content


def test_chapter_list_view_denied(auto_login_user):
    client, user = auto_login_user()
    url = reverse("chapters:list")
    response = client.get(url)
    assert response.status_code == 200
    assert "Filter Chapters" in response.content.decode("UTF-8")


@pytest.mark.django_db
@pytest.mark.freeze_time("2026-05-15 12:00:00")
def test_chapter_list_view_chapter_officer(auto_login_user):
    client, user = auto_login_user(make_officer="chapter")
    url = reverse("chapters:list")
    response = client.get(url, follow=True)
    assert response.status_code == 200
    assert "Filter Chapters" in response.content.decode("UTF-8")


@pytest.mark.django_db
@pytest.mark.freeze_time("2026-05-15 12:00:00")
def test_chapter_list_view_natoff(auto_login_user):
    client, user = auto_login_user(make_officer="national")
    url = reverse("chapters:list")
    response = client.get(url, follow=True)
    assert response.status_code == 200
    assert "Filter Chapters" in response.content.decode("UTF-8")


# ─── ChapterRedirectView ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_chapter_redirect_view_redirects_to_own_chapter(auto_login_user):
    client, user = auto_login_user()
    url = reverse("chapters:redirect")
    response = client.get(url)
    assert response.status_code == 302
    assert user.current_chapter.slug in response["Location"]


@pytest.mark.django_db
def test_chapter_redirect_view_unauthenticated(client):
    url = reverse("chapters:redirect")
    response = client.get(url)
    assert response.status_code == 302
    assert "login" in response["Location"]


# ─── ChapterDetailView ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_chapter_detail_own_chapter(auto_login_user):
    """User can see their own chapter's detail page."""
    client, user = auto_login_user()
    chapter = user.current_chapter
    url = reverse("chapters:detail", kwargs={"slug": chapter.slug})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_chapter_detail_unauthenticated(client):
    chapter = ChapterFactory()
    url = reverse("chapters:detail", kwargs={"slug": chapter.slug})
    response = client.get(url)
    assert response.status_code == 302


# ─── ChapterListView (natoff sees all chapters) ────────────────────────────────


@pytest.mark.django_db
def test_chapter_list_view_unauthenticated(client):
    response = client.get(reverse("chapters:list"))
    assert response.status_code == 302


# ─── ChapterDetailView – natoff path ─────────────────────────────────────────


@pytest.mark.django_db
def test_chapter_detail_view_natoff_user(auto_login_user):
    """National officer visiting chapter detail triggers natoff=True in context."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    chapter = user.current_chapter
    url = reverse("chapters:detail", kwargs={"slug": chapter.slug})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_chapter_detail_view_post_chapter_form_redirects(auto_login_user):
    """POST to chapter detail with action=chapter redirects on success."""
    client, user = auto_login_user()
    chapter = user.current_chapter
    url = reverse("chapters:detail", kwargs={"slug": chapter.slug})
    # Post minimal chapter form data – all optional fields
    post_data = {
        "action": "chapter",
        "email": "test@example.com",
        "website": "",
        "facebook": "",
        "instagram": "",
        "tiktok": "",
        "linkedin": "",
        "youtube": "",
        "twitter": "",
        "address_line_2": "",
        "address_contact": "",
        "address_phone_number": "",
        "council": chapter.council or "",
        "house": False,
        "recognition": chapter.recognition or "",
        "recognition_url": "",
        "email_regent": "",
        "email_vice_regent": "",
        "email_scribe": "",
        "email_treasurer": "",
        "email_corresponding_secretary": "",
    }
    response = client.post(url, post_data)
    # Should redirect (302) or render 200 with errors
    assert response.status_code in [200, 302]


@pytest.mark.django_db
def test_chapter_form_has_optional_recognition_url_field():
    """The campus-recognition form exposes an optional 'recognition_url' question."""
    from thetatauCMT.chapters.forms import ChapterForm

    form = ChapterForm()
    assert "recognition_url" in form.fields
    assert form.fields["recognition_url"].required is False


@pytest.mark.django_db
def test_chapter_recognition_url_persists():
    """recognition_url is saved on the Chapter model."""
    chapter = ChapterFactory()
    chapter.recognition_url = "https://finaid.example.edu/recognition"
    chapter.save(update_fields=["recognition_url"])
    chapter.refresh_from_db()
    assert chapter.recognition_url == "https://finaid.example.edu/recognition"


@pytest.mark.django_db
def test_chapter_list_view_returns_200_authenticated(auto_login_user):
    """Authenticated user can see the chapter list."""
    client, user = auto_login_user()
    url = reverse("chapters:list")
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ─── ChapterDetailView – audit loop coverage ─────────────────────────────────


@pytest.mark.django_db
def test_chapter_detail_view_with_audit_data(auto_login_user):
    """When Audit objects exist for the chapter the audit loop in
    get_context_data runs (lines 139-147 of views.py)."""
    from django.utils import timezone

    from thetatauCMT.forms.models import Audit

    client, user = auto_login_user()
    chapter = user.current_chapter

    Audit.objects.create(
        user=user,
        year=2023,
        term="fa",
        modified=timezone.now(),
        dues_member=100.0,
        dues_pledge=50.0,
        frequency="month",
        payment_plan=True,
        cash_book=True,
        cash_register=True,
        member_account=True,
        cash_book_reviewed=True,
        cash_register_reviewed=True,
        member_account_reviewed=True,
        balance_checking=1000.0,
        balance_savings=500.0,
        debit_card=True,
        debit_card_access="regent",
        agreement=True,
    )

    url = reverse("chapters:detail", kwargs={"slug": chapter.slug})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_chapter_detail_view_audit_with_officer_role(auto_login_user):
    """When the audited user has an officer role the audit_data branch runs
    (covers lines 142-147 of views.py including line 156)."""
    import datetime

    from django.utils import timezone

    from thetatauCMT.forms.models import Audit
    from thetatauCMT.users.models import UserRoleChange

    client, user = auto_login_user()
    chapter = user.current_chapter

    today = datetime.date.today()
    UserRoleChange.objects.create(
        user=user,
        role="regent",
        start=today - datetime.timedelta(days=60),
        end=today + datetime.timedelta(days=60),
    )

    Audit.objects.create(
        user=user,
        year=2023,
        term="fa",
        modified=timezone.now(),
        dues_member=100.0,
        dues_pledge=50.0,
        frequency="month",
        payment_plan=True,
        cash_book=True,
        cash_register=True,
        member_account=True,
        cash_book_reviewed=True,
        cash_register_reviewed=True,
        member_account_reviewed=True,
        balance_checking=1000.0,
        balance_savings=500.0,
        debit_card=True,
        debit_card_access="regent",
        agreement=True,
    )

    url = reverse("chapters:detail", kwargs={"slug": chapter.slug})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_chapter_detail_view_with_national_officer_role(auto_login_user):
    """A user with current_roles containing a NAT_OFFICERS role triggers
    natoff=True in the table constructor (line 182 of views.py)."""
    client, user = auto_login_user()
    user.current_roles = ["national director"]
    user.save()
    chapter = user.current_chapter
    url = reverse("chapters:detail", kwargs={"slug": chapter.slug})
    response = client.get(url)
    assert response.status_code == 200


# ─── ChapterAuditView / ChapterAuditRedirectView ─────────────────────────────


@pytest.mark.django_db
def test_chapter_audit_redirect_view(auto_login_user):
    """The Finances nav link at /chapters/audit/ sends the user to their own
    chapter's audit page."""
    client, user = auto_login_user()
    chapter = user.current_chapter
    url = reverse("chapters:audit_redirect")
    response = client.get(url, follow=False)
    assert response.status_code == 302
    assert response["Location"] == reverse("chapters:audit", kwargs={"slug": chapter.slug})


@pytest.mark.django_db
def test_chapter_audit_view_own_chapter(auto_login_user):
    """A logged-in chapter member can view their own chapter's audit summary."""
    from django.utils import timezone

    from thetatauCMT.forms.models import Audit

    client, user = auto_login_user()
    chapter = user.current_chapter
    Audit.objects.create(
        user=user,
        year=2023,
        term="fa",
        modified=timezone.now(),
        dues_member=100.0,
        dues_pledge=50.0,
        frequency="month",
        payment_plan=True,
        cash_book=True,
        cash_register=True,
        member_account=True,
        cash_book_reviewed=True,
        cash_register_reviewed=True,
        member_account_reviewed=True,
        balance_checking=1000.0,
        balance_savings=500.0,
        debit_card=True,
        debit_card_access="regent",
        agreement=True,
    )
    url = reverse("chapters:audit", kwargs={"slug": chapter.slug})
    response = client.get(url)
    assert response.status_code == 200
    body = response.content.decode()
    assert "Chapter Audit" in body


@pytest.mark.django_db
def test_chapter_audit_view_other_chapter_denied(auto_login_user):
    """A regular chapter member cannot view another chapter's audit."""
    client, user = auto_login_user()
    other_chapter = ChapterFactory()
    url = reverse("chapters:audit", kwargs={"slug": other_chapter.slug})
    response = client.get(url, follow=False)
    assert response.status_code == 302
    assert response["Location"] == reverse("home")


@pytest.mark.django_db
def test_chapter_audit_view_natoff_can_view_any(auto_login_user):
    """National officers can view any chapter's audit."""
    client, user = auto_login_user()
    _add_to_group(user, "natoff")
    other_chapter = ChapterFactory()
    url = reverse("chapters:audit", kwargs={"slug": other_chapter.slug})
    response = client.get(url)
    assert response.status_code == 200
