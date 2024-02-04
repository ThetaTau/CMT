from herald import registry
from herald.base import EmailNotification
from django.conf import settings
from django.http import HttpRequest
from django.utils.safestring import mark_safe
from django.core.files.base import ContentFile
from django.forms.models import model_to_dict
from core.models import current_term, current_year
from forms.tables import SignTable, BadgeTable
from forms.models import Badge
from users.models import User
from configs.models import Config


@registry.register_decorator()
class EmailRMPSigned(EmailNotification):  # extend from EmailNotification for emails
    template_name = "rmp_complete"  # name of template, without extension
    subject = "Risk Management Policies Signed"  # subject of email

    def __init__(self, user, file, file_name):
        self.to_emails = set([user.email])  # set list of emails to send to
        self.cc = ["cmt@thetatau.org"]
        self.reply_to = [
            "central.office@thetatau.org",
        ]
        self.context = {
            "user": user,
            "file_name": file_name,
            "host": settings.CURRENT_URL,
        }
        # https://github.com/worthwhile/django-herald#email-attachments
        self.attachments = [
            (file_name, file, "application/pdf"),
        ]

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from users.models import User
        from forms.views import RiskManagementDetailView
        from forms.models import RiskManagement
        from django.http import HttpRequest

        form = RiskManagement.objects.order_by("?")[0]
        view = RiskManagementDetailView.as_view()
        new_request = HttpRequest()
        test_user = User.objects.order_by("?")[0]
        new_request.user = test_user
        new_request.path = f"/forms/rmp-complete/{form.id}"
        new_request.method = "GET"
        risk_view = view(new_request, pk=form.id)
        risk_file = risk_view.content
        file_name = f"Risk Management Form {test_user}"
        return [test_user, risk_file, file_name]


@registry.register_decorator()
class EmailRMPReport(EmailNotification):  # extend from EmailNotification for emails
    template_name = "report"  # name of template, without extension
    subject = "[CMT] Theta Tau Report Submitted"  # subject of email

    def __init__(self, user, file):
        self.to_emails = set(["risk@thetatau.org"])  # set list of emails to send to
        self.cc = [user.email, "central.office@thetatau.org"]
        self.reply_to = [
            "central.office@thetatau.org",
        ]
        file_name = file.name
        chapter = user.current_chapter
        if not chapter.candidate_chapter:
            chapter_name = chapter.name + " Chapter"
        else:
            chapter_name = chapter.name
        self.subject = f"[CMT] {chapter_name} Theta Tau Report Submitted"
        self.context = {
            "user": user,
            "file_name": file_name,
            "host": settings.CURRENT_URL,
        }
        # https://github.com/worthwhile/django-herald#email-attachments
        file.seek(0)
        self.attachments = [
            (file_name, file.read(), file.mime_type),
        ]

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from users.models import User

        test_user = User.objects.order_by("?")[0]
        from django.core.files import File

        test_path = "thetatauCMT/forms/test/example_rmp.pdf"
        f = open(test_path, "rb")
        risk_file = File(f)
        risk_file.mime_type = "application/pdf"
        return [test_user, risk_file]


