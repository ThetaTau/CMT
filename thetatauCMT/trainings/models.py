import json
import datetime
import requests
from time import sleep
from django.conf import settings
from django.contrib import messages
from django.db import models
from django.http import Http404
from django.db.models import Q
from core.models import TimeStampedModel
from users.models import User

LOCATION_IDS = {
    "alpha": "5B13D292-857B-11ED-9ADB-9E75914CA38D",
    "beta": "5B539C24-857B-11ED-8B20-6170107EB2B6",
    "chi": "F429FE1C-8282-11ED-95DE-C5B2914CA38D",
    "chi-beta": "5B8E3136-857B-11ED-98A1-24688EED22F2",
    "chi-delta": "5BE29CE4-857B-11ED-B6F1-F33DA3AC54A4",
    "chi-epsilon": "5C200462-857B-11ED-BC3B-8670107EB2B6",
    "chi-gamma": "5C638B56-857B-11ED-AE16-9E75914CA38D",
    "delta": "5CB1F37C-857B-11ED-9F4D-FE678EED22F2",
    "delta-beta": "5D06C3DE-857B-11ED-BE86-A13DA3AC54A4",
    "delta-gamma": "5D50A922-857B-11ED-BF48-8075914CA38D",
    "epsilon": "5D90474E-857B-11ED-913F-8670107EB2B6",
    "epsilon-beta": "5DD1758E-857B-11ED-9E3A-8075914CA38D",
    "epsilon-delta": "5E171058-857B-11ED-B358-8670107EB2B6",
    "epsilon-gamma": "5E56D1A2-857B-11ED-ADC3-6170107EB2B6",
    "eta": "5E976988-857B-11ED-94A2-24688EED22F2",
    "eta-beta": "5EDCE300-857B-11ED-97B0-9E75914CA38D",
    "eta-delta": "5F2ACF70-857B-11ED-BCAB-FE678EED22F2",
    "eta-epsilon": "5F65C2CE-857B-11ED-A4B9-6170107EB2B6",
    "eta-gamma": "5FA36412-857B-11ED-8F11-8075914CA38D",
    "gamma": "5FE3FAE0-857B-11ED-B213-A13DA3AC54A4",
    "gamma-beta": "6024F52C-857B-11ED-A9E0-24688EED22F2",
    "iota": "60644628-857B-11ED-A35E-F33DA3AC54A4",
    "iota-beta": "60A1B88C-857B-11ED-94CC-8075914CA38D",
    "iota-delta": "60E2CFDE-857B-11ED-834A-6170107EB2B6",
    "iota-epsilon": "61260FE2-857B-11ED-AFDA-8670107EB2B6",
    "iota-gamma": "61729556-857B-11ED-A7C5-3B688EED22F2",
    "iupui-candidate-chap": "61B7DCBA-857B-11ED-B55E-8670107EB2B6",
    "jmu-candidate-chapte": "61F65CCE-857B-11ED-B60C-FE678EED22F2",
    "kappa": "62372362-857B-11ED-A942-24688EED22F2",
    "kappa-beta": "62770C8E-857B-11ED-BA2F-A13DA3AC54A4",
    "kappa-delta": "62B3FC48-857B-11ED-BA6B-F33DA3AC54A4",
    "kappa-epsilon": "62EF0680-857B-11ED-B133-9E75914CA38D",
    "kappa-gamma": "6330DF4C-857B-11ED-A5FC-6170107EB2B6",
    "lambda": "6374AD1C-857B-11ED-91EE-8670107EB2B6",
    "lambda-beta": "63B67986-857B-11ED-AA51-3B688EED22F2",
    "lambda-delta": "63F4F2BA-857B-11ED-8CCC-3B688EED22F2",
    "lambda-epsilon": "643C15E6-857B-11ED-B05E-24688EED22F2",
    "lambda-gamma": "648225D6-857B-11ED-96F3-8075914CA38D",
    "mu": "64D50B34-857B-11ED-A14B-F33DA3AC54A4",
    "mu-beta": "6514ABFE-857B-11ED-80C4-9E75914CA38D",
    "mu-delta": "6558A52A-857B-11ED-85BD-6170107EB2B6",
    "mu-epsilon": "659857F6-857B-11ED-887A-24688EED22F2",
    "mu-gamma": "65D659B6-857B-11ED-BF62-8670107EB2B6",
    "nu": "6619543C-857B-11ED-99AF-F33DA3AC54A4",
    "nu-beta": "665F203E-857B-11ED-939E-3B688EED22F2",
    "nu-delta": "669FD14C-857B-11ED-B61B-A13DA3AC54A4",
    "nu-epsilon": "66E1423A-857B-11ED-9FB9-9E75914CA38D",
    "nu-gamma": "6721FF3C-857B-11ED-9129-3B688EED22F2",
    "omega": "67653DEC-857B-11ED-ADF4-6170107EB2B6",
    "omega-beta": "67A7018C-857B-11ED-9056-E23DA3AC54A4",
    "omega-delta": "67E3C2AC-857B-11ED-B4EC-F33DA3AC54A4",
    "omega-epsilon": "682AEAF6-857B-11ED-A9E8-E23DA3AC54A4",
    "omega-gamma": "687A6B6C-857B-11ED-8D99-B675914CA38D",
    "omicron": "68DF674C-857B-11ED-B8EA-9E75914CA38D",
    "omicron-beta": "691BF9B4-857B-11ED-A3EB-6170107EB2B6",
    "omicron-delta": "69594512-857B-11ED-9655-24688EED22F2",
    "omicron-epsilon": "6996617C-857B-11ED-8CC3-F33DA3AC54A4",
    "omicron-gamma": "69DF7D4E-857B-11ED-A73F-00688EED22F2",
    "onu-candidate-chapte": "6A302582-857B-11ED-89F4-6170107EB2B6",
    "phi": "6A6D4282-857B-11ED-A0BF-24688EED22F2",
    "phi-beta": "6AAAF762-857B-11ED-BEC4-8670107EB2B6",
    "phi-delta": "6AE8440A-857B-11ED-88ED-F33DA3AC54A4",
    "phi-epsilon": "6B2A406C-857B-11ED-80D1-9E75914CA38D",
    "phi-gamma": "6B6B5304-857B-11ED-A81F-6170107EB2B6",
    "pi": "6BA76BBE-857B-11ED-9A58-24688EED22F2",
    "pi-beta": "6BE8B538-857B-11ED-B259-3B688EED22F2",
    "pi-delta": "6C2835FA-857B-11ED-A9BB-F33DA3AC54A4",
    "pi-epsilon": "6C9284D2-857B-11ED-A4EF-053EA3AC54A4",
    "pi-gamma": "6CD1A162-857B-11ED-8091-6170107EB2B6",
    "psi": "6D1562C6-857B-11ED-B1A1-3B688EED22F2",
    "psi-beta": "6D52161C-857B-11ED-8922-E23DA3AC54A4",
    "psi-delta": "6D9B2CF8-857B-11ED-AE79-3B688EED22F2",
    "psi-epsilon": "6DE418F0-857B-11ED-BA07-F33DA3AC54A4",
    "psi-gamma": "6E334312-857B-11ED-B944-E23DA3AC54A4",
    "rho": "6E6CBD4A-857B-11ED-B544-24688EED22F2",
    "rho-beta": "6EB02652-857B-11ED-BD63-8670107EB2B6",
    "rho-delta": "6EF33758-857B-11ED-9E04-9570107EB2B6",
    "rho-epsilon": "6F4F44A8-857B-11ED-8A4E-B675914CA38D",
    "rho-gamma": "6FADC654-857B-11ED-AAF1-4A70107EB2B6",
    "row-candidate-chapte": "6FFE16E0-857B-11ED-B75B-3B688EED22F2",
    "sigma": "7042347E-857B-11ED-861B-A675914CA38D",
    "sigma-beta": "708BB720-857B-11ED-8B10-B675914CA38D",
    "sigma-delta": "70D51C08-857B-11ED-B791-9570107EB2B6",
    "sigma-epsilon": "7116D508-857B-11ED-B1DD-24688EED22F2",
    "sigma-gamma": "715C0DDA-857B-11ED-8E54-E33DA3AC54A4",
    "slo-candidate-chapte": "71B3D92A-857B-11ED-86A7-A675914CA38D",
    "tau": "7205530E-857B-11ED-96B9-9570107EB2B6",
    "tau-beta": "72463838-857B-11ED-AB8B-24688EED22F2",
    "tau-delta": "7285A1BC-857B-11ED-BAEA-9570107EB2B6",
    "tau-epsilon": "72C90C68-857B-11ED-B5FE-E33DA3AC54A4",
    "tau-gamma": "730FA4B6-857B-11ED-BB5C-4A70107EB2B6",
    "test": "73699822-857B-11ED-9AC4-3B688EED22F2",
    "theta": "73AF91BA-857B-11ED-BD1F-4A70107EB2B6",
    "theta-delta": "742342AE-857B-11ED-9E40-9570107EB2B6",
    "theta-epsilon": "747AE3F6-857B-11ED-9432-E33DA3AC54A4",
    "theta-gamma": "74BBAA12-857B-11ED-B456-A675914CA38D",
    "ua-candidate-chapter": "74F9A394-857B-11ED-BC0D-9570107EB2B6",
    "unh-candidate-chapte": "753B1B6C-857B-11ED-899B-E23DA3AC54A4",
    "unlv-candidate-chapt": "757ACDAC-857B-11ED-83EC-24688EED22F2",
    "upsilon": "75B873FA-857B-11ED-9161-4A70107EB2B6",
    "upsilon-beta": "761D3394-857B-11ED-A275-3B688EED22F2",
    "upsilon-delta": "765FC5B0-857B-11ED-A155-E33DA3AC54A4",
    "upsilon-epsilon": "76A65FDE-857B-11ED-929F-9A70107EB2B6",
    "upsilon-gamma": "7702799A-857B-11ED-A251-3B688EED22F2",
    "uw-candidate-chapter": "774AAA44-857B-11ED-BD4C-E23DA3AC54A4",
    "vic-candidate-chapte": "7794F32E-857B-11ED-92E8-5F75914CA38D",
    "xi": "77D44A42-857B-11ED-8138-3B688EED22F2",
    "xi-beta": "7817437E-857B-11ED-A99A-E23DA3AC54A4",
    "xi-delta": "78752FC0-857B-11ED-AEBA-6C70107EB2B6",
    "xi-epsilon": "78CBB156-857B-11ED-82B5-E23DA3AC54A4",
    "xi-gamma": "7912C096-857B-11ED-8827-9570107EB2B6",
    "zeta": "79686C62-857B-11ED-B008-6C70107EB2B6",
    "zeta-beta": "79B7102E-857B-11ED-8F4F-9575914CA38D",
    "zeta-delta": "79F8BCB8-857B-11ED-BD1C-6C70107EB2B6",
    "zeta-epsilon": "7A601F0C-857B-11ED-852E-3B688EED22F2",
    "zeta-gamma": "7AA8584E-857B-11ED-84F4-F73DA3AC54A4",
}
POSITION_IDS = {
    "active": "57C2B918-8284-11ED-975A-DBF9A2AC54A4",
    "alumni": "53D639CE-8284-11ED-86FD-DBF9A2AC54A4",
    "pnm": "007CFE80-8283-11ED-BCC2-B0268EED22F2",
}


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
    def add_user(user, request=None):
        # trainings = user.trainings.all()
        # if trainings:
        #     # If there are any trainings then we know user already in system
        #     message = f"{user} skipped, already in system"
        #     if request:
        #         messages.add_message(request, messages.WARNING, message)
        #     else:
        #         print(message)
        #     return
        authenticate_header = Training.authenticate_header()
        url = "https://thetatau-tx.vectorlmsedu.com/graphql/"
        location_id = LOCATION_IDS.get(user.chapter.slug, None)
        position_id = POSITION_IDS.get(user.current_status, None)
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
