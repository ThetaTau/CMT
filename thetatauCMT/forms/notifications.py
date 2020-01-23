from herald import registry
from herald.base import EmailNotification
from django.conf import settings
from django.forms.models import model_to_dict


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


@registry.register_decorator()
class EmailRMPReport(EmailNotification):  # extend from EmailNotification for emails
    template_name = 'report'  # name of template, without extension
    subject = '[CMT] Theta Tau Report Submitted'  # subject of email

    def __init__(self, user, file):
        self.to_emails = set(['risk@thetatau.org'])  # set list of emails to send to
        self.cc = ["cmt@thetatau.org", user.email, 'central.office@thetatau.org']
        self.reply_to = ["cmt@thetatau.org", ]
        file_name = file.name
        chapter = user.current_chapter
        if 'colony' not in chapter.name.lower():
            chapter_name = chapter.name + " Chapter"
        else:
            chapter_name = chapter.name
        self.subject = f'[CMT] {chapter_name} Theta Tau Report Submitted'
        self.context = {
            'user': user,
            'file_name': file_name,
            'host': settings.CURRENT_URL,
        }
        # https://github.com/worthwhile/django-herald#email-attachments
        self.attachments = [
            (file_name, file.read(), file.mime_type),
        ]

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from users.models import User
        test_user = User.objects.order_by('?')[0]
        from django.core.files import File
        test_path = 'thetatauCMT/forms/test/example_rmp.pdf'
        f = open(test_path, 'r')
        risk_file = File(f)
        risk_file.mime_type = 'application/pdf'
        return [test_user, risk_file]


@registry.register_decorator()
class EmailAdvisorWelcome(EmailNotification):  # extend from EmailNotification for emails
    template_name = 'advisor'  # name of template, without extension
    subject = 'Theta Tau Chapter Advisor'  # subject of email

    def __init__(self, user):
        self.to_emails = set([user.email])  # set list of emails to send to
        self.cc = ['central.office@thetatau.org']
        self.reply_to = ["jim.gaffney@thetatau.org", ]
        chapter = user.current_chapter
        if 'colony' not in chapter.name.lower():
            chapter_name = chapter.name + " Chapter"
        else:
            chapter_name = chapter.name
        self.subject = f'Theta Tau Chapter Advisor, {chapter_name}'
        self.context = {
            'user': user,
            'chapter_name': chapter_name,
            'school': chapter.school,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from users.models import User
        test_user = User.objects.order_by('?')[0]
        return [test_user]


@registry.register_decorator()
class EmailPledgeOther(EmailNotification):  # extend from EmailNotification for emails
    template_name = 'pledge_other'  # name of template, without extension
    subject = '[CMT] Other Pledge Program'  # subject of email

    def __init__(self, user, file):
        self.to_emails = set(['risk@thetatau.org'])  # set list of emails to send to
        self.cc = ["cmt@thetatau.org"]
        self.reply_to = ["cmt@thetatau.org", ]
        file_name = file.name
        self.context = {
            'user': user,
            'file_name': file_name,
            'host': settings.CURRENT_URL,
        }
        # https://github.com/worthwhile/django-herald#email-attachments
        self.attachments = [
            (file_name, file.read(), file.mime_type),
        ]

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from users.models import User
        test_user = User.objects.order_by('?')[0]
        from django.core.files import File
        test_path = 'thetatauCMT/forms/test/example_rmp.pdf'
        f = open(test_path, 'r')
        risk_file = File(f)
        risk_file.mime_type = 'application/pdf'
        return [test_user, risk_file]


@registry.register_decorator()
class EmailPledgeConfirmation(EmailNotification):  # extend from EmailNotification for emails
    template_name = 'pledge'  # name of template, without extension
    subject = 'Theta Tau Pledge Form'  # subject of email

    def __init__(self, pledge_form):
        self.to_emails = set([pledge_form.email_school])  # set list of emails to send to
        self.cc = [pledge_form.email_personal]
        self.reply_to = ["cmt@thetatau.org", ]
        model_dict = model_to_dict(pledge_form)
        form_dict = {}
        for key, value in model_dict.items():
            if hasattr(pledge_form, f"verbose_{key}"):
                value = {True: 'Yes', False: 'No'}[value]
                form_dict[getattr(pledge_form, f"verbose_{key}")] = value
            else:
                if (key.startswith('explain_') or key.startswith('other_')) and value == "":
                    continue
                if key not in ['id', 'address']:
                    form_dict[key.replace('_', ' ').title()] = value
                elif key == 'address':
                    form_dict["Address"] = getattr(pledge_form, key).formatted
        self.context = {
            'form': form_dict,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from forms.models import Pledge
        test_pledge_form = Pledge.objects.order_by('?')[0]
        return [test_pledge_form]
