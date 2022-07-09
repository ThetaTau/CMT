import json
import datetime
import requests
from django.conf import settings
from django.db import models
from core.models import TimeStampedModel
from users.models import User


class Training(TimeStampedModel):
    class Meta:
        ordering = [
            "-completed_time",
        ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="trainings")
    progress_id = models.CharField(max_length=100)
    course_id = models.CharField(max_length=100)
    course_title = models.CharField(max_length=50)
    completed = models.BooleanField(default=False)
    completed_time = models.DateTimeField(blank=True, null=True)
    max_quiz_score = models.FloatField()

    @staticmethod
    def authenticate_header():
        auth_file = settings.ROOT_DIR / "secrets" / "LMS_API_KEY"
        refresh = True
        if auth_file.exists():
            with open(auth_file) as file_obj:
                response_json = json.load(file_obj)
            expires_in = response_json["expires_in"]
            created_at = response_json["created_at"]
            created_at = datetime.datetime.fromtimestamp(created_at)
            expires_in = datetime.timedelta(seconds=expires_in)
            if (created_at + expires_in) > datetime.datetime.now():
                refresh = False
        if refresh:
            url = "https://api.fifoundry.net/oauth/token"
            params = dict(
                grant_type="client_credentials",
                client_id=settings.LMS_ID,
                client_secret=settings.LMS_SECRET,
            )
            headers = {"Accept": "application/json", "Content-Type": "application/json"}
            response = requests.post(url, params=params, headers=headers)
            if response.status_code == 200:
                response_json = response.json()
                with open(auth_file, "w") as file_obj:
                    json.dump(response_json, file_obj)
            else:
                # There was an error
                raise ValueError(f"LMS Auth error: {response.reason}")
        authenticate_header = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"{response_json['token_type']} {response_json['access_token']}",
        }
        return authenticate_header

    @staticmethod
    def get_progress_all_users(since=None, scroll_id=None):
        authenticate_header = Training.authenticate_header()
        lms_since_file = settings.ROOT_DIR / "secrets" / "LMS_SINCE"
        if since is None:
            if lms_since_file.exists():
                with open(lms_since_file) as file_obj:
                    response_json = json.load(file_obj)
                since = response_json["since"]
            else:
                since = datetime.datetime.now() - datetime.timedelta(days=7)
                since = since.isoformat()
        url = "https://api.fifoundry.net/v1/progress/user_assignments"

        params = dict(since=since, scroll_size=100)
        if scroll_id is not None:
            params["scroll_id"] = scroll_id
        response = requests.get(url, headers=authenticate_header, params=params)
        if response.status_code == 204:
            print(f"There were no updated trainings {response.reason}")
            return
        response_json = response.json()
        next = response_json["next"]
        data = response_json["data"]
        for user_info in data:
            """{
            "id": "dc335f10-1d5f-4b20-bfc0-94fc6336b0a7",
            "email": "somebody@everfi.com",
            "active": True,
            "sso_id": "somebody@everfi.com",
            "deleted": False,
            "location": {"name": "Felderwin"},
            "groupings": [],
            "last_name": "Jones",
            "first_name": "Geoff",
            "student_id": "876565",
            "employee_id": "341325",
            }"""
            user_email = user_info["user"]["email"]
            user = User.objects.get(email=user_email)
            for progress in data["progress"]:
                """example progress object
                {
                    "id": "b5e90d5e-49eb-4cd3-b6b3-4d338ab01362",
                    "name": "Diversity: Inclusion in the Modern Workplace (EDU)",
                    "due_on": "2020-05-10",
                    "content_id": "4f2cb36a-07bd-4fe9-b406-230da89111d3",
                    "started_at": None,
                    "completed_at": None,
                    "content_status": "not_started",
                    "last_progress_at": None,
                    "percent_completed": 0,
                }"""
                course_id = progress["content_id"]
                completed = progress["content_status"] == "completed"
                completed_at = progress["completed_at"]
                completed_at = (
                    datetime.datetime.fromisoformat(completed_at)
                    if completed_at
                    else None
                )
                values = dict(
                    user=user,
                    progress_id=progress["id"],
                    course_id=course_id,
                    course_title=progress["name"],
                    completed=completed,
                    completed_time=completed_at,
                    max_quiz_score=progress["percent_completed"],
                )
                obj, created = Training.objects.update_or_create(
                    user=user, course_id=course_id, defaults=values
                )
        scroll_id = next["scroll_id"]
        if not scroll_id:
            """{
            "since": "2020-05-22T19:27:42.908191Z",
            "scroll_id": None,
            "scroll_size": 1000,
            "filter": {},
            "href": "https://api.fifoundry.net/v1/progress/user_assignments?scroll_size=1000&since=2020-05-22T19"
            "%3A27%3A42.908191Z",
            }"""
            with open(lms_since_file, "w") as file_obj:
                json.dump(next, file_obj)
        else:
            Training.get_progress_all_users(since=next["since"], scroll_id=scroll_id)

    @staticmethod
    def add_user(user):
        authenticate_header = Training.authenticate_header()
        url = "https://api.fifoundry.net/v1/admin/registration_sets"
        payload = {
            "data": {
                "type": "registration_sets",
                "attributes": {
                    "registrations": [
                        {
                            "rule_set": "user_rule_set",
                            "first_name": user.preferred_name
                            if user.preferred_name
                            else user.first_name,
                            "last_name": user.last_name,
                            "email": user.email,
                            # "location_id": "1712",
                        },
                        {"rule_set": "he_learner", "role": "undergrad"},
                    ]
                },
            }
        }
        response = requests.post(url, headers=authenticate_header, json=payload)
        if response.status_code == 201:
            print(f"User {user} successfully added to LMS system")
