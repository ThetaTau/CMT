from herald import registry
from herald.base import EmailNotification
from tasks.models import TaskDate
from django.conf import settings


@registry.register_decorator()
class OfficerMonthly(EmailNotification):  # extend from EmailNotification for emails
    template_name = 'officer_monthly'  # name of template, without extension
    subject = 'CMT Monthly Update'  # subject of email

    def __init__(self, chapter):  # optionally customize the initialization
        self.context = {'user': chapter}  # set context for the template rendering
        officer_list, previous = chapter.get_current_officers_council(False)
        self.to_emails = set([officer.email for officer in officer_list])  # set list of emails to send to
        self.cc = [chapter.region.email, "cmt@thetatau.org"]
        self.reply_to = ["cmt@thetatau.org", ]
        if 'colony' not in chapter.name.lower():
            chapter_name = chapter.name + " Chapter"
        else:
            chapter_name = chapter.name
        self.subject = f'CMT Monthly Update {chapter_name}'
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
        from users.models import User
        return [User.objects.order_by('?')[0].chapter]


@registry.register_decorator()
class NewOfficers(EmailNotification):  # extend from EmailNotification for emails
    template_name = 'officer_new'  # name of template, without extension
    subject = 'Welcome New Theta Tau Officers'  # subject of email

    def __init__(self, new_officers):  # optionally customize the initialization
        self.to_emails = set([officer.email for officer in new_officers])  # set list of emails to send to
        self.reply_to = ["cmt@thetatau.org", ]
        chapter = new_officers[0].current_chapter
        self.context = {
            'chapter': chapter,
            "region_facebook": chapter.region.facebook,
            "region_web": chapter.region.website,
            "director_emails": chapter.region.email,
            'host': settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from users.models import User
        return [[User.objects.order_by('?')[0], User.objects.order_by('?')[0],
                 User.objects.order_by('?')[0]]]
