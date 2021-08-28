from herald import registry
from herald.base import EmailNotification
from tasks.models import TaskDate
from django.conf import settings
from chapters.models import Chapter
from chapters.tables import ChapterStatusTable


@registry.register_decorator()
class OfficerMonthly(EmailNotification):  # extend from EmailNotification for emails
    template_name = "officer_monthly"  # name of template, without extension
    subject = "CMT Monthly Update"  # subject of email

    def __init__(self, chapter):  # optionally customize the initialization
        self.context = {"user": chapter}  # set context for the template rendering
        officer_list, previous = chapter.get_current_officers_council(False)
        # set list of emails to send to
        self.to_emails = set([officer.email for officer in officer_list]) | set(
            chapter.get_generic_chapter_emails()
        )
        self.cc = []
        self.reply_to = [
            "cmt@thetatau.org",
        ]
        if "colony" not in chapter.name.lower():
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
            "tasks_overdue": TaskDate.incomplete_dates_for_chapter_past(chapter),
            "region_announcements": None,
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
        if region == "colony":
            email = "coldir@thetatau.org"
            chapters = Chapter.objects.filter(colony=True)
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
            if not chapter.active or (chapter.colony and not region == "colony"):
                continue
            officers = chapter.get_current_officers_council_specific()
            officer_order = {0: "Regent", 1: "Scribe", 2: "Vice", 3: "Treasurer"}
            missing = ", ".join(
                [
                    officer_order[ind]
                    for ind, officer in enumerate(officers)
                    if officer is None
                ]
            )
            data.append(
                {
                    "name": chapter.name,
                    "slug": chapter.slug,
                    "balance": chapter.balance,
                    "balance_date": chapter.balance_date,
                    "officer_missing": missing,
                    "member_count": chapter.actives().count(),
                    "pledge_count": chapter.pledges().count(),
                    "event_count": chapter.events_last_month().count(),
                    "tasks_overdue": TaskDate.incomplete_dates_for_chapter_past(
                        chapter
                    ).count(),
                }
            )
        table = ChapterStatusTable(data=data)
        self.context = {
            "region": region,
            "table": table,
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
