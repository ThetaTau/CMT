import base64
import datetime
import json
import logging
import re
from time import sleep

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.db import models
from django.db.models import Q
from django.http import Http404
from django.utils import timezone

import core.requests as requests
from core.models import TimeStampedModel
from thetatauCMT.users.models import User

logger = logging.getLogger(__name__)


def _log_level_for(message_level):
    """Map a Django ``messages`` level to a stdlib ``logging`` level."""
    if message_level >= messages.ERROR:
        return logging.ERROR
    if message_level >= messages.WARNING:
        return logging.WARNING
    return logging.INFO


class TrainingSystemUnavailable(Exception):
    """The Vector LMS API is unreachable or returned an unusable response.

    Raised by the Vector LMS request helpers when the endpoint cannot be reached,
    answers with a non-success status after retries, or returns an empty / non-JSON
    body (an HTML gateway page, for example, makes ``response.json()`` raise
    ``JSONDecodeError``). Callers catch it to surface a friendly "training system
    unavailable, please try again later" message instead of returning a 500
    (issues #840, #862, #877, #879, #917, #918, #979, #1004).
    """


# HTTP statuses the Vector LMS returns transiently and that typically succeed on a
# retry: 429 (rate limit) and the 5xx gateway family.
_TRANSIENT_LMS_STATUSES = frozenset({429, 500, 502, 503, 504})


def _lms_response_json(response, description):
    """Return parsed JSON from a Vector LMS ``response`` or raise ``TrainingSystemUnavailable``.

    Guards the two production failure modes: a non-success status (an HTML gateway
    or 5xx error page) and an empty / non-JSON body, both of which otherwise make
    ``response.json()`` raise ``JSONDecodeError`` (a ``ValueError``) and bubble up as
    a 500.
    """
    # ``requests.Response.ok`` is ``status_code < 400``; derive it from the status
    # code so lightweight test doubles only need to expose ``status_code``/``json``.
    status_code = getattr(response, "status_code", None)
    if status_code is not None and status_code >= 400:
        reason = getattr(response, "reason", "") or ""
        raise TrainingSystemUnavailable(f"{description}: training system returned HTTP {status_code} {reason}".strip())
    try:
        return response.json()
    except ValueError as exc:  # JSONDecodeError is a subclass of ValueError
        raise TrainingSystemUnavailable(
            f"{description}: training system returned an empty or non-JSON response."
        ) from exc


def _post_lms_json(url, *, description="Vector LMS request", attempts=3, initial_delay=1.0, backoff=2.0, **post_kwargs):
    """POST to the Vector LMS, retrying transient failures, and return parsed JSON.

    Mirrors :func:`core.utils.retry_google_api` for the retry/backoff shape but
    understands ``requests``-style responses: connection errors and transient
    statuses (429 / 5xx) are retried with exponential backoff, while a persistent
    failure, a non-success status, or an empty / non-JSON body raises
    ``TrainingSystemUnavailable`` so the caller can surface a friendly message
    instead of a 500.
    """
    delay = initial_delay
    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(url, **post_kwargs)
        except requests.RequestException as exc:
            if attempt == attempts:
                raise TrainingSystemUnavailable(f"{description}: could not reach the training system.") from exc
            logger.warning(
                "%s could not connect (attempt %s/%s); retrying in %.1fs",
                description,
                attempt,
                attempts,
                delay,
            )
            sleep(delay)
            delay *= backoff
            continue
        status_code = getattr(response, "status_code", None)
        if status_code in _TRANSIENT_LMS_STATUSES and attempt < attempts:
            logger.warning(
                "%s got transient HTTP %s (attempt %s/%s); retrying in %.1fs",
                description,
                status_code,
                attempt,
                attempts,
                delay,
            )
            sleep(delay)
            delay *= backoff
            continue
        return _lms_response_json(response, description)


