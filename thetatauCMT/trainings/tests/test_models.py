import pytest
from thetatauCMT.trainings.models import Training


@pytest.mark.django_db
def test_training_str(auto_login_user):
    """Training __str__ uses the default model repr (no custom __str__ defined)."""
    _, user = auto_login_user()
    training = Training(
        user=user,
        progress_id="prog-001",
        course_id="course-001",
        course_title="Introduction to Safety",
        completed=False,
        max_quiz_score=100.0,
    )
    training.save()
    assert training.course_title == "Introduction to Safety"
    assert str(training.pk) in str(training)


@pytest.mark.django_db
def test_training_completed_false_by_default(auto_login_user):
    _, user = auto_login_user()
    training = Training(
        user=user,
        progress_id="prog-002",
        course_id="course-002",
        course_title="Risk Management",
        max_quiz_score=80.0,
    )
    training.save()
    assert training.completed is False


@pytest.mark.django_db
def test_training_for_user(auto_login_user):
    """Trainings are associated with the correct user."""
    _, user = auto_login_user()
    training = Training.objects.create(
        user=user,
        progress_id="prog-003",
        course_id="course-003",
        course_title="Leadership Training",
        completed=True,
        max_quiz_score=95.0,
    )
    assert Training.objects.filter(user=user).count() == 1
    assert Training.objects.get(pk=training.pk).completed is True


@pytest.mark.django_db
def test_training_ordering(auto_login_user):
    """Trainings are ordered by -completed_time by default."""
    from django.utils import timezone
    _, user = auto_login_user()
    t1 = Training.objects.create(
        user=user, progress_id="p1", course_id="c1",
        course_title="Course A", completed=True,
        completed_time=timezone.now(), max_quiz_score=90.0,
    )
    t2 = Training.objects.create(
        user=user, progress_id="p2", course_id="c2",
        course_title="Course B", completed=True,
        completed_time=timezone.now(), max_quiz_score=85.0,
    )
    qs = list(Training.objects.filter(user=user))
    # Most recently completed should come first
    assert qs[0].pk == t2.pk
