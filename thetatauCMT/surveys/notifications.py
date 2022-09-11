from herald import registry
from herald.base import EmailNotification
from django.conf import settings


@registry.register_decorator()
class DepledgeSurveyEmail(
    EmailNotification
):  # extend from EmailNotification for emails
    render_types = ["html"]
    template_name = "depledge_survey"  # name of template, without extension
    subject = "Theta Tau PNM Exit Survey"  # subject of email

    def __init__(self, user):
        emails = set(user.emailaddress_set.values_list("email", flat=True)) | {
            user.email,
            user.email_school,
        }
        self.to_emails = emails
        self.cc = []
        self.reply_to = [
            "central.office@thetatau.org",
        ]
        self.context = {
            "user": user,
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from forms.models import Depledge

        user = Depledge.objects.order_by("?")[0].user
        return [
            user,
        ]


@registry.register_decorator()
class DepledgeSurveyFollowUpEmail(EmailNotification):
    render_types = ["html"]
    template_name = "depledge_followup"

    def __init__(self, id, message):
        self.to_emails = ["Jennifer.Kreiman@thetatau.org"]
        self.reply_to = ["Jim.Gaffney@thetatau.org"]
        self.subject = f"[CMT] Depledge Follow Up: {id}"
        self.context = {
            "host": settings.CURRENT_URL,
            "message": message,
        }

    @staticmethod
    def get_demo_args():
        from .models import DepledgeSurvey
        from django.urls import reverse
        from django.utils.safestring import mark_safe

        survey = DepledgeSurvey.objects.order_by("?")[0]
        user = survey.user
        link = reverse(
            "admin:surveys_depledgesurvey_change", kwargs={"object_id": survey.id}
        )
        message = mark_safe(
            f"A depledge from {user.chapter.full_name} has asked "
            f"for a follow up to their survey. <br>"
            f'<a href="{settings.CURRENT_URL}{link}">See link here.</a>'
        )
        return [user.id, message]


@registry.register_decorator()
class SurveyEmail(EmailNotification):  # extend from EmailNotification for emails
    render_types = ["html"]
    template_name = "survey"  # name of template, without extension
    subject = "Theta Tau Survey"  # subject of email

    def __init__(self, user, survey_name, survey_link, message):
        emails = set(user.emailaddress_set.values_list("email", flat=True)) | {
            user.email,
            user.email_school,
        }
        self.subject = f"Theta Tau {survey_name} Survey"
        self.to_emails = emails
        self.cc = []
        self.reply_to = [
            "central.office@thetatau.org",
        ]
        self.context = {
            "user": user,
            "host": settings.CURRENT_URL,
            "survey_link": survey_link,
            "subject": self.subject,
            "message": message,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from django.urls import reverse
        from users.models import User

        test_user = User.objects.order_by("?")[0]

        survey_link = settings.CURRENT_URL + reverse(
            "surveys:survey-detail", kwargs={"slug": "graduation-survey"}
        )
        return [test_user, "Graduation", survey_link, "Please fill out the following"]
