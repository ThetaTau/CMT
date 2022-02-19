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
        emails = set(user.emailaddress_set.values_list("email", flat=True))
        self.to_emails = emails
        self.cc = []
        self.reply_to = [
            "cmt@thetatau.org",
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
