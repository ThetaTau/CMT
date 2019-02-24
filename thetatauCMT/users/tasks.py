from django.core import management
from celery import shared_task


@shared_task
def monthly_chapter_officer_email():
    try:
        """
        Send monthly chapter email by using Django management command.
        """
        management.call_command("monthly_chapter_officer_email", verbosity=0)
        return "success"
    except Exception as e:
        print(e)
