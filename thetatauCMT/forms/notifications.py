from herald import registry
from herald.base import EmailNotification
from django.conf import settings


@registry.register_decorator()
class EmailRMPSigned(EmailNotification):  # extend from EmailNotification for emails
    template_name = 'rmp_complete'  # name of template, without extension
    subject = 'Risk Management Policies Signed'  # subject of email

    def __init__(self, user, file, file_name):
        self.to_emails = set([user.email])  # set list of emails to send to
        self.cc = ["cmt@thetatau.org"]
        self.reply_to = ["cmt@thetatau.org", ]
        self.context = {
            'user': user,
            'file_name': file_name,
            'host': settings.CURRENT_URL,
        }
        # https://github.com/worthwhile/django-herald#email-attachments
        self.attachments = [
            (file_name, file, 'application/pdf'),
        ]

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from users.models import User
        from forms.views import RiskManagementDetailView
        from forms.models import RiskManagement
        from django.http import HttpRequest
        form = RiskManagement.objects.order_by('?')[0]
        view = RiskManagementDetailView.as_view()
        new_request = HttpRequest()
        test_user = User.objects.order_by('?')[0]
        new_request.user = test_user
        new_request.path = f'/forms/rmp-complete/{form.id}'
        new_request.method = 'GET'
        risk_view = view(new_request, pk=form.id)
        risk_file = risk_view.content
        file_name = f"Risk Management Form {test_user}"
        return [test_user, risk_file, file_name]
