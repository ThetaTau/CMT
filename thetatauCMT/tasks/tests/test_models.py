import datetime
import pytest
from django.utils import timezone
from django.utils.text import slugify
from thetatauCMT.tasks.models import Task, TaskDate, TaskChapter


# ---------------------------------------------------------------------------
# Helper: create a Task + TaskDate matching a chapter's school_type
# ---------------------------------------------------------------------------

def _make_task_with_date(school_type="semester", days_offset=0):
    """Create a Task and a matching TaskDate; returns (task, task_date)."""
    task = Task(
        name=f"Test Task {school_type} {days_offset}",
        owner="regent",
        type="task",
        resource="",
        description="Created for test",
    )
    task.save()
    due_date = datetime.date.today() + datetime.timedelta(days=days_offset)
    task_date = TaskDate.objects.create(
        task=task,
        school_type=school_type,
        date=due_date,
    )
    return task, task_date

# ---------------------------------------------------------------------------
# Task.__str__ and save
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_task_str():
    task = Task.objects.first()
    assert str(task) == task.name


@pytest.mark.django_db
def test_task_save_sets_slug():
    """Task.save() sets slug = slugify(name + owner)."""
    task = Task(
        name="My Custom Task",
        owner="regent",
        type="task",
        resource="",
        description="A task for testing slug generation",
    )
    task.save()
    assert task.slug == slugify("My Custom Task" + "regent")


# ---------------------------------------------------------------------------
# Task.render_task_link
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_render_task_link_http_resource():
    """A task with an http resource produces an <a> link."""
    task = Task(
        name="External Link Task",
        owner="regent",
        type="form",
        resource="https://example.com/form",
        description="A task linking to an external site",
    )
    task.save()
    link = task.render_task_link
    assert "href" in str(link)
    assert "https://example.com/form" in str(link)


@pytest.mark.django_db
def test_render_task_link_empty_resource():
    """A task with no resource returns empty string."""
    task = Task(
        name="No Resource Task",
        owner="regent",
        type="task",
        resource="",
        description="A task with no link",
    )
    task.save()
    link = task.render_task_link
    assert link == ""


@pytest.mark.django_db
def test_render_task_link_url_resource():
    """A task with a URL-name resource (containing ':') produces an <a> link."""
    task = Task(
        name="URL Resource Task",
        owner="regent",
        type="form",
        resource="forms:rmp",
        description="A task with a named URL resource",
    )
    task.save()
    link = task.render_task_link
    assert "href" in str(link)


# ---------------------------------------------------------------------------
# Task.all_dates_for_task_chapter
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_all_dates_for_task_chapter_matches_school_type(chapter):
    """Only dates matching the chapter's school_type (or 'all') are returned."""
    task = Task.objects.first()
    dates = task.all_dates_for_task_chapter(chapter)
    # All returned dates should match chapter.school_type or be 'all'
    for td in dates:
        assert td.school_type in (chapter.school_type, "all")


# ---------------------------------------------------------------------------
# Task.incomplete_dates_for_task_chapter
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_incomplete_dates_for_task_chapter_excludes_completed(chapter, task_chapter_factory):
    """Dates that have already been completed by the chapter are excluded."""
    school_type = chapter.school_type
    task, task_date = _make_task_with_date(school_type=school_type, days_offset=10)
    # Create a TaskChapter completion record
    TaskChapter.objects.create(
        task=task_date,
        chapter=chapter,
        date=timezone.now().date(),
    )
    incomplete = task.incomplete_dates_for_task_chapter(chapter)
    completed_ids = {task_date.pk}
    for td in incomplete:
        assert td.pk not in completed_ids


# ---------------------------------------------------------------------------
# TaskDate.__str__
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_task_date_str(chapter):
    school_type = chapter.school_type
    task, task_date = _make_task_with_date(school_type=school_type)
    expected = f"{task.name} for {task.owner} due on {task_date.date}"
    assert str(task_date) == expected


# ---------------------------------------------------------------------------
# TaskDate.complete
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_task_date_complete_returns_empty_when_not_done(chapter):
    school_type = chapter.school_type
    _, task_date = _make_task_with_date(school_type=school_type)
    completions = task_date.complete(chapter)
    # No TaskChapter exists, so result should be empty
    assert completions.count() == 0


# ---------------------------------------------------------------------------
# TaskDate.incomplete_dates_for_chapter
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_incomplete_dates_for_chapter_returns_queryset(chapter):
    result = TaskDate.incomplete_dates_for_chapter(chapter)
    # Should be a queryset (may be empty), not None
    assert result is not None


