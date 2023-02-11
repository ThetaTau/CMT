import json
import datetime
import requests
from time import sleep
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.db import models
from django.http import Http404
from django.db.models import Q
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
    course_title = models.CharField(max_length=500)
    completed = models.BooleanField(default=False)
    completed_time = models.DateTimeField(blank=True, null=True)
    max_quiz_score = models.FloatField()

    @staticmethod
    def authenticate_header():
        auth_file = settings.ROOT_DIR / "secrets" / "LMS_API_KEY"
        refresh = True
        response_json = {}
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
            url = "https://thetatau-tx.vectorlmsedu.com/oauth/token"
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
    def get_progress_all_users(
        since=None, scroll_id=None, override=False, days=7, missing=None
    ):
        return
        authenticate_header = Training.authenticate_header()
        lms_since_file = settings.ROOT_DIR / "secrets" / "LMS_SINCE"
        if since is None or override:
            if lms_since_file.exists() and not override:
                with open(lms_since_file) as file_obj:
                    response_json = json.load(file_obj)
                since = response_json["since"]
            else:
                print(f"Syncing {days=}")
                since = datetime.datetime.now() - datetime.timedelta(days=days)
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
                since=since, scroll_id=scroll_id, missing=missing
            )
            return
        elif response.status_code != 200:
            print(
                f"There was an error with training progress update, message: {response.reason}"
            )
        response_json = response.json()
        next = response_json["next"]
        data = response_json["data"]
        if missing is None:
            missing = []
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
            student_id = user_info["user"]["student_id"]
            query = Q(email__iexact=user_email) | Q(username__iexact=user_email)
            if student_id:
                query |= Q(user_id__iexact=student_id)
            user = User.objects.filter(query).first()
            if not user:
                print(f"User with email {user_email} or {student_id} does not exist")
                missing.append(user_email)
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
                # print(f"Training {obj} created {created} with values {values}")
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
            print(f"Sync complete, missing {missing}")
        else:
            Training.get_progress_all_users(
                since=next["since"], scroll_id=scroll_id, missing=missing
            )

    @staticmethod
    def get_location_position_ids(status, location):
        url = "https://thetatau-tx.vectorlmsedu.com/graphql/"
        authenticate_header = Training.authenticate_header()
        query_locations = f"""
                query
                   {{ Locations  (name: "{location}" )
                    {{ nodes
                      {{ locationId
                        name
                        code
                      }}
                    }}
                }}
                """
        response = requests.post(
            url, json={"query": query_locations}, headers=authenticate_header
        )
        all_locations = response.json()
        location_id = all_locations["data"]["Locations"]["nodes"][0]["locationId"]
        query_positions = f"""
                query
                   {{ Positions  (code: "{status[0:8]}")
                    {{ nodes
                      {{ positionId
                        name
                        code
                      }}
                    }}
                }}
                """
        response = requests.post(
            url, json={"query": query_positions}, headers=authenticate_header
        )
        all_positions = response.json()
        position_id = all_positions["data"]["Positions"]["nodes"][0]["positionId"]
        return location_id, position_id

    @staticmethod
    def add_user(user, request=None):
        authenticate_header = Training.authenticate_header()
        url = "https://thetatau-tx.vectorlmsedu.com/graphql/"
        status = user.current_status
        status_align = {
            "friend": "nonmember",
            "resignedCC": "resigned",
            "away": "active",
            "activepend": "active",
            "alumnipend": "alumni",
        }
        status = status_align.get(status, status)
        location_id, position_id = Training.get_location_position_ids(
            status, user.chapter.name
        )
        if not location_id or not position_id:
            response_json_location_add = ""
            if not location_id:
                location_add = f"""
                mutation  change {{
                    addLocation(
                        name: "{user.chapter.name}"
                        code: "{user.chapter.slug}"
                        parentId: "C90461D8-617A-11ED-ABCA-8399029E49FF"
                        )  {{
                        locationId
                        name
                    }}
                }}
                """
                authenticate_header = Training.authenticate_header()
                response = requests.post(
                    url, json={"query": location_add}, headers=authenticate_header
                )
                response_json_location_add = response.json()
                location_id = response_json_location_add["data"]["addLocation"][
                    "locationId"
                ]
            if not location_id or not position_id:
                message = (
                    f"Sync training is missing:<br>{location_id=} {position_id=} for {user=} should be "
                    f"{user.chapter.slug=} {status=}, Attempted to add location {response_json_location_add=}"
                )
                send_mail(
                    "Sync Training Error",
                    message,
                    "cmt@thetatau.org",
                    ["cmt@thetatau.org", "central.office@thetatau.org"],
                    fail_silently=True,
                )
                messages.add_message(request, messages.ERROR, message)
                return
        first_name = user.preferred_name if user.preferred_name else user.first_name
        add_user_mutation = f"""
        mutation  add {{
            addPerson(
                externalUniqueId: "{user.user_id}"
                first: "{first_name}"
                last: "{user.last_name}"
                username: "{user.email}"
                email: "{user.email}"
                positionId: "{position_id}"
                locationId: "{location_id}"
                ) {{
                username
                personId
            }}
        }}
        """
        response = requests.post(
            url, headers=authenticate_header, json={"query": add_user_mutation}
        )
        response_json = response.json()
        if response.status_code == 200:
            """
            {'data': {'addPerson': {'personId': 'C3F57814-96CF-11ED-98EA-B8B2786A17CA',
                'username': 'Jim.Gaffney@thetatau.org'}}}

            {'errors': [{'locations': [{'line': 15, 'column': 9}],
               'message': 'Unable to create person: This username already exists.\n',
               'path': ['addPerson']}],
             'data': {'addPerson': None}}
            """
            if "errors" not in response_json:
                message = f"{user} successfully added to training system"
                level = messages.INFO
                person_id = response_json["data"]["addPerson"]["personId"]
                if person_id and user.is_national_officer():
                    location_id, position_id = Training.get_location_position_ids(
                        "natoff", "Theta Tau"
                    )
                    query = f"""
                    mutation  JobMutation {{
                        Person (personId: "{person_id}") {{
                            addJob(locationId:"{location_id}", positionId:"{position_id}"){{
                                jobId
                            }}
                      }}
                    }}
                    """
                    response = requests.post(
                        url, json={"query": query}, headers=authenticate_header
                    )
                    json_response = response.json()
                    print(json_response)
            else:
                message = f"{user} NOT added to training system, maybe an error. {response_json}"
                level = messages.ERROR
        elif response.status_code == 429:
            # 150 requests per rolling 300 seconds
            sleep(120)
            print("Delaying for rate limit add training user")
            Training.add_user(user, request=request)
            return
        else:
            message = (
                f"{user} NOT added to training system, maybe an error. {response_json}"
            )
            level = messages.ERROR
        if request is None:
            print(message)
        else:
            messages.add_message(request, level, message)
        return response_json
