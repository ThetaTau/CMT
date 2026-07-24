import datetime
import json

import pytest
from django.utils import timezone

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
    Training.objects.create(
        user=user,
        progress_id="p1",
        course_id="c1",
        course_title="Course A",
        completed=True,
        completed_time=timezone.now(),
        max_quiz_score=90.0,
    )
    t2 = Training.objects.create(
        user=user,
        progress_id="p2",
        course_id="c2",
        course_title="Course B",
        completed=True,
        completed_time=timezone.now(),
        max_quiz_score=85.0,
    )
    qs = list(Training.objects.filter(user=user))
    # Most recently completed should come first
    assert qs[0].pk == t2.pk


def test_interpret_enroll_result_actually_enrolled():
    """An ``after.enrollment`` state means the user is really enrolled."""
    results = [{"identifier": "a@b.com", "after": {"enrollment": True, "allowed": False}}]
    status, detail = Training._interpret_enroll_result(results)
    assert status == "enrolled"
    assert detail == "enrolled"


def test_interpret_enroll_result_pending_allowed():
    """``after.allowed`` (no enrollment) is a pending allowance, not enrolled.

    This is the case the old code silently reported as success, which is why
    people were "still not enrolled" until they logged in via SSO.
    """
    results = [{"identifier": "a@b.com", "after": {"enrollment": False, "allowed": True}}]
    status, detail = Training._interpret_enroll_result(results)
    assert status == "pending"
    assert "log" in detail.lower()


def test_interpret_enroll_result_invalid_identifier():
    results = [{"identifier": "bad", "invalidIdentifier": True}]
    status, _detail = Training._interpret_enroll_result(results)
    assert status == "error"


def test_interpret_enroll_result_error_flag():
    results = [{"identifier": "a@b.com", "error": True, "message": "boom"}]
    status, detail = Training._interpret_enroll_result(results)
    assert status == "error"
    assert detail == "boom"


def test_interpret_enroll_result_empty_is_pending():
    status, _detail = Training._interpret_enroll_result([])
    assert status == "pending"


class _FakeResponse:
    """Minimal stand-in for a requests Response used by enroll_user_ed."""

    def __init__(self, status_code=200, reason="OK", body=None):
        self.status_code = status_code
        self.reason = reason
        self._body = body or {}

    def json(self):
        return self._body


@pytest.mark.django_db
def test_enroll_user_ed_parses_per_course_outcomes(auto_login_user, settings, monkeypatch):
    """enroll_user_ed reports the real per-course outcome from the response body.

    The bulk-enroll endpoint always answers 200, so the body is what matters:
    course 1 is really enrolled, course 2 is only a pending SSO allowance.
    """
    course_1 = "course-v1:ThetaTau+TT101+intro"
    course_2 = "course-v1:ThetaTau+TT201+adv"
    settings.ED_COURSES = [course_1, course_2]
    _, user = auto_login_user()

    body = {
        "courses": {
            course_1: {"results": [{"after": {"enrollment": True, "allowed": False}}]},
            course_2: {"results": [{"after": {"enrollment": False, "allowed": True}}]},
        }
    }
    monkeypatch.setattr(
        "thetatauCMT.trainings.models.requests.post",
        lambda *a, **k: _FakeResponse(body=body),
    )

    results = Training.enroll_user_ed(user, header={"Authorization": "JWT x"})
    outcomes = {course_id: status for course_id, status, _msg in results}
    assert outcomes == {course_1: "enrolled", course_2: "pending"}


@pytest.mark.django_db
def test_enroll_user_ed_reports_not_global_staff_on_403(auto_login_user, settings, monkeypatch):
    """A 403 from bulk-enroll is surfaced as a clear 'not global staff' error."""
    settings.ED_COURSES = ["course-v1:ThetaTau+TT101+intro"]
    _, user = auto_login_user()
    monkeypatch.setattr(
        "thetatauCMT.trainings.models.requests.post",
        lambda *a, **k: _FakeResponse(status_code=403, reason="Forbidden"),
    )

    results = Training.enroll_user_ed(user, header={"Authorization": "JWT x"})
    assert [status for _c, status, _m in results] == ["error"]
    assert "global staff" in results[0][2]


