from herald import registry
from herald.base import EmailNotification
from tasks.models import TaskDate
from django.conf import settings
from django.shortcuts import reverse
from users.models import User
from chapters.models import Chapter
from chapters.tables import ChapterStatusTable


@registry.register_decorator()
class MemberInfoUpdate(EmailNotification):  # extend from EmailNotification for emails
    render_types = ["html"]
    template_name = "member_info_update"  # name of template, without extension
    subject = "[CMT] RMP & Update Member Information"  # subject of email

    def __init__(self, user, updater):
        emails = set(user.emailaddress_set.values_list("email", flat=True)) | {
            user.email,
            user.email_school,
        }
        self.to_emails = emails
        self.cc = []
        self.reply_to = [
            "cmt@thetatau.org",
        ]
        password = True
        if not user.has_usable_password() or not user.password:
            # Need link to generate password
            password = False
        self.context = {
            "user": user,
            "updater": updater,
            "password": password,
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        user = User.objects.order_by("?")[0]
        updater = User.objects.order_by("?")[0]
        return [user, updater]


@registry.register_decorator()
class OfficerMonthly(EmailNotification):  # extend from EmailNotification for emails
    template_name = "officer_monthly"  # name of template, without extension
    subject = "CMT Monthly Update"  # subject of email

    def __init__(self, chapter):  # optionally customize the initialization
        self.context = {"user": chapter}  # set context for the template rendering
        officer_list, previous = chapter.get_current_officers_council()
        # set list of emails to send to
        emails = chapter.council_emails()
        self.to_emails = emails
        self.cc = []
        self.reply_to = [
            "cmt@thetatau.org",
        ]
        if not chapter.candidate_chapter:
            chapter_name = chapter.name + " Chapter"
        else:
            chapter_name = chapter.name
        self.subject = f"CMT Monthly Update {chapter_name}"
        self.context = {
            "previous_officers": previous,
            "chapter": chapter_name,
            "last_month_events": chapter.events_last_month().count(),
            "semester_events": chapter.events_semester().count(),
            "count_members": chapter.actives().count(),
            "count_pledges": chapter.pledges().count(),
            "balance": chapter.balance,
            "balance_date": chapter.balance_date,
            "tasks_upcoming": TaskDate.incomplete_dates_for_chapter_next_month(chapter),
            "tasks_overdue": TaskDate.incomplete_dates_for_chapter(chapter),
            "region_announcements": None,
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        return [Chapter.objects.order_by("?")[0]]


@registry.register_decorator()
class RDMonthly(EmailNotification):  # extend from EmailNotification for emails
    template_name = "rd_monthly"  # name of template, without extension
    subject = "CMT Monthly Update Region Summary"  # subject of email
    render_types = ["html"]

    def __init__(self, region):  # optionally customize the initialization
        # Chapter, Members, Pledges, Events Last Month, Submissions Last Month, Current Balance, Tasks Overdue
        # List of tasks due next 45 days
        if region == "candidate_chapter":
            email = "ccd@thetatau.org"
            chapters = Chapter.objects.filter(candidate_chapter=True)
        else:
            email = region.email
            chapters = region.chapters.all()
        self.to_emails = {email}
        self.cc = []
        self.reply_to = [
            "cmt@thetatau.org",
        ]
        data = []
        for chapter in chapters:
            if not chapter.active:
                continue
            officers = chapter.get_current_officers_council_specific()
            officer_order = {
                0: "Regent",
                1: "Scribe",
                2: "Vice",
                3: "Treasurer",
                4: "Corresponding Secretary",
            }
            missing = ", ".join(
                [
                    officer_order[ind]
                    for ind, officer in enumerate(officers)
                    if officer is None
                ]
            )
            host = settings.CURRENT_URL
            link = reverse("chapters:detail", kwargs={"slug": chapter.slug})
            link = host + link
            data.append(
                {
                    "name": chapter.name,
                    "slug": chapter.slug,
                    "link": link,
                    "balance": chapter.balance,
                    "balance_date": chapter.balance_date,
                    "officer_missing": missing,
                    "member_count": chapter.actives().count(),
                    "pledge_count": chapter.pledges().count(),
                    "event_count": chapter.events_last_month().count(),
                    "tasks_overdue": TaskDate.incomplete_dates_for_chapter(
                        chapter
                    ).count(),
                    "host": host,
                }
            )
        table = ChapterStatusTable(data=data)
        self.context = {
            "region": region,
            "table": table,
            "tasks_upcoming": TaskDate.dates_for_next_month(),
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        # return ["colony"]
        return [Chapter.objects.order_by("?")[0].region]


@registry.register_decorator()
class NewOfficers(EmailNotification):  # extend from EmailNotification for emails
    template_name = "officer_new"  # name of template, without extension
    subject = "Welcome New Theta Tau Officers"  # subject of email

    def __init__(self, new_officers):  # optionally customize the initialization
        self.to_emails = set(
            [officer.email for officer in new_officers]
        )  # set list of emails to send to
        self.reply_to = [
            "cmt@thetatau.org",
        ]
        chapter = new_officers[0].current_chapter
        self.context = {
            "chapter": chapter,
            "region_facebook": chapter.region.facebook,
            "region_web": chapter.region.website,
            "director_emails": chapter.region.email,
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from users.models import User

        return [
            [
                User.objects.order_by("?")[0],
                User.objects.order_by("?")[0],
                User.objects.order_by("?")[0],
            ]
        ]


@registry.register_decorator()
class OfficerUpdateReminder(
    EmailNotification
):  # extend from EmailNotification for emails
    render_types = ["html"]
    template_name = "officer_update_reminder"  # name of template, without extension
    subject = "Officer update reminder"  # subject of email

    def __init__(
        self, chapter, emails, officers_to_update
    ):  # optionally customize the initialization
        emails = {email for email in emails if email}
        format_officers = ", ".join(officers_to_update)
        self.to_emails = emails
        self.cc = [chapter.region.email]
        self.reply_to = [
            "cmt@thetatau.org",
        ]
        if not chapter.candidate_chapter:
            chapter_name = chapter.name + " Chapter"
        else:
            chapter_name = chapter.name
        self.subject = f"CMT Officer update {chapter_name}"
        self.context = {
            "chapter": chapter_name,
            "officers": format_officers,
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        chapter = Chapter.objects.order_by("?")[0]
        emails, officers_to_update = chapter.get_about_expired_coucil()
        return [
            chapter,
            emails,
            officers_to_update,
        ]
