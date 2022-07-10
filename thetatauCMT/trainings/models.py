import json
import datetime
import requests
from time import sleep
from django.conf import settings
from django.contrib import messages
from django.db import models
from django.http import Http404
from core.models import TimeStampedModel
from users.models import User

LABEL_IDS = {
    "Zeta Gamma": "269850",
    "Zeta Epsilon": "269849",
    "Zeta Delta": "269848",
    "Zeta": "269847",
    "Xi Gamma": "269846",
    "Xi Epsilon": "269845",
    "Xi Delta": "269844",
    "Xi Beta": "269843",
    "Xi": "269842",
    "UW Candidate Chapter": "269841",
    "Upsilon Gamma": "269840",
    "Upsilon Epsilon": "269839",
    "Upsilon Delta": "269838",
    "Upsilon Beta": "269837",
    "Upsilon": "269836",
    "UNLV Candidate Chapter": "269835",
    "Theta Gamma": "269834",
    "Theta Epsilon": "269833",
    "Theta Delta": "269832",
    "TEST": "269831",
    "Tau Gamma": "269830",
    "Tau Epsilon": "269829",
    "Tau Delta": "269828",
    "Tau Beta": "269827",
    "SLO Candidate Chapter": "269826",
    "SJSU Candidate Chapter": "269825",
    "Sigma Gamma": "269824",
    "Sigma Epsilon": "269823",
    "Sigma Delta": "269822",
    "Sigma": "269821",
    "Rho Gamma": "269820",
    "Rho Epsilon": "269819",
    "Rho Delta": "269818",
    "Rho Beta": "269817",
    "Rho": "269816",
    "Psi Gamma": "269815",
    "Psi Epsilon": "269814",
    "Psi Delta": "269813",
    "Psi Beta": "269812",
    "Pi Gamma": "269811",
    "Pi Epsilon": "269810",
    "Pi Delta": "269809",
    "Pi": "269808",
    "Phi Gamma": "269807",
    "Phi Epsilon": "269806",
    "Phi Delta": "269805",
    "Phi": "269804",
    "Omicron Epsilon": "269803",
    "Omicron Delta": "269802",
    "Omicron Beta": "269801",
    "Omicron": "269800",
    "Omega Gamma": "269799",
    "Omega Delta": "269798",
    "Omega Beta": "269797",
    "Omega": "269796",
    "Nu Gamma": "269795",
    "Nu Epsilon": "269794",
    "Nu Delta": "269793",
    "Mu Gamma": "269792",
    "Mu Epsilon": "269791",
    "Mu Delta": "269790",
    "Mu": "269789",
    "Lambda Gamma": "269788",
    "Lambda Epsilon": "269787",
    "Lambda Delta": "269786",
    "Kappa Gamma": "269785",
    "Kappa Epsilon": "269784",
    "Kappa Delta": "269783",
    "Kappa Beta": "269782",
    "Kappa": "269781",
    "JMU Candidate Chapter": "269780",
    "IUPUI Candidate Chapter": "269779",
    "Iota Gamma": "269778",
    "Iota Epsilon": "269777",
    "Iota Delta": "269776",
    "Gamma Beta": "269775",
    "Eta Gamma": "269774",
    "Eta Delta": "269773",
    "Eta": "269772",
    "Epsilon Delta": "269771",
    "Epsilon Beta": "269770",
    "Epsilon": "269769",
    "Delta Gamma": "269768",
    "Delta": "269767",
    "Chi Gamma": "269766",
    "Chi Epsilon": "269765",
    "Chi Beta": "269764",
    "Chi": "269763",
    "Beta": "269762",
    "Alpha": "269761",
    "alumni": "269853",
    "pnm": "269852",
    "active": "269851",
}


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
                raise Http404(
                    f"Training System authentication error: {response.reason}"
                )
        authenticate_header = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"{response_json['token_type']} {response_json['access_token']}",
        }
        return authenticate_header

    @staticmethod
    def get_progress_all_users(since=None, scroll_id=None, override=False):
        authenticate_header = Training.authenticate_header()
        lms_since_file = settings.ROOT_DIR / "secrets" / "LMS_SINCE"
        if since is None or override:
            if lms_since_file.exists() and not override:
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
        print(f"Training progress update params {params}")
        response = requests.get(url, headers=authenticate_header, params=params)
        if response.status_code == 204:
            print(f"There were no updated trainings, message: {response.reason}")
            return
        elif response.status_code == 429:
            # 200 requests per rolling 60 seconds
            sleep(120)
            print("Delaying for rate limit training progress update")
            Training.get_progress_all_users(
                since=since, scroll_id=scroll_id, override=override
            )
            return
        elif response.status_code != 200:
            print(
                f"There was an error with training progress update, message: {response.reason}"
            )
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
            try:
                user = User.objects.get(email=user_email)
            except User.DoesNotExist:
                print(f"User with email {user_email} does not exist")
                continue
            for progress in user_info["progress"]:
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
                print(f"Training {obj} created {created} with values {values}")
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
    def add_user(user, request=None):
        trainings = user.trainings.all()
        if trainings:
            # If there are any trainings then we know user already in system
            message = f"{user} skipped, already in system"
            if request:
                messages.add_message(request, messages.WARNING, message)
            else:
                print(message)
            return
        authenticate_header = Training.authenticate_header()
        url = "https://api.fifoundry.net/v1/admin/registration_sets"
        chapter_label = LABEL_IDS.get(user.chapter.name, None)
        status_label = LABEL_IDS.get(user.current_status, None)
        labels = [label for label in [chapter_label, status_label] if label]
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
                            "category_labels": labels,
                        },
                        {"rule_set": "he_learner", "role": "undergrad"},
                    ]
                },
            }
        }
        response = requests.post(url, headers=authenticate_header, json=payload)
        if response.status_code == 201:
            message = f"{user} successfully added to training system"
            level = messages.INFO
        elif response.status_code == 429:
            # 200 requests per rolling 60 seconds
            sleep(120)
            print("Delaying for rate limit add training user")
            Training.add_user(user, request=request)
            return
        else:
            message = f"{user} NOT added to training system, likely a duplicate. {response.reason}"
            level = messages.ERROR
        if request is None:
            print(message)
        else:
            messages.add_message(request, level, message)
