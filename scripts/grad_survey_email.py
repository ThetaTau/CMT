import base64
from datetime import datetime
from django.conf import settings
from django.urls import reverse
from forms.models import StatusChange
from configs.models import Config
from surveys.notifications import SurveyEmail


def run():
    """
    python manage.py runscript grad_survey_email
    """
    grads = StatusChange.objects.filter(
        reason__in=["graduate"], date_start__gt=datetime(2022, 3, 1)
    )
    total = grads.count()
    slug = Config.get_value("GraduationSurvey")
    for count, grad in enumerate(grads):
        user = grad.user
        print(f"{count + 1}/{total} for user: {user}")
        if not slug:
            continue
        if "http" in slug:
            survey_link = slug
        else:
            user_id = base64.b64encode(user.user_id.encode("utf-8")).decode("utf-8")
            survey_link = settings.CURRENT_URL + reverse(
                "surveys:survey-detail-member",
                kwargs={"slug": slug, "user_id": user_id},
            )
        SurveyEmail(
            user,
            "Graduation",
            survey_link,
            "Congratulations on your graduation!  "
            "We'd like to get your thoughts on your Theta Tau experience "
            "so that we can make the Fraternity better for everybody.",
        ).send()