# The Vector LMS course id/title for the required health & safety programming
# (branded "CommunityEdu"). Kept as a shared constant since it identifies the
# course used both when upserting `Training` rows from the LMS and when
# computing chapter completion percentages (`trainings.services`).
COMMUNITY_EDU_COURSE_ID = "5d7b72cf-7e22-43a3-a4aa-628d8ee6c1a9"
COMMUNITY_EDU_COURSE_TITLE = "CommunityEdu: Fraternity & Sorority Life"


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
    def authenticate_header(force=False):
        auth_file = settings.ROOT_DIR / "secrets" / "LMS_API_KEY"
        refresh = True
        response_json = {}
        if not force and auth_file.exists():
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
            # A gateway/5xx error or empty body used to make ``response.json()`` raise
            # ``JSONDecodeError`` here and 500 the caller (issue #1004); route the token
            # request through the shared helper so an outage raises
            # ``TrainingSystemUnavailable`` (retried for transient 5xx) instead.
            response_json = _post_lms_json(
                url,
                params=params,
                headers=headers,
                description="Training system authentication",
            )
            with open(auth_file, "w") as file_obj:
                json.dump(response_json, file_obj)
        try:
            authenticate_header = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"{response_json['token_type']} {response_json['access_token']}",
            }
        except KeyError as exc:
            raise TrainingSystemUnavailable(
                "Training system authentication returned an unexpected response (missing token)."
            ) from exc
        return authenticate_header

    @staticmethod
    def get_progress_all_users():
        url = "https://thetatau-tx.vectorlmsedu.com/graphql/"
        has_next = True
        cursor = ""
        batch_num = -1
        while has_next:
            authenticate_header = Training.authenticate_header()
            if cursor:
                cursor = f'after: "{cursor}"'
            query = f"""
                query
                {{ People (first: 100 {cursor} active: "1")
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
                json_response = _post_lms_json(
                    url,
                    json={"query": query},
                    headers=authenticate_header,
                    description="Training system progress lookup",
                )
            except TrainingSystemUnavailable as exc:
                # The cached token can go stale mid-sync on a large batch (issue:
                # a 9000-user sync failing ~halfway through with a 401). 401 isn't
                # in _post_lms_json's transient-retry set, so force a fresh token
                # (bypassing the cache) and retry this page once before giving up.
                if "HTTP 401" not in str(exc):
                    raise
                logger.warning("Training system progress lookup got HTTP 401; forcing token refresh and retrying")
                authenticate_header = Training.authenticate_header(force=True)
                json_response = _post_lms_json(
                    url,
                    json={"query": query},
                    headers=authenticate_header,
                    description="Training system progress lookup",
                )
            if "data" not in json_response:
                raise TrainingSystemUnavailable(f"Training system progress lookup returned no data: {json_response}")
            users = json_response["data"]["People"]["nodes"]
            has_next = json_response["data"]["People"]["pageInfo"]["hasNextPage"]
            cursor = json_response["data"]["People"]["pageInfo"]["endCursor"]
            total = json_response["data"]["People"]["pageInfo"]["totalCount"]
            batch_num += 1
            for count, user_info in enumerate(users):
                logger.info(f"Working on {count + 1 + (100 * batch_num)}/{total} batch has more {has_next}")
                progresses = user_info["progress"]
                username = user_info["username"]
                user_pk = user_info["externalUniqueId"]
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
                course_title = COMMUNITY_EDU_COURSE_TITLE
                course_id = COMMUNITY_EDU_COURSE_ID
                user = User.objects.filter(
                    Q(username__iexact=username)
                    | Q(id__iexact=user_pk)
                    | Q(email__iexact=username)
                    | Q(email_school__iexact=username)
                ).first()
                if not user:
                    logger.warning(f"USER DOES NOT EXIST {user_info}")
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
                logger.debug("Training upsert values: %s", values)
                try:
                    obj, created = Training.objects.update_or_create(user=user, course_id=course_id, defaults=values)
                except Training.MultipleObjectsReturned:
                    trainings = Training.objects.filter(user=user, course_id=course_id).order_by("-created")
                    for training in trainings[1:]:
                        training.delete()
                    obj, created = Training.objects.update_or_create(user=user, course_id=course_id, defaults=values)

    @staticmethod
    def get_extra_groups():
        url = "https://thetatau-tx.vectorlmsedu.com/graphql/"
        authenticate_header = Training.authenticate_header()
        has_next = True
        cursor = ""
        extra_groups_total = []
        while has_next:
            if cursor:
                cursor = f'after: "{cursor}"'
            query_positions = f"""
                query
                   {{ Positions (first: 100 {cursor})
                    {{ nodes
                      {{ positionId
                        name
                        code
                      }}
                      pageInfo
                      {{
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
            json_response = _post_lms_json(
                url,
                json={"query": query_positions},
                headers=authenticate_header,
                description="Training system positions lookup",
            )
            positions = (json_response.get("data") or {}).get("Positions") or {}
            extra_groups = [(node["code"], node["name"]) for node in (positions.get("nodes") or []) if node["code"]]
            extra_groups_total.extend(extra_groups)
            page_info = positions.get("pageInfo") or {}
            has_next = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor", "")
        extra_groups_total = sorted(extra_groups_total, key=lambda x: x[1].lower())
        return extra_groups_total

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
        all_locations = _post_lms_json(
            url,
            json={"query": query_locations},
            headers=authenticate_header,
            description="Training system location lookup",
        )
        # An empty ``nodes`` list means the location does not exist yet in the training
        # system. Return ``None`` so ``add_user`` creates it via its ``addLocation``
        # fallback instead of raising ``IndexError`` (issue #1085). A gateway/non-JSON
        # response now raises ``TrainingSystemUnavailable`` instead of a 500 (Cluster A).
        location_nodes = ((all_locations.get("data") or {}).get("Locations") or {}).get("nodes") or []
        location_id = location_nodes[0]["locationId"] if location_nodes else None
        # Frontend will let you add position as long as you want,
        # but the graphql will only return and match on the first 8 characters
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
        all_positions = _post_lms_json(
            url,
            json={"query": query_positions},
            headers=authenticate_header,
            description="Training system position lookup",
        )
        position_id_nodes = ((all_positions.get("data") or {}).get("Positions") or {}).get("nodes") or []
        if position_id_nodes:
            position_id = position_id_nodes[0]["positionId"]
        else:
            # if no data
            # {'data': {'Positions': {'nodes': []}}}
            add_position = f"""
                mutation  change {{
                    addPosition(
                        name: "{status}"
                        code: "{status}"
                        )  {{
                        positionId
                        name
                        code
                    }}
                }}
                """
            new_positions = _post_lms_json(
                url,
                json={"query": add_position},
                headers=authenticate_header,
                description="Training system add position",
            )
            position_id = ((new_positions.get("data") or {}).get("addPosition") or {}).get("positionId")
        return location_id, position_id

    @staticmethod
    def add_user(user, extra_group=None, request=None):
        """Add ``user`` to the Vector LMS, degrading gracefully when it is down.

        Wraps :meth:`_add_user` so a Vector LMS outage surfaces a friendly
        "training system unavailable, please try again later" message (and the
        calling officer/admin/form POST still succeeds) instead of a 500
        (issues #840, #862, #877, #879, #917, #979).
        """
        try:
            return Training._add_user(user, extra_group=extra_group, request=request)
        except (TrainingSystemUnavailable, requests.RequestException):
            logger.exception("Training add_user failed for %s: training system unavailable", user)
            if request is not None:
                messages.add_message(
                    request,
                    messages.WARNING,
                    f"{user} could not be added to the training system because it is unavailable. "
                    "Please try again later.",
                )
            return None

    @staticmethod
    def _add_user(user, extra_group=None, request=None):
        message = ""
        level = messages.INFO
        authenticate_header = Training.authenticate_header()
        url = "https://thetatau-tx.vectorlmsedu.com/graphql/"
        status = user.current_status
        status_align = {
            "friend": "nonmember",
            "resignedCC": "resigned",
            "away": "active",
            "activepend": "active",
            "alumnipend": "alumni",
            "": "pnm",
        }
        status = status_align.get(status, status)
        location_id, position_id = Training.get_location_position_ids(status, user.chapter.name)
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
                response_json_location_add = _post_lms_json(
                    url,
                    json={"query": location_add},
                    headers=authenticate_header,
                    description="Training system add location",
                )
                location_id = ((response_json_location_add.get("data") or {}).get("addLocation") or {}).get(
                    "locationId"
                )
            if not location_id or not position_id:
                message = (
                    f"Sync training is missing:<br>{location_id=} {position_id=} for {user=} should be "
                    f"{user.chapter.slug=} {status=}, Attempted to add location {response_json_location_add=}"
                    "Please notify the central office."
                )
                send_mail(
                    "Sync Training Error",
                    message,
                    "cmt@thetatau.org",
                    ["cmt@thetatau.org", "central.office@thetatau.org"],
                    fail_silently=True,
                )
                logger.error(message)
                if request is not None:
                    messages.add_message(request, messages.ERROR, message)
                return
        first_name = user.preferred_name if user.preferred_name else user.first_name
        add_user_mutation = f"""
        mutation  add {{
            addPerson(
                externalUniqueId: "{user.id}"
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
        response = requests.post(url, headers=authenticate_header, json={"query": add_user_mutation})
        if response.status_code == 200:
            response_json = _lms_response_json(response, "Training system add person")
            """
            {'data': {'addPerson': {'personId': 'C3F57814-96CF-11ED-98EA-B8B2786A17CA',
                'username': 'Jim.Gaffney@thetatau.org'}}}

            {'errors': [{'locations': [{'line': 15, 'column': 9}],
               'message': 'Unable to create person: This username already exists.\n',
               'path': ['addPerson']}],
             'data': {'addPerson': None}}
            """
            person_id = None
            if "errors" not in response_json:
                message = f"{user} successfully added to training system"
                level = messages.INFO
                person_id = response_json["data"]["addPerson"]["personId"]
            elif "This username already exists" in response_json["errors"][0]["message"]:
                query = f"""
                query a
                {{ username: People (username: "{user.username}" )
                    {{ nodes
                       {{ username
                         personId
                       }}
                    }}
                    email: People (username: "{user.email}" )
                    {{ nodes
                       {{ username
                         personId
                       }}
                    }}
                    email_school: People (username: "{user.email_school}" )
                    {{ nodes
                       {{ username
                         personId
                       }}
                    }}
                    externalUniqueId: People (externalUniqueId: "{user.id}" )
                    {{ nodes
                       {{ username
                         personId
                       }}
                    }}
                }}
                """
                response_json = _post_lms_json(
                    url,
                    headers=authenticate_header,
                    json={"query": query},
                    description="Training system person lookup",
                )
                people_nodes = []
                response_data = response_json.get("data") or {}
                for node_name in [
                    "username",
                    "email",
                    "email_school",
                    "externalUniqueId",
                ]:
                    nodes = (response_data.get(node_name) or {}).get("nodes") or []
                    people_nodes.extend(nodes)
                if people_nodes:
                    person_id = people_nodes[0]["personId"]
                    ids = set([people_node["personId"] for people_node in people_nodes])
                    if len(ids) > 1:
                        message = (
                            f"{user} Had multiple matching accounts. All other accounts, using first {people_nodes}"
                        )
                        level = messages.ERROR
                else:
                    message = f"{user} NOT added to training system or updated, maybe an error. {response_json}"
                    level = messages.ERROR
            else:
                message = f"{user} NOT added to training system, maybe an error. {response}"
                level = messages.ERROR

            def add_extra_group(extra_group, location, person_id):
                try:
                    location_id, position_id = Training.get_location_position_ids(extra_group, location)
                    query = f"""
                        mutation  JobMutation {{
                            Person (personId: "{person_id}") {{
                                addJob(locationId:"{location_id}", positionId:"{position_id}"){{
                                    jobId
                                }}
                          }}
                        }}
                        """
                    json_response = _post_lms_json(
                        url,
                        json={"query": query},
                        headers=authenticate_header,
                        description="Training system add job",
                    )
                    logger.debug("Training add_extra_group response: %s", json_response)
                    return True
                except (requests.RequestException, ValueError, TrainingSystemUnavailable):
                    # The Vector LMS endpoint intermittently returns an empty body or an
                    # HTML gateway error (5xx), which makes ``response.json()`` raise
                    # ``JSONDecodeError`` (a ``ValueError``). Treat any such failure as a
                    # soft failure so the officer-update POST is not turned into a 500
                    # (see issue #1086).
                    logger.exception(
                        "Training add_extra_group failed for person_id=%s extra_group=%s",
                        person_id,
                        extra_group,
                    )
                    return False

            if person_id and user.is_national_officer():
                if add_extra_group("natoff", "Theta Tau", person_id):
                    message += f" Added {user} to extra_group=natoff and location=Theta Tau"
                else:
                    message += f" Could NOT add {user} to extra_group=natoff; training system unavailable, please try again later."
                    level = max(level, messages.WARNING)
            if person_id and extra_group:
                if add_extra_group(extra_group, user.chapter.name, person_id):
                    message += f" Added {user} to {extra_group=} and location={user.chapter.name}"
                else:
                    message += (
                        f" Could NOT add {user} to {extra_group=}; training system unavailable, please try again later."
                    )
                    level = max(level, messages.WARNING)
        elif response.status_code == 429:
            # 150 requests per rolling 300 seconds
            sleep(120)
            logger.warning("Delaying for rate limit add training user")
            Training.add_user(user, request=request)
            return
        else:
            message = f"{user} NOT added to training system, maybe an error. {response}"
            level = messages.ERROR
        logger.log(_log_level_for(level), message)
        if request is not None:
            messages.add_message(request, level, message)
        return response

    @staticmethod
    def get_person_id(user, id_type="id", request=None):
        message = ""
        level = messages.ERROR
        url = "https://thetatau-tx.vectorlmsedu.com/graphql/"
        authenticate_header = Training.authenticate_header()
        if id_type == "id":
            query_str = f'externalUniqueId: "{user.id}"'
        else:
            query_str = f'username: "{user.username}"'
        find_id_query = f"""
        query {{ People ({query_str})
             {{ nodes
                {{
                  first
                  last
                  personId
                  username
                  externalUniqueId
               }}
            }}
         }}"""
        #
        response = requests.post(url, json={"query": find_id_query}, headers=authenticate_header)
        person_id = None
        if response.status_code == 429:
            # 150 requests per rolling 300 seconds
            logger.warning("Delaying for rate limit deactivate training user")
            sleep(120)
            return Training.get_person_id(user, id_type=id_type, request=request)
        elif response.status_code != 200:
            message = f"    {user} NOT deactivated from training system, ERROR getting ID maybe an error. {response.reason} {find_id_query}"
            level = messages.ERROR
            logger.log(_log_level_for(level), message)
            if request is not None:
                messages.add_message(request, level, message)
        else:
            response_json = _lms_response_json(response, "Training system person id lookup")
            if "errors" not in response_json:
                # {'data': {'People': {'nodes': []}}}
                nodes = response_json["data"]["People"]["nodes"]
                if nodes:
                    person_id = nodes[0]["personId"]
                elif id_type == "id":
                    logger.info(f"    No id found for type {id_type} for {user} {response_json}")
                    person_id, message, level = Training.get_person_id(user, id_type="username", request=request)
                else:
                    logger.info(f"    No id found for type {id_type} for {user} {response_json}")
            else:
                message = (
                    f"    {user} NOT deactivated from training system, ERROR getting ID maybe an error. {response_json}"
                )
                level = messages.ERROR
        return person_id, message, level

    @staticmethod
    def deactivate_user(user, request=None):
        """Deactivate ``user`` in the Vector LMS, degrading gracefully when it is down.

        Wraps :meth:`_deactivate_user` so a Vector LMS outage does not 500 the
        depledge / resignation / disciplinary paths that call it; the status change
        is already saved and the deactivation is a best-effort side effect.
        """
        try:
            return Training._deactivate_user(user, request=request)
        except (TrainingSystemUnavailable, requests.RequestException):
            logger.exception("Training deactivate_user failed for %s: training system unavailable", user)
            if request is not None:
                messages.add_message(
                    request,
                    messages.WARNING,
                    f"{user} could not be deactivated in the training system because it is unavailable. "
                    "Please try again later.",
                )
            return None

    @staticmethod
    def _deactivate_user(user, request=None):
        response_json = None
        url = "https://thetatau-tx.vectorlmsedu.com/graphql/"
        authenticate_header = Training.authenticate_header()
        # https://thetatau-tx.vectorlmsedu.com/login
        logger.info(f"Deactivating user {user}")
        person_id, message, level = Training.get_person_id(user, request=request)
        if person_id:
            deactivate_user_mutation = f"""
            mutation  DeactivatepersonMutation {{
                Person(personId: "{person_id}") {{
                deactivate  {{
                    username
                    personId
                    externalUniqueId
                }}
              }}
            }}
            """
            response = requests.post(
                url,
                headers=authenticate_header,
                json={"query": deactivate_user_mutation},
            )
            if response.status_code == 200:
                response_json = _lms_response_json(response, "Training system deactivate person")
                """
                {'data': {'Person': {'deactivate': {'personId': '0C235BDE-7314-11EF-8C2B-FB441EDB9904',
                    'externalUniqueId': '93697',
                    'username': 'jim.gaffney@thetatau.org'}}}}
                """
                if "errors" not in response_json:
                    message = f"    {user} successfully deactivated from training system"
                    level = messages.INFO
                else:
                    message = f"    {user} NOT deactivated from training system, maybe an error. {response_json}"
                    level = messages.ERROR
            elif response.status_code == 429:
                # 150 requests per rolling 300 seconds
                sleep(120)
                logger.warning("Delaying for rate limit deactivate training user")
                Training.deactivate_user(user, request=request)
                return
            else:
                message = f"    {user} NOT deactivated from training system, maybe an error. {response.reason}"
                level = messages.ERROR
        logger.log(_log_level_for(level), message)
        if request is not None:
            messages.add_message(request, level, message)

    @staticmethod
    def _ed_authenticate_header():
        """Return an ``Authorization`` header for the Open edX REST API.

        Uses the OAuth2 ``client_credentials`` grant. The application owner
        tied to ``ED_ID``/``ED_SECRET`` must be Open edX **global staff**
        (``is_staff=True``); the bulk-enroll endpoint uses ``IsStaff`` and
        otherwise responds ``403``.
        """
        credential = f"{settings.ED_ID}:{settings.ED_SECRET}"
        encoded_credential = base64.b64encode(credential.encode("utf-8")).decode("utf-8")
        token_response = requests.post(
            f"{settings.ED_HOST}/oauth2/access_token",
            headers={
                "Authorization": f"Basic {encoded_credential}",
                "Cache-Control": "no-cache",
            },
            data={"grant_type": "client_credentials", "token_type": "jwt"},
        )
        if token_response.status_code != 200:
            raise Http404(f"Open edX authentication error: {token_response.reason}")
        access_token = token_response.json()["access_token"]
        return {
            "Authorization": f"JWT {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _interpret_enroll_result(identifier_results):
        """Collapse bulk-enroll per-identifier results into ``(status, detail)``.

        ``status`` is one of ``"enrolled"``, ``"pending"`` or ``"error"``.
        Only one identifier is ever sent, so the first result is inspected.
        """
        if not identifier_results:
            return "pending", "submitted (no confirmation returned)"
        result = identifier_results[0]
        if not isinstance(result, dict):
            return "pending", "submitted"
        if result.get("invalidIdentifier"):
            return "error", "invalid identifier (email not accepted by Open edX)"
        if result.get("error"):
            return "error", str(result.get("message") or "enrollment error")
        after = result.get("after") or {}
        if after.get("enrollment"):
            return "enrolled", "enrolled"
        if after.get("allowed"):
            return "pending", "pending: enrolls once the user logs in via SSO"
        return "pending", "submitted"

    @staticmethod
    def enroll_user_ed(user, courses=None, header=None, request=None, _retried=False):
        """Enroll ``user`` in the configured Open edX course run(s).

        Returns a list of ``(course_id, status, message)`` tuples.

        ``bulk_enroll`` always answers ``200 OK`` when the payload is valid; the
        real outcome lives in the response body. With ``auto_enroll`` an account
        that does not exist yet only gets a *pending* enrollment
        (``CourseEnrollmentAllowed``) that becomes real once the person logs in
        via SSO. The old code only checked the status code, so pending/failed
        enrollments were silently reported as success — which is why "people
        were still not enrolled". Here the per-identifier ``before``/``after``
        states are parsed so each outcome is reported accurately.
        """
        if courses is None:
            courses = settings.ED_COURSES
        if header is None:
            header = Training._ed_authenticate_header()

        payload = {
            "auto_enroll": True,
            "email_students": False,
            "action": "enroll",
            "courses": ",".join(courses),
            "identifiers": user.email,
        }
        response = requests.post(
            f"{settings.ED_HOST}/api/bulk_enroll/v1/bulk_enroll",
            headers=header,
            json=payload,
        )

        results = []
        if response.status_code == 429 and not _retried:
            # EnrollmentUserThrottle — back off once then retry.
            sleep(120)
            return Training.enroll_user_ed(user, courses=courses, header=header, request=request, _retried=True)
        if response.status_code == 403:
            results.append(
                (
                    ",".join(courses),
                    "error",
                    f"{user} NOT enrolled: the Open edX API account is not global staff "
                    "(bulk-enroll requires is_staff=True on the ED_ID application owner).",
                )
            )
        elif response.status_code != 200:
            results.append(
                (
                    ",".join(courses),
                    "error",
                    f"{user} NOT enrolled, HTTP {response.status_code} {response.reason}.",
                )
            )
        else:
            body = response.json()
            course_results = body.get("courses") or {} if hasattr(body, "get") else {}
            for course_id in courses:
                course_block = course_results.get(course_id) or {}
                status, detail = Training._interpret_enroll_result(course_block.get("results") or [])
                results.append((course_id, status, f"{user}: {course_id}, {detail}"))

        for _course_id, status, message in results:
            level = messages.INFO if status in ("enrolled", "pending") else messages.ERROR
            logger.log(_log_level_for(level), message)
            if request is not None:
                messages.add_message(request, level, message)
        return results

    @staticmethod
    def add_user_ed(user, request=None):
        """Ensure ``user`` is enrolled in the configured Open edX course run(s).

        Thin wrapper around :meth:`enroll_user_ed`, kept for the admin action
        and other existing callers.
        """
        return Training.enroll_user_ed(user, request=request)

    @staticmethod
    def get_progress_all_users_ed(courses=None, header=None):
        """Sync training progress from Open edX (ed.thetatau.org) into ``Training``.

        For each configured course run this pages the Grades API
        (``GET /api/grades/v1/courses/{course_id}/``) and upserts one
        ``Training`` row per matched CMT user. The Grades API reports
        ``passed`` / ``percent`` for every enrolled account; only accounts that
        have actually logged in via SSO appear (a pending ``auto_enroll`` does
        not), so this records real progress only.

        The endpoint is JWT-authenticated and requires the ``ED_ID`` application
        owner to be Open edX global staff (same requirement as bulk-enroll).
        """
        if courses is None:
            courses = settings.ED_COURSES
        if header is None:
            header = Training._ed_authenticate_header()
        user_index = Training._ed_user_index()
        for course_id in courses:
            course_title = Training._ed_course_title(course_id, header)
            url = f"{settings.ED_HOST}/api/grades/v1/courses/{course_id}/"
            while url:
                response = requests.get(url, headers=header)
                if response.status_code == 429:
                    logger.warning("Delaying for rate limit Open edX grades sync...")
                    sleep(120)
                    continue
                if response.status_code != 200:
                    logger.error(
                        f"    Open edX grades sync error for {course_id}: "
                        f"HTTP {response.status_code} {response.reason}"
                    )
                    break
                body = response.json()
                for grade in body.get("results") or []:
                    Training._sync_ed_grade(course_id, course_title, grade, user_index)
                # CourseEnrollmentPagination is a CursorPagination: follow
                # ``next`` until it is null.
                url = body.get("next")

    @staticmethod
    def _ed_course_title(course_id, header):
        """Best-effort display name for a course run; falls back to the id."""
        try:
            response = requests.get(
                f"{settings.ED_HOST}/api/courses/v1/courses/{course_id}/",
                headers=header,
            )
            if response.status_code == 200:
                return response.json().get("name") or course_id
        except Exception:
            pass
        return course_id

    @staticmethod
    def _ed_normalize(value):
        """Lowercase, alphanumeric-only form used to match Open edX accounts.

        The SSO stores the Open edX ``username`` as the CMT ``name`` (which
        Open edX strips of spaces/punctuation), and the grades API blanks the
        email for non-masters enrollments, so matching is done on this
        normalised form of the CMT name/username/email fields.
        """
        return re.sub(r"[^a-z0-9]", "", (value or "").lower())

    @staticmethod
    def _ed_user_index():
        """Map ``normalised identifier -> CMT user id`` for account matching."""
        index = {}
        rows = User.objects.values_list("id", "name", "username", "email", "email_school")
        for uid, name, username, email, email_school in rows:
            for key in (name, username, email, email_school):
                norm = Training._ed_normalize(key)
                if norm:
                    index.setdefault(norm, uid)
        return index

    @staticmethod
    def _sync_ed_grade(course_id, course_title, grade, user_index):
        """Upsert one ``Training`` row from a single Grades API record."""
        username = grade.get("username")
        email = grade.get("email")
        user_id = user_index.get(Training._ed_normalize(username))
        if not user_id and email:
            user_id = user_index.get(Training._ed_normalize(email))
        if not user_id:
            logger.debug(f"    No CMT user match for Open edX account username={username!r} course={course_id}")
            return
        passed = bool(grade.get("passed"))
        percent = grade.get("percent") or 0
        existing = Training.objects.filter(user_id=user_id, course_id=course_id).order_by("-created").first()
        if passed:
            completed_time = existing.completed_time if existing and existing.completed_time else timezone.now()
        else:
            completed_time = None
        values = dict(
            progress_id="",
            course_title=course_title,
            completed=passed,
            completed_time=completed_time,
            max_quiz_score=round(float(percent) * 100, 2),
        )
        try:
            Training.objects.update_or_create(user_id=user_id, course_id=course_id, defaults=values)
        except Training.MultipleObjectsReturned:
            duplicates = Training.objects.filter(user_id=user_id, course_id=course_id).order_by("-created")
            for training in duplicates[1:]:
                training.delete()
            Training.objects.update_or_create(user_id=user_id, course_id=course_id, defaults=values)