def test_ed_normalize_strips_case_and_punctuation():
    """_ed_normalize reduces a value to lowercase alphanumerics only."""
    assert Training._ed_normalize("John Q. Smith-Jones") == "johnqsmithjones"
    assert Training._ed_normalize(None) == ""
    assert Training._ed_normalize("") == ""


@pytest.mark.django_db
def test_sync_ed_grade_matches_and_marks_completed(auto_login_user):
    """A passing grade upserts a completed Training row matched via the SSO name.

    Open edX stores the username as the CMT name (spaces stripped) and the
    grades API blanks the email, so matching is by the normalized name.
    """
    _, user = auto_login_user()
    course_id = "course-v1:ThetaTau+TT101+intro"
    index = Training._ed_user_index()
    grade = {"username": user.name, "email": "", "passed": True, "percent": 0.83}

    Training._sync_ed_grade(course_id, "Intro Course", grade, index)

    training = Training.objects.get(user=user, course_id=course_id)
    assert training.completed is True
    assert training.completed_time is not None
    assert training.max_quiz_score == 83.0
    assert training.course_title == "Intro Course"


@pytest.mark.django_db
def test_sync_ed_grade_not_passed_leaves_incomplete(auto_login_user):
    """A non-passing grade records the percent but stays incomplete."""
    _, user = auto_login_user()
    course_id = "course-v1:ThetaTau+TT101+intro"
    index = Training._ed_user_index()
    grade = {"username": user.name, "email": "", "passed": False, "percent": 0.1}

    Training._sync_ed_grade(course_id, "Intro Course", grade, index)

    training = Training.objects.get(user=user, course_id=course_id)
    assert training.completed is False
    assert training.completed_time is None
    assert training.max_quiz_score == 10.0


@pytest.mark.django_db
def test_sync_ed_grade_preserves_existing_completed_time(auto_login_user):
    """Re-syncing a passed course keeps the original completion timestamp."""
    _, user = auto_login_user()
    course_id = "course-v1:ThetaTau+TT101+intro"
    earlier = timezone.now() - datetime.timedelta(days=30)
    Training.objects.create(
        user=user,
        progress_id="",
        course_id=course_id,
        course_title="Intro Course",
        completed=True,
        completed_time=earlier,
        max_quiz_score=80.0,
    )
    index = Training._ed_user_index()
    grade = {"username": user.name, "email": "", "passed": True, "percent": 0.95}

    Training._sync_ed_grade(course_id, "Intro Course", grade, index)

    training = Training.objects.get(user=user, course_id=course_id)
    assert training.completed_time == earlier  # original timestamp preserved
    assert training.max_quiz_score == 95.0  # score refreshed


@pytest.mark.django_db
def test_sync_ed_grade_no_match_creates_nothing(auto_login_user):
    """An Open edX account with no matching CMT user is skipped, not created."""
    _, user = auto_login_user()
    course_id = "course-v1:ThetaTau+TT101+intro"
    index = Training._ed_user_index()
    grade = {"username": "NoSuchPersonExistsHere999", "email": "", "passed": True, "percent": 1.0}

    Training._sync_ed_grade(course_id, "Intro Course", grade, index)

    assert Training.objects.filter(course_id=course_id).count() == 0