@registry.register_decorator()
class EmailAdvisorWelcome(
    EmailNotification
):  # extend from EmailNotification for emails
    template_name = "advisor"  # name of template, without extension
    subject = "Theta Tau Chapter Advisor"  # subject of email

    def __init__(self, user):
        self.to_emails = set([user.email])  # set list of emails to send to
        self.cc = ["central.office@thetatau.org"]
        self.reply_to = [
            "jim.gaffney@thetatau.org",
        ]
        chapter = user.current_chapter
        if not chapter.candidate_chapter:
            chapter_name = chapter.name + " Chapter"
        else:
            chapter_name = chapter.name
        self.subject = f"Theta Tau Chapter Advisor, {chapter_name}"
        self.context = {
            "user": user,
            "chapter_name": chapter_name,
            "school": chapter.school,
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from users.models import User

        test_user = User.objects.order_by("?")[0]
        return [test_user]


@registry.register_decorator()
class EmailPledgeOther(EmailNotification):  # extend from EmailNotification for emails
    template_name = "pledge_other"  # name of template, without extension
    subject = "[CMT] Other Pledge Program"  # subject of email

    def __init__(self, user, file):
        self.to_emails = set(["risk@thetatau.org"])  # set list of emails to send to
        self.cc = ["central.office@thetatau.org"]
        self.reply_to = [
            user.email,
        ]
        file_name = file.name
        self.context = {
            "user": user,
            "file_name": file_name,
            "host": settings.CURRENT_URL,
        }
        # https://github.com/worthwhile/django-herald#email-attachments
        self.attachments = [
            (file_name, file.read(), file.mime_type),
        ]

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from users.models import User

        test_user = User.objects.order_by("?")[0]
        from django.core.files import File

        test_path = "thetatauCMT/forms/test/example_rmp.pdf"
        f = open(test_path, "rb")
        risk_file = File(f)
        risk_file.mime_type = "application/pdf"
        return [test_user, risk_file]


@registry.register_decorator()
class EmailPledgeConfirmation(
    EmailNotification
):  # extend from EmailNotification for emails
    template_name = "pledge"  # name of template, without extension
    subject = "Theta Tau Prospective New Member Confirmation"  # subject of email

    def __init__(self, pledge_form, bill_file):
        self.to_emails = {pledge_form.user.email_school, pledge_form.user.email}
        self.reply_to = [
            "central.office@thetatau.org",
        ]
        pledge_dict = model_to_dict(pledge_form)
        model_dict = model_to_dict(pledge_form.user)
        model_dict.update(pledge_dict)
        for remove_item in [
            "user",
            "password",
            "badge_number",
            "id",
            "last_login",
            "is_staff",
            "is_active",
            "date_joined",
            "is_superuser",
            "employer",
            "employer_position",
            "groups",
            "user_permissions",
            "no_contact",
            "deceased",
            "deceased_changed",
            "deceased_date",
            "address_changed",
            "employer_changed",
            "employer_address",
            "emergency_first_name",
            "emergency_middle_name",
            "emergency_last_name",
            "emergency_nickname",
            "emergency_phone_number",
            "emergency_relation",
        ]:
            if remove_item in model_dict:
                del model_dict[remove_item]
        form_dict = {}
        for key, value in model_dict.items():
            if hasattr(pledge_form, f"verbose_{key}"):
                value = {True: "Yes", False: "No"}[value]
                form_dict[getattr(pledge_form, f"verbose_{key}")] = value
            else:
                if (
                    key.startswith("explain_") or key.startswith("other_")
                ) and value == "":
                    continue
                if key not in ["id", "address", "major", "chapter"]:
                    form_dict[key.replace("_", " ").title()] = value
                elif key == "address":
                    form_dict["Address"] = getattr(pledge_form.user, key).formatted
                elif key == "major":
                    form_dict["Major"] = pledge_form.user.major.major
                elif key == "chapter":
                    form_dict["Chapter"] = pledge_form.user.chapter.name
                    form_dict["School"] = pledge_form.user.chapter.school

        self.context = {
            "form": form_dict,
            "host": settings.CURRENT_URL,
        }
        file_name = "Potential New Member Bill of Rights.pdf"
        self.attachments = [
            (file_name, bill_file, "application/pdf"),
        ]

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from forms.models import Pledge
        from forms.views import BillOfRightsPDFView
        from django.http import HttpRequest

        test_pledge_form = Pledge.objects.order_by("?")[0]
        new_request = HttpRequest()
        new_request.method = "GET"
        view = BillOfRightsPDFView.as_view()
        bill_view = view(new_request, pk=test_pledge_form.user.chapter.id)
        bill_file = bill_view.content
        return [test_pledge_form, bill_file]


@registry.register_decorator()
class EmailPledgeWelcome(EmailNotification):  # extend from EmailNotification for emails
    template_name = "pledge_welcome"  # name of template, without extension
    subject = "Theta Tau Welcome Prospective New Member"  # subject of email
    render_types = ["html"]

    def __init__(self, pledge_form):
        user = pledge_form.user
        name = user.first_name
        email_school = user.email_school
        email_personal = user.email
        chapter = user.chapter
        school_type = chapter.school_type
        no_later_month = {
            "sp_semester": "March 15",
            "sp_quarter": "May 15",
            "fa_semester": "October 15",
            "fa_quarter": "November 15",
        }[f"{current_term()}_{school_type}"]
        self.to_emails = set([email_school])  # set list of emails to send to
        if email_school != email_personal:
            self.cc = [email_personal]
        self.reply_to = [
            "central.office@thetatau.org",
        ]
        welcome = Config.get_value("PledgeWelcome", clean=False)
        self.context = {
            "name": name,
            "welcome": welcome,
            "no_later_date": f"{no_later_month}, {current_year()}",
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from forms.models import Pledge

        test_pledge_form = Pledge.objects.order_by("?")[0]
        return [test_pledge_form]


@registry.register_decorator()
class BadgePNMNotify(EmailNotification):  # extend from EmailNotification for emails
    render_types = ["html"]
    template_name = "badge_pnm_notify"  # name of template, without extension
    subject = "Theta Tau Badge Explainer"  # subject of email

    def __init__(self, user):  # optionally customize the initialization
        emails = {email for email in user.emails if email}
        self.to_emails = emails
        emails = user.chapter.get_email_specific(["vice regent", "treasurer"])
        self.cc = list(emails)
        self.reply_to = [
            "central.office@thetatau.org",
        ]
        message = Config.get_value("badge_pnm_notify", clean=False)
        badges = BadgeTable(
            Badge.objects.exclude(name__icontains="candidate").order_by("cost")
        )
        request = HttpRequest()
        badge_table = badges.as_html(request)
        message = message.replace("{{ badge_table }}", badge_table)
        self.context = {
            "message": mark_safe(message),
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from forms.models import Pledge

        test_pledge = Pledge.objects.order_by("?")[0]
        return [test_pledge]


@registry.register_decorator()
class EmailPledgeOfficer(EmailNotification):
    render_types = ["html"]
    template_name = "pledge_officer"
    subject = "Theta Tau Prospective New Member Submission"

    def __init__(self, pledge_form):
        (
            _,
            scribe,
            vice,
            _,
            _,
        ) = pledge_form.user.chapter.get_current_officers_council_specific()
        generics = pledge_form.user.chapter.get_generic_chapter_emails()
        emails = set()
        if scribe:
            emails.add(scribe.email)
        if vice:
            emails.add(vice.email)
        if generics[1]:  # Scribe
            emails.add(generics[1])
        if generics[2]:  # Vice
            emails.add(generics[2])
        self.to_emails = emails
        self.cc = [
            pledge_form.user.email_school,
        ]
        self.reply_to = [
            "central.office@thetatau.org",
        ]
        self.context = {
            "pledge": pledge_form.user.first_name + " " + pledge_form.user.last_name,
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from forms.models import Pledge

        test_pledge_form = Pledge.objects.order_by("?")[0]
        return [test_pledge_form]


@registry.register_decorator()
class EmailProcessUpdate(EmailNotification):
    render_types = ["html"]
    template_name = "process"

    def __init__(
        self,
        model_obj,
        complete_step,
        next_step,
        state,
        message,
        fields,
        *,  # This requires all following parameters to be keyword args
        process_title="Process Update",
        email_officers=False,
        attachments=None,
        extra_emails=None,
        direct_user=None,
    ):
        emails = set()
        user = direct_user
        obj = None
        if hasattr(model_obj, "process") and hasattr(model_obj, "flow_class"):
            process_title = model_obj.flow_class.process_title
            model_obj = model_obj.process
        if hasattr(model_obj, "chapter"):
            chapter = model_obj.chapter
        else:
            chapter = model_obj.user.chapter
        if direct_user:
            obj = direct_user.chapter
        if direct_user is None:
            if hasattr(model_obj, "user"):
                user = model_obj.user
                obj = user
            else:
                user = model_obj.created_by
                obj = chapter
                email_officers = True
        if email_officers:
            officers = chapter.get_current_officers_council_specific()
            if user is None:
                for ind, officer in enumerate(officers):
                    if officer:
                        user = officers.pop(ind)
                        break
                else:
                    # No officers
                    process_title = "NO OFFICERS"
                    message = "THIS CHAPTER HAS NO OFFICERS, PLEASE REACH OUT TO THE CHAPTER ASAP TO FIX THIS!"
                    emails.add(chapter.region.email)
                    user = User.objects.get(username="Jim.Gaffney@thetatau.org")
            emails = chapter.council_emails()
            if user and user.email in emails:
                emails.remove(user.email)
        if extra_emails:
            emails = emails | set(extra_emails)
        if user is None:
            process_title = "NO OFFICERS"
            message = "THIS CHAPTER HAS NO OFFICERS, PLEASE REACH OUT TO THE CHAPTER ASAP TO FIX THIS!"
            user = User.objects.get(username="Jim.Gaffney@thetatau.org")
            emails.add(chapter.region.email)
        self.to_emails = {user.email}  # set list of emails to send to
        self.cc = list(set({"central.office@thetatau.org"} | emails))
        self.reply_to = [
            "central.office@thetatau.org",
        ]
        self.subject = f"[CMT] {process_title} {state} for {obj}"
        info = {}
        for field in fields:
            if isinstance(field, dict):
                info.update(field)
                continue
            field_obj = model_obj._meta.get_field(field)
            if field == "user":
                info[field_obj.verbose_name] = model_obj.user
                continue
            try:
                info[field_obj.verbose_name] = model_obj._get_FIELD_display(field_obj)
            except TypeError:
                info[field_obj.verbose_name] = field_obj.value_to_string(model_obj)
        files = []
        if hasattr(model_obj, "form"):
            file = model_obj.form
            files.append(file)
        if attachments:
            for attachment in attachments:
                model_obj_orig = None
                if "." in attachment:
                    sub_obj, attachment = attachment.split(".")
                    model_obj_orig = model_obj
                    model_obj = getattr(model_obj, sub_obj)
                file = getattr(model_obj, attachment)
                if model_obj_orig is not None:
                    model_obj = model_obj_orig
                if file.name:
                    files.append(file)
        file_names = [file.name for file in files]
        self.context = {
            "user": user,
            "obj": obj,
            "file_names": file_names,
            "complete_step": complete_step,
            "next_step": next_step,
            "info": info,
            "process_title": process_title,
            "host": settings.CURRENT_URL,
            "message": message,
            "state": state,
        }
        # https://github.com/worthwhile/django-herald#email-attachments
        self.attachments = []
        for file in files:
            file.seek(0)
            self.attachments.append(
                (file.name, file.read(), None),
            )

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from forms.models import InitiationProcess

        # test = PrematureAlumnus.objects.order_by('?')[0]
        test = InitiationProcess.objects.order_by("?")[0]
        member_list = "Test, blue, green, red, orange, purple"
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
        return [
            test,
            "Badge/Shingles Order Submitted",
            "Initiation Process Complete",
            "Badges/Shingles Ordered",
            "Your chapter has paid an initiation invoice.",
            [
                {"members": member_list},
                "invoice",
            ],
        ]


@registry.register_decorator()
class EmailConventionUpdate(EmailNotification):
    render_types = ["html"]
    template_name = "convention"

    def __init__(self, activation, user, message):
        from forms.views import get_sign_status

        data, _, _ = get_sign_status(user, initial=True)
        table = SignTable(data=data)
        process_title = activation.flow_class.process_title
        self.to_emails = set([user.email])  # set list of emails to send to
        self.reply_to = [
            "central.office@thetatau.org",
        ]
        self.subject = f"[CMT] {process_title}"
        self.context = {
            "user": user,
            "message": message,
            "process_title": process_title,
            "table": table,
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from forms.models import Convention

        test = Convention.objects.order_by("?")[0]
        test.process = test
        return [
            test,
            test.delegate,
            "Convention Form Submitted",
        ]


@registry.register_decorator()
class EmailOSMUpdate(EmailNotification):
    render_types = ["html"]
    template_name = "osm"

    def __init__(self, activation, user, message, nominate=None):
        officer = True
        if nominate is None:
            officer = False
        process_title = activation.flow_class.process_title
        self.to_emails = {user.email}
        self.reply_to = [
            "central.office@thetatau.org",
        ]
        self.subject = f"[CMT] {process_title}"
        self.context = {
            "user": user,
            "message": message,
            "officer": officer,
            "nominate": nominate,
            "process_title": "Outstanding Student Member Process",
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():
        from forms.models import OSM

        test = OSM.objects.order_by("?")[0]
        test.process = test
        # return [test, test.officer1,
        #         "Outstanding Student Member Form Submission", test.nominate]
        return [test, test.nominate, "Outstanding Student Member Nomination"]


@registry.register_decorator()
class CentralOfficeGenericEmail(EmailNotification):
    render_types = ["html"]
    template_name = "central_office"

    def __init__(self, message, subject="[CMT] Record Message", attachments=None):
        self.to_emails = ["central.office@thetatau.org"]
        self.cc = ["cmt@thetatau.org"]
        self.reply_to = ["cmt@thetatau.org"]
        self.subject = subject
        file_names = []
        if attachments:
            for file in attachments:
                if hasattr(file, "name"):
                    file_names.append(file.name)
                elif hasattr(file, "get_filename"):
                    file_names.append(file.get_filename())
        else:
            attachments = []
        self.context = {
            "file_names": file_names,
            "host": settings.CURRENT_URL,
            "message": message,
        }
        # https://github.com/worthwhile/django-herald#email-attachments
        self.attachments = []
        for file in attachments:
            if hasattr(file, "seek"):
                file.seek(0)
                self.attachments.append(
                    (file.name, file.read(), None),
                )
            elif hasattr(file, "get_content_type"):
                self.attachments.append(file)

    @staticmethod
    def get_demo_args():
        from forms.flows import render_to_pdf

        info = {"Test": "This is a test"}
        forms = render_to_pdf(
            "forms/disciplinary_form_pdf.html",
            context={"info": info},
        )

        return ["This is a test message", [ContentFile(forms, name="Testfile.pdf")]]
