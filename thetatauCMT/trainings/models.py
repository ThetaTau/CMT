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
    def get_progress_all_users():
        url = "https://thetatau-tx.vectorlmsedu.com/graphql/"
        authenticate_header = Training.authenticate_header()
        has_next = True
        cursor = ""
        batch_num = -1
        while has_next:
            if cursor:
                cursor = f'after: "{cursor}"'
            query = f"""
                query
                {{ People (first: 100 {cursor})
                    {{ nodes
                       {{ username
                           first
                           last
                         externalUniqueId
                         personId
                         progress {{
                            completed
                            completeTime
                            courseInfo {{
                                title
                                courseInfoId
                            }}
                            progressId
                            maxQuizScore
                            }}
                       }}
                      pageInfo {{
                           count
                           totalCount
                           startCursor
                           endCursor
                           hasNextPage
                           hasPreviousPage
                       }}
                    }}
                }}
                """
            try:
                response = requests.post(
                    url, json={"query": query}, headers=authenticate_header
                )
                json_response = response.json()
            except:
                if response.status_code == 429:
                    print("Delay for 300...")
                    sleep(300)
                    authenticate_header = Training.authenticate_header()
                    continue
                break
            users = json_response["data"]["People"]["nodes"]
            has_next = json_response["data"]["People"]["pageInfo"]["hasNextPage"]
            cursor = json_response["data"]["People"]["pageInfo"]["endCursor"]
            total = json_response["data"]["People"]["pageInfo"]["totalCount"]
            batch_num += 1
            for count, user_info in enumerate(users):
                print(
                    f"Working on {count + 1 + (100 * batch_num)}/{total} batch has more {has_next}"
                )
                progresses = user_info["progress"]
                username = user_info["username"]
                user_id = user_info["externalUniqueId"]
                # The Vector system does not keep track of assignments only
                # completions so assume assigned to our only training
                completed = False
                completed_at = None
                progress_id = ""
                max_quiz_score = 0
                if progresses:
                    for progress in progresses:
                        course_title = progress["courseInfo"]["title"]
                        if "(Full Course)" in course_title:
                            completed = progress["completed"]
                            completed_at = progress["completeTime"]
                            progress_id = progress["progressId"]
                            max_quiz_score = progress["maxQuizScore"]
                            if not max_quiz_score:
                                if completed:
                                    max_quiz_score = 100
                                else:
                                    max_quiz_score = 0
                # We want to maintain backwards connection with old training system,
                # so we use the same title/id
                course_title = "CommunityEdu: Fraternity & Sorority Life"
                course_id = "5d7b72cf-7e22-43a3-a4aa-628d8ee6c1a9"
                user = User.objects.filter(
                    Q(username__iexact=username)
                    | Q(user_id__iexact=user_id)
                    | Q(email__iexact=username)
                    | Q(email_school__iexact=username)
                ).first()
                if not user:
                    print(f"USER DOES NOT EXIST {user_info}")
                    continue
                values = dict(
                    user=user,
                    progress_id=progress_id,
                    course_id=course_id,
                    course_title=course_title,
                    completed=completed,
                    completed_time=completed_at,
                    max_quiz_score=max_quiz_score,
                )
                print(values)
                obj, created = Training.objects.update_or_create(
                    user=user, course_id=course_id, defaults=values
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
