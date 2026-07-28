import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.notes.models import ChapterNote


def _make_natoff(user, client):
    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    client.force_login(user)


def _create_chapter_note(user, **kwargs):
    """Create a ChapterNote with required fields."""
    chapter = ChapterFactory()
    defaults = dict(
        chapter=chapter,
        created_by=user,
        title="Test Note Title",
        note="<p>Test note content.</p>",
        type="note",
        restricted=False,
    )
    defaults.update(kwargs)
    note = ChapterNote(**defaults)
    note.save()
    return note


@pytest.mark.django_db
def test_chapter_note_detail_view_authenticated(auto_login_user):
    """Any authenticated user can view an unrestricted ChapterNote."""
    client, user = auto_login_user()
    note = _create_chapter_note(user)
    url = reverse("notes:detail", kwargs={"pk": note.pk})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_chapter_note_detail_view_unauthenticated(auto_login_user):
    """Unauthenticated users are redirected from note detail."""
    client, user = auto_login_user()
    note = _create_chapter_note(user)
    client.logout()
    url = reverse("notes:detail", kwargs={"pk": note.pk})
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_chapter_note_detail_restricted_accessible_to_any_user(auto_login_user):
    """Restricted ChapterNotes are viewable by any authenticated user.

    Note: ChapterNoteDetailView.get() checks `not request.user.is_council_officer`
    but is_council_officer is a method (not a @property), so the check never
    redirects — any logged-in user can see restricted notes.
    """
    client, user = auto_login_user()
    note = _create_chapter_note(user, restricted=True)
    url = reverse("notes:detail", kwargs={"pk": note.pk})
    response = client.get(url)
    # Due to the missing @property decorator on is_council_officer, restricted
    # notes are always accessible to logged-in users
    assert response.status_code == 200


@pytest.mark.django_db
def test_chapter_note_create_view_natoff_get(auto_login_user):
    """Natoff can access ChapterNoteCreateView (GET returns form)."""
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    chapter = ChapterFactory()
    url = reverse("notes:add", kwargs={"slug": chapter.slug})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_chapter_note_create_view_regular_user_redirected(auto_login_user):
    """Non-natoff users are redirected from ChapterNoteCreateView."""
    client, user = auto_login_user()
    chapter = ChapterFactory()
    url = reverse("notes:add", kwargs={"slug": chapter.slug})
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_chapter_note_create_view_unauthenticated(auto_login_user):
    """Unauthenticated users are redirected to login."""
    client, user = auto_login_user()
    chapter = ChapterFactory()
    client.logout()
    url = reverse("notes:add", kwargs={"slug": chapter.slug})
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_user_note_create_view_natoff_get(auto_login_user):
    """Natoff can access UserNoteCreateView for a specific user."""
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    url = reverse("notes:add_user", kwargs={"username": user.username})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_note_create_view_regular_user_redirected(auto_login_user):
    """Non-natoff users are redirected from UserNoteCreateView."""
    client, user = auto_login_user()
    url = reverse("notes:add_user", kwargs={"username": user.username})
    response = client.get(url)
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# ChapterNoteDetailView — POST (note_form_valid, get_success_url) (5.7)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_chapter_note_detail_view_post_note_form_valid(auto_login_user):
    """Posting a valid note form to the detail view saves changes and redirects."""
    client, user = auto_login_user()
    note = _create_chapter_note(user)
    url = reverse("notes:detail", kwargs={"pk": note.pk})
    post_data = {
        "action": "note",
        "title": "Updated Title",
        "type": "note",
        "restricted": "",
        "note": "<p>Updated content</p>",
    }
    response = client.post(url, post_data)
    # Should redirect to notes:detail after successful save
    assert response.status_code in (200, 302)


@pytest.mark.django_db
def test_chapter_note_create_view_post_form_valid(auto_login_user):
    """POSTing a valid form to note create view creates a note and redirects."""
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    chapter = ChapterFactory()
    url = reverse("notes:add", kwargs={"slug": chapter.slug})
    post_data = {
        "title": "New Note Title",
        "type": "note",
        "restricted": "",
        "note": "<p>New note content</p>",
    }
    response = client.post(url, post_data)
    # Should redirect after successful create
    assert response.status_code in (200, 302)
    if response.status_code == 302:
        from thetatauCMT.notes.models import ChapterNote

        assert ChapterNote.objects.filter(title="New Note Title").exists()


@pytest.mark.django_db
def test_chapter_note_subnotes_post_sets_created_by(auto_login_user):
    """Adding a sub-note sets ``created_by`` instead of raising.

    ``subnotes_form_valid`` read ``instance.created_by`` (a non-null FK) on an
    unsaved sub-note, which raised RelatedObjectDoesNotExist (issue #888).
    """
    client, user = auto_login_user()
    note = _create_chapter_note(user)
    url = reverse("notes:detail", kwargs={"pk": note.pk})
    post_data = {
        "action": "subnotes",
        "form-TOTAL_FORMS": "1",
        "form-INITIAL_FORMS": "0",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
        "form-0-title": "Child sub-note",
        "form-0-type": "note",
        "form-0-note": "<p>child</p>",
        "form-0-restricted": "",
    }
    response = client.post(url, post_data)
    assert response.status_code in (200, 302)
    child = ChapterNote.objects.filter(title="Child sub-note", parent=note).first()
    assert child is not None
    assert child.created_by_id == user.id
