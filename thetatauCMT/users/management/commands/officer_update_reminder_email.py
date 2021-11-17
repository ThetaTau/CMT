
"""
Notes:
    To test run command
        docker-compose -f local.yml run --rm django python manage.py officer_update_reminder_email
"""

#Includes
import datetime
from django.core.management import BaseCommand
from django.core.mail import send_mail
from users.notifications import OfficerMonthly, RDMonthly,OfficerUpdateRemider
from chapters.models import Chapter
from regions.models import Region

# python manage.py officer_update_reminder_email
# python3 manage.py officer_update_reminder_email # for mac

#Variables for send mail function
emailSubject = 'Officer update reminder'
emailMessage = "Please update all officers."
ThetaTauEmail = "cmt@thetatau.org"


# python manage.py officer_update_reminder
class Command(BaseCommand):
    # Show this when the user types help
    help = "Send email to eboard positions to remind to update"

    def add_arguments(self, parser):
        parser.add_argument("-override", action="store_true")
        parser.add_argument("-chapter", nargs="+", type=str)
        parser.add_argument("-rdonly", action="store_true")

    # A command must define handle()
    def handle(self, *args, **options):
        override = options.get("override", False)
        chapters_only = options.get("chapter", None)
        if chapters_only is not None:
            chapters = Chapter.objects.filter(slug__in=chapters_only)
        else:
            chapters = Chapter.objects.all()
        for chapter in chapters:
            if not chapter.active:
                continue
            #print(f"Chapter: {chapter}")
            print(chapter)
            # print(chapter.get_current_officers_council_specific())#only 3 out of the five
            # print(chapter.get_generic_chapter_emails())#out of email only produces the email of the chapter
            # print(chapter.get_current_officers())#prints out true
            # print(chapter.get_current_officers_council())
            futurePos = chapter.get_about_expired_coucil()
            officers = chapter.get_current_officers_council(combine=False)[0]
            regent = officers.filter(role="regent").first()
            scribe = officers.filter(role="scribe").first()
            vice = officers.filter(role="vice regent").first()
            treasurer = officers.filter(role="treasurer").first()
            cosec = officers.filter(role="corresponding secretary").first()
            for people in futurePos:
                print(f"{people}")     
    
    

            