@pytest.mark.django_db
def test_incomplete_dates_for_chapter_next_month_returns_queryset(chapter):
    result = TaskDate.incomplete_dates_for_chapter_next_month(chapter)
    assert result is not None


@pytest.mark.django_db
def test_dates_for_next_month_returns_queryset():
    result = TaskDate.dates_for_next_month()
    assert result is not None


# ---------------------------------------------------------------------------
# Task.completed_last
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_task_completed_last_returns_none_when_no_completions(chapter):
    task = Task.objects.first()
    result = task.completed_last(chapter)
    assert result is None


@pytest.mark.django_db
def test_task_completed_last_returns_submission_when_completed(chapter):
    """When a TaskChapter exists for the chapter, completed_last returns its submission_object."""
    school_type = chapter.school_type
    task, task_date = _make_task_with_date(school_type=school_type, days_offset=5)
    tc = TaskChapter.objects.create(
        task=task_date,
        chapter=chapter,
        date=datetime.date.today(),
    )
    # submission_object is None since we did not attach one
    result = task.completed_last(chapter)
    # completed_last returns tc.submission_object which is None
    assert result is None


# ---------------------------------------------------------------------------
# Task.mark_complete
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_mark_complete_unknown_name_returns_none(chapter):
    result = Task.mark_complete("Nonexistent Task Name XYZ", chapter)
    assert result is None


@pytest.mark.django_db
def test_mark_complete_creates_task_chapter(chapter):
    """mark_complete for a known task name without obj creates a TaskChapter."""
    school_type = chapter.school_type
    task, task_date = _make_task_with_date(school_type=school_type, days_offset=5)
    before = TaskChapter.objects.filter(task=task_date, chapter=chapter).count()
    Task.mark_complete(task.name, chapter)
    after = TaskChapter.objects.filter(task=task_date, chapter=chapter).count()
    assert after == before + 1


# ---------------------------------------------------------------------------
# TaskDate.incomplete_dates_for_chapter_past
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_incomplete_dates_for_chapter_past_returns_queryset(chapter):
    result = TaskDate.incomplete_dates_for_chapter_past(chapter)
    assert result is not None


# ---------------------------------------------------------------------------
# TaskDate.dates_for_chapter
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_dates_for_chapter_returns_queryset(chapter):
    result = TaskDate.dates_for_chapter(chapter)
    assert result is not None


# ---------------------------------------------------------------------------
# TaskChapter.check_previous
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_task_chapter_check_previous_returns_false_initially(chapter):
    school_type = chapter.school_type
    _, task_date = _make_task_with_date(school_type=school_type)
    assert TaskChapter.check_previous(task_date, chapter) is False


@pytest.mark.django_db
def test_task_chapter_check_previous_returns_true_after_creation(chapter):
    school_type = chapter.school_type
    _, task_date = _make_task_with_date(school_type=school_type)
    today = datetime.date.today()
    TaskChapter.objects.create(task=task_date, chapter=chapter, date=today)
    assert TaskChapter.check_previous(task_date, chapter, date=today) is True


# ---------------------------------------------------------------------------
# Task.render_task_link — submission_type path (line 55)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_render_task_link_with_submission_type():
    """A task with submission_type set produces a Submission link."""
    from thetatauCMT.scores.models import ScoreType

    score_type = ScoreType.objects.create(
        name="Test Sub Score",
        description="Score for task submission test",
        section="bro",
        points=10,
        term_points=5,
        formula="",
        slug="test-sub-score-tasks",
        type="Sub",
        base_points=0.0,
        attendance_multiplier=0.0,
        member_add=0.0,
        stem_add=0.0,
        alumni_add=0.0,
        guest_add=0.0,
        special="",
    )
    task = Task(
        name="Submission Type Task",
        owner="regent",
        type="sub",
        resource="",
        description="Task with submission type",
        submission_type=score_type,
    )
    task.save()
    link = task.render_task_link
    assert "Submission" in str(link)
    assert "href" in str(link)


# ---------------------------------------------------------------------------
# Task.render_task_link — ballot resource path (line 64)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_render_task_link_ballot_resource():
    """A task with 'ballot' in its resource uses the ballot reverse URL."""
    task = Task(
        name="Ballot Task",
        owner="regent",
        type="form",
        resource="ballots:vote",
        description="Task with ballot resource",
    )
    task.save()
    link = task.render_task_link
    assert "href" in str(link)
    assert "Ballot" in str(link)