@pytest.mark.django_db
def test_get_progress_all_users_ed_pages_and_upserts(auto_login_user, settings, monkeypatch):
    """get_progress_all_users_ed follows pagination, fetches the title, upserts."""
    _, user = auto_login_user()
    course_id = "course-v1:ThetaTau+TT101+intro"
    settings.ED_HOST = "https://ed.example.org"
    settings.ED_COURSES = [course_id]

    page2 = f"https://ed.example.org/api/grades/v1/courses/{course_id}/?cursor=page2"
    grade1 = {"username": user.name, "email": "", "passed": True, "percent": 0.9}
    grade2 = {"username": "NobodyMatchesThis999", "email": "", "passed": True, "percent": 0.5}

    def fake_get(url, headers=None, **kwargs):
        if "/api/courses/v1/courses/" in url:
            return _FakeResponse(body={"name": "Paged Intro"})
        if "cursor=page2" in url:
            return _FakeResponse(body={"results": [grade2], "next": None})
        return _FakeResponse(body={"results": [grade1], "next": page2})

    monkeypatch.setattr("thetatauCMT.trainings.models.requests.get", fake_get)

    Training.get_progress_all_users_ed(header={"Authorization": "JWT x"})

    training = Training.objects.get(user=user, course_id=course_id)
    assert training.completed is True
    assert training.max_quiz_score == 90.0
    assert training.course_title == "Paged Intro"
    # grade2 matched no CMT user, so only the one row exists.
    assert Training.objects.filter(course_id=course_id).count() == 1


@pytest.mark.django_db
def test_add_user_survives_non_json_addjob_response(auto_login_user, monkeypatch):
    """A non-JSON ``addJob`` response must not turn officer sync into a 500 (issue #1086).

    The Vector LMS ``addJob`` endpoint intermittently answers with an empty body or an
    HTML gateway error, so ``response.json()`` raises ``JSONDecodeError`` (a
    ``ValueError``). ``add_user`` must treat that as a soft failure instead of letting
    it propagate out of the officer-update POST.
    """
    _, user = auto_login_user()

    monkeypatch.setattr(Training, "authenticate_header", staticmethod(lambda: {"Authorization": "x"}))
    monkeypatch.setattr(
        Training,
        "get_location_position_ids",
        staticmethod(lambda *args, **kwargs: ("loc-1", "pos-1")),
    )

    class _AddPersonResponse:
        status_code = 200

        def json(self):
            return {"data": {"addPerson": {"personId": "PID-1"}}}

    class _BadJsonResponse:
        status_code = 200

        def json(self):
            raise json.JSONDecodeError("Expecting value", "", 0)

    def fake_post(*args, **kwargs):
        query = (kwargs.get("json") or {}).get("query", "")
        if "addJob" in query:
            return _BadJsonResponse()
        return _AddPersonResponse()

    monkeypatch.setattr("thetatauCMT.trainings.models.requests.post", fake_post)

    # Must not raise even though the addJob response body is not valid JSON.
    response = Training.add_user(user, extra_group="risk management chair")
    assert response.status_code == 200


def test_get_location_position_ids_missing_location_returns_none(monkeypatch):
    """An unknown location yields ``location_id=None`` instead of ``IndexError`` (issue #1085).

    ``add_user`` relies on a ``None`` location id to trigger its ``addLocation``
    fallback; previously an empty ``Locations`` ``nodes`` list raised ``IndexError``
    and turned the officer-update POST into a 500.
    """
    monkeypatch.setattr(Training, "authenticate_header", staticmethod(lambda: {"Authorization": "x"}))

    class _Resp:
        status_code = 200

        def __init__(self, body):
            self._body = body

        def json(self):
            return self._body

    def fake_post(*args, **kwargs):
        query = (kwargs.get("json") or {}).get("query", "")
        if "Locations" in query:
            return _Resp({"data": {"Locations": {"nodes": []}}})
        return _Resp({"data": {"Positions": {"nodes": [{"positionId": "pos-1"}]}}})

    monkeypatch.setattr("thetatauCMT.trainings.models.requests.post", fake_post)

    location_id, position_id = Training.get_location_position_ids("active", "Nonexistent Chapter")
    assert location_id is None
    assert position_id == "pos-1"
