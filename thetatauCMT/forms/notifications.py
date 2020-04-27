from herald import registry
from herald.base import EmailNotification
from django.conf import settings
from django.forms.models import model_to_dict
from core.models import current_term, current_year
from forms.tables import ConventionTable


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
        file.seek(0)
        self.attachments = [
            (file_name, file.read(), file.mime_type),
        ]

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from users.models import User
        test_user = User.objects.order_by('?')[0]
        from django.core.files import File
        test_path = 'thetatauCMT/forms/test/example_rmp.pdf'
        f = open(test_path, 'rb')
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
            'host': settings.CURRENT_URL,
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
        f = open(test_path, 'rb')
        risk_file = File(f)
        risk_file.mime_type = 'application/pdf'
        return [test_user, risk_file]


@registry.register_decorator()
class EmailPledgeConfirmation(EmailNotification):  # extend from EmailNotification for emails
    template_name = 'pledge'  # name of template, without extension
    subject = 'Theta Tau Prospective New Member Confirmation'  # subject of email

    def __init__(self, pledge_form):
        self.to_emails = set([pledge_form.email_school])  # set list of emails to send to
        if pledge_form.email_school != pledge_form.email_personal:
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
            'host': settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from forms.models import Pledge
        test_pledge_form = Pledge.objects.order_by('?')[0]
        return [test_pledge_form]


@registry.register_decorator()
class EmailPledgeWelcome(EmailNotification):  # extend from EmailNotification for emails
    template_name = 'pledge_welcome'  # name of template, without extension
    subject = 'Theta Tau Welcome Prospective New Member'  # subject of email

    def __init__(self, pledge_form):
        name = pledge_form.first_name
        email_school = pledge_form.email_school
        email_personal = pledge_form.email_personal
        chapter = pledge_form.school_name
        school_type = chapter.school_type
        no_later_month = {
            'sp_semester': 'March 15',
            'sp_quarter': 'May 15',
            'fa_semester': 'October 15',
            'fa_quarter': 'November 15',
        }[f'{current_term()}_{school_type}']
        self.to_emails = set([email_school])  # set list of emails to send to
        if email_school != email_personal:
            self.cc = [email_personal]
        self.reply_to = ["central.office@thetatau.org", ]
        self.context = {
            'name': name,
            'no_later_date': f"{no_later_month}, {current_year()}",
            'host': settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from forms.models import Pledge
        test_pledge_form = Pledge.objects.order_by('?')[0]
        return [test_pledge_form]


@registry.register_decorator()
class EmailPledgeOfficer(EmailNotification):
    render_types = ['html']
    template_name = 'pledge_officer'
    subject = 'Theta Tau Prospective New Member Submission'

    def __init__(self, pledge_form):
        officers = pledge_form.school_name.get_current_officers_council(combine=False)[0]
        scribe = officers.filter(role='scribe').first()
        vice = officers.filter(role='vice regent').first()
        emails = set()
        if scribe:
            emails.add(scribe.email)
        if vice:
            emails.add(vice.email)
        self.to_emails = emails
        self.cc = [pledge_form.email_school, ]
        self.reply_to = ["cmt@thetatau.org", ]
        self.context = {
            'pledge': pledge_form.first_name + ' ' + pledge_form.last_name,
            'host': settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from forms.models import Pledge
        test_pledge_form = Pledge.objects.order_by('?')[0]
        return [test_pledge_form]


@registry.register_decorator()
class EmailProcessUpdate(EmailNotification):
    render_types = ['html']
    template_name = 'process'

    def __init__(self, activation, complete_step, next_step, state, message, fields):
        if hasattr(activation.process, 'user'):
            user = activation.process.user
            obj = user
            emails = set()
        else:
            user = activation.process.created_by
            obj = activation.process.chapter
            officers, _ = activation.process.chapter.get_current_officers_council(combine=False)
            emails = set([officer.email for officer in officers])
            if user.email in emails:
                emails.remove(user.email)
        file = False
        file_name = None
        if hasattr(activation.process, 'form'):
            file = activation.process.form
            file_name = file.name
        process_title = activation.flow_class.process_title
        self.to_emails = {user.email}  # set list of emails to send to
        self.cc = list({"cmt@thetatau.org", 'central.office@thetatau.org'} | emails)
        self.reply_to = ["cmt@thetatau.org", ]
        self.subject = f'[CMT] {process_title} {state} for {obj}'
        info = {}
        for field in fields:
            if isinstance(field, dict):
                info.update(field)
                continue
            key = activation.process._meta.get_field(field).verbose_name
            value = getattr(activation.process, field, '')
            if activation.process._meta.get_field(field).choices:
                value = activation.process.TYPES.get_value(value)
            info[key] = value
        self.context = {
            'user': user,
            'obj': obj,
            'file_name': file_name,
            'complete_step': complete_step,
            'next_step': next_step,
            'info': info,
            'process_title': process_title,
            'host': settings.CURRENT_URL,
            'message': message,
            'state': state,
        }
        # https://github.com/worthwhile/django-herald#email-attachments
        if file:
            file.seek(0)
            self.attachments = [
                (file_name, file.read(), None),
            ]

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from forms.models import PrematureAlumnus
        from forms.models import InitiationProcess
        # test = PrematureAlumnus.objects.order_by('?')[0]
        test = InitiationProcess.objects.order_by('?')[0]
        member_list = 'Test, blue, green, red, orange, purple'
        test.process = test
        # return [test, "Premature Alumnus Request", "Executive Director Review",
        #         "Submitted", "This is the test message",
        #         ['good_standing', 'financial', 'semesters', 'lifestyle',
        #          'consideration', 'prealumn_type', 'vote', 'approved_exec',
        #          'exec_comments', ]]
        # return [test, "Initiation Report Submitted",
        #         "Central Office Processing & Invoice Generation",
        #         "Submitted",
        #         "Your chapter has submitted an initiation report." +
        #         " Once the Central Office processes the report, an invoice will be generated" +
        #         " and will be sent to your chapter on the last business day of this month.",
        #         [{'members': member_list}, ]]
        # return [test, "Initiation Invoice Paid",
        #         "Central Office Badge/Shingle Order",
        #         "Payment Received",
        #         "Your chapter has paid an initiation invoice." +
        #         " Once the Central Office processes the payment, an order will be sent" +
        #         " to the jeweler/shingler.",
        #         [{'members': member_list}, 'invoice', ]]
        return [test, "Badge/Shingles Order Submitted",
                "Initiation Process Complete",
                "Badges/Shingles Ordered",
                "A badges and shingles order has been sent to the vendor.",
                [{'members': member_list}, 'invoice', ]]


@registry.register_decorator()
class EmailConventionUpdate(EmailNotification):
    render_types = ['html']
    template_name = 'convention'

    def __init__(self, activation, user, message):
        from forms.views import get_credential_status
        data, _, _ = get_credential_status(user)
        table = ConventionTable(data=data)
        process_title = activation.flow_class.process_title
        self.to_emails = set([user.email])  # set list of emails to send to
        self.reply_to = ["cmt@thetatau.org", ]
        self.subject = f'[CMT] {process_title}'
        self.context = {
            'user': user,
            'message': message,
            'process_title': process_title,
            'table': table,
            'host': settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from forms.models import Convention
        test = Convention.objects.order_by('?')[0]
        test.process = test
        return [test, test.delegate, "Convention Form Submitted",]