# ---------------------------------------------------------------------------
# Task.mark_complete — with obj parameter (lines 113-154)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_mark_complete_with_obj_non_audit(chapter):
    """mark_complete with obj for a non-audit task sets submission_object on TaskChapter."""
    school_type = chapter.school_type
    task, task_date = _make_task_with_date(school_type=school_type, days_offset=5)
    # For non-audit/pledge/osm tasks, create_submission=False; obj is stored as-is
    # Use chapter as the obj (a valid model instance with pk)
    Task.mark_complete(task.name, chapter, obj=chapter)
    tc = TaskChapter.objects.filter(task=task_date, chapter=chapter).last()
    assert tc is not None


# ---------------------------------------------------------------------------
# Task.mark_complete — named task branches (Audit, Pledge Program, OSM)
# lines 128-153 in models.py
# ---------------------------------------------------------------------------

def _make_score_type(slug, name=None):
    """Create or get a ScoreType with the given slug for use in tests."""
    from thetatauCMT.scores.models import ScoreType

    score_type, _ = ScoreType.objects.get_or_create(
        slug=slug,
        defaults={
            "name": name or slug.replace("-", " ").title(),
            "description": f"{slug} score",
            "section": "bro",
            "points": 10,
            "term_points": 5,
            "formula": "",
            "type": "Sub",
            "base_points": 0.0,
            "attendance_multiplier": 0.0,
            "member_add": 0.0,
            "stem_add": 0.0,
            "alumni_add": 0.0,
            "guest_add": 0.0,
            "special": "",
        },
    )
    return score_type


@pytest.mark.django_db
def test_mark_complete_audit_branch_creates_task_chapter(chapter):
    """mark_complete('Audit', ...) takes the Audit branch and creates a TaskChapter."""
    _make_score_type("audit", name="Audit")

    # Use the existing fixture "Audit" task for regent (owner filter)
    # and attach a TaskDate that matches the chapter's school_type
    task = Task.objects.filter(name="Audit", owner="regent").first()
    assert task is not None, "Fixture must have an 'Audit' task for regent"
    due_date = datetime.date.today() + datetime.timedelta(days=5)
    task_date = TaskDate.objects.create(
        task=task, school_type=chapter.school_type, date=due_date
    )

    Task.mark_complete("Audit", chapter, current_roles=["regent"], user=None, obj=chapter)

    tc = TaskChapter.objects.filter(task=task_date, chapter=chapter).last()
    assert tc is not None
    # Verify the submission object is a Submission pointing to the audit form
    from thetatauCMT.submissions.models import Submission
    assert tc.submission_object is not None
    assert f"forms:audit_complete {chapter.pk}" in tc.submission_object.file.name


@pytest.mark.django_db
def test_mark_complete_pledge_program_branch_creates_task_chapter(chapter):
    """mark_complete('Pledge Program', ...) takes the Pledge Program branch."""
    from unittest.mock import MagicMock

    _make_score_type("pledge-program", name="Pledge Program")

    # Use (or create) a "Pledge Program" task
    task, _ = Task.objects.get_or_create(
        name="Pledge Program",
        owner="regent",
        defaults={"type": "task", "resource": "", "description": "Pledge Program task"},
    )
    due_date = datetime.date.today() + datetime.timedelta(days=5)
    task_date = TaskDate.objects.create(
        task=task, school_type=chapter.school_type, date=due_date
    )

    # obj needs a .manual attribute (simulates a PledgeProcess)
    mock_obj = MagicMock()
    mock_obj.pk = 9002
    mock_obj.manual = "not_other"

    Task.mark_complete("Pledge Program", chapter, current_roles=["regent"], user=None, obj=mock_obj)

    tc = TaskChapter.objects.filter(task=task_date, chapter=chapter).last()
    assert tc is not None
    from thetatauCMT.submissions.models import Submission
    assert tc.submission_object is not None
    assert tc.submission_object.file.name == "forms:pledge_program"


@pytest.mark.django_db
def test_mark_complete_osm_branch_creates_task_chapter(chapter):
    """mark_complete('Outstanding Student Member', ...) takes the OSM branch."""
    _make_score_type("osm", name="Outstanding Student Member")

    task, _ = Task.objects.get_or_create(
        name="Outstanding Student Member",
        owner="regent",
        defaults={"type": "task", "resource": "", "description": "OSM task"},
    )
    due_date = datetime.date.today() + datetime.timedelta(days=5)
    task_date = TaskDate.objects.create(
        task=task, school_type=chapter.school_type, date=due_date
    )

    Task.mark_complete(
        "Outstanding Student Member", chapter, current_roles=["regent"], user=None, obj=chapter
    )

    tc = TaskChapter.objects.filter(task=task_date, chapter=chapter).last()
    assert tc is not None
    from thetatauCMT.submissions.models import Submission
    assert tc.submission_object is not None
    assert tc.submission_object.file.name == "osmform"


