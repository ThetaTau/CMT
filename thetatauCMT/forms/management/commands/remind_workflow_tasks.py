import datetime
from django.conf import settings
from django.urls import reverse
from django.core.management import BaseCommand
from viewflow.models import Task
from viewflow.activation import STATUS
from core.flows import cancel_process
from forms.forms import DisciplinaryForm1
from forms.notifications import EmailProcessUpdate


class Command(BaseCommand):
    # Show this when the user types help
    help = "Check all assigned workflow tasks, if today - 14/30 remind tasks"

    def add_arguments(self, parser):
        parser.add_argument("-date", nargs=1, type=str, help="all tasks < date + 1 day")
        parser.add_argument(
            "-chapter", nargs=1, type=str, help="Only process for this chapter"
        )

    # A command must define handle()
    def handle(self, *args, **options):
        date_str = options.get("date", None)
        chapter_only = options.get("chapter", None)
        if chapter_only is not None:
            chapter_only = chapter_only[0]
            print(f"Process tasks for chapter {chapter_only}")
        date = datetime.datetime.today()
        if date_str:
            date_str = date_str[0]
            date = datetime.datetime.strptime(date_str, "%Y%m%d")
        print(f"Process tasks for date <= {date}")
        host = settings.CURRENT_URL
        # We look for tasks assigned but not handled
        function_tasks = Task.objects.filter(
            status=STATUS.ASSIGNED, flow_task_type="HUMAN"
        )
        print(f"Assigned Tasks found {function_tasks.count()}")
        for function_task in function_tasks.all():
            process = function_task.flow_process
            owner = function_task.owner
            chapter = process.chapter
            created = process.created.date()
            if chapter_only:
                if chapter.name.lower() != chapter_only:
                    continue
            date_5mo = (date - datetime.timedelta(days=30 * 5)).date()
            date_30 = (date - datetime.timedelta(days=30)).date()
            date_14 = (date - datetime.timedelta(days=14)).date()
            date_7 = (date - datetime.timedelta(days=7)).date()
            extra = ""
            days = 30
            email_officers = False
            fields = []
            attachments = []
            extra_emails = {}
            complete_step = "Previous step complete"
            next_step = "Next Step"
            state = "Pending Update"
            process_title = "Process Update"
            message = "Please update on process."
            if process.flow_class.process_title == "Disciplinary Process":
                if function_task.flow_task.name == "submit_form2":
                    if process.trial_date <= date_30:
                        # Trial date time plus delta is not yet reached
                        # Send every day past 30 days
                        process_title = f"URGENT {process.flow_class.process_title}"
                        days = 30
                        email_officers = True
                        extra_emails = {chapter.region.email}
                        extra = "<i>This email will continue to be sent daily until the form is submitted or someone contacts the central office with an update.</i>"
                    elif process.trial_date == date_7:
                        process_title = f"REMINDER {process.flow_class.process_title}"
                        days = 7
                    elif process.trial_date == date_14:
                        process_title = f"REMINDER {process.flow_class.process_title}"
                        days = 14
                        email_officers = True
                    else:
                        continue
                    link = reverse(
                        "viewflow:forms:disciplinaryprocess:submit_form2",
                        kwargs={
                            "process_pk": process.pk,
                            "task_pk": function_task.pk,
                        },
                    )
                    link = host + link
                    complete_step = "Trial Complete"
                    next_step = "Complete Trial Outcome Form"
                    state = "Pending Trial Outcome Form"
                    fields = DisciplinaryForm1._meta.fields[:]
                    fields.remove("charging_letter")
                    message = (
                        "This is a reminder that, per the form filed on "
                        f"{created}, your chapter had scheduled a trial for "
                        f"{process.user} on {process.trial_date}.  "
                        f"It has been over {days} days since the trial date. Please remember that {owner} must update us on the status "
                        f"of this trial by filling out the form located at: <a href='{link}'>Disciplinary Process Form 2</a>.  (This link will only work for the assigned member)"
                        f"<br><b>If {owner} is no longer available or the trial date has changed or anything needs to be updated"
                        f", please reach out to the Central Office. {extra}"
                        f" Please fill out the next form or updated the central office ASAP.</b><br>"
                        " If you have questions, please email or call the Central Office "
                        "at central.office@thetatau.org // 512-472-1904."
                    )
                else:
                    # not a notify function
                    continue
            elif process.flow_class.process_title == "Convention Process":
                if created <= date_5mo:
                    cancel_process(process)
                    continue
                elif created <= date_30:
                    process_title = f"URGENT {process.flow_class.process_title}"
                    days = 30
                    email_officers = True
                    extra_emails = {chapter.region.email}
                    extra = "<i>This email will continue to be sent daily until the form is submitted or someone contacts the central office with an update.</i>"
                elif created == date_14:
                    process_title = f"REMINDER {process.flow_class.process_title}"
                    days = 14
                    email_officers = True
                elif created == date_7:
                    process_title = f"REMINDER {process.flow_class.process_title}"
                    days = 7
                else:
                    # not in time ranges
                    continue
                link = reverse(
                    f"viewflow:forms:convention:{function_task.flow_task.name}",
                    kwargs={
                        "process_pk": process.pk,
                        "task_pk": function_task.pk,
                    },
                )
                link = host + link
                complete_step = "Convention Delegates Selected"
                next_step = "Delegate and Officer Verification"
                state = "Pending Verification and Signatures"
                message = (
                    "This is a reminder that, per the form filed on "
                    f"{created}, your chapter selected delegates and alternates."
                    f"It has been over {days} days since the selection date. Please remember that {owner} must verify the selection "
                    f"by filling out the form located at: <a href='{link}'>Convention Process Form</a>. (This link will only work for the assigned member)"
                    f"<br><b>If {owner} is no longer available or the delegate information has changed or anything needs to be updated"
                    f", please reach out to the Central Office. {extra}"
                    f" Please fill out the next form or updated the central office ASAP.</b><br>"
                    " If you have questions, please email or call the Central Office "
                    "at central.office@thetatau.org // 512-472-1904."
                )
            elif process.flow_class.process_title == "OSM Process":
                if created <= date_5mo:
                    cancel_process(process)
                elif created <= date_30:
                    process_title = f"URGENT {process.flow_class.process_title}"
                    days = 30
                    email_officers = True
                    extra_emails = {chapter.region.email}
                    extra = "<i>This email will continue to be sent daily until the form is submitted or someone contacts the central office with an update.</i>"
                elif created == date_14:
                    process_title = f"REMINDER {process.flow_class.process_title}"
                    days = 14
                    email_officers = True
                elif created == date_7:
                    process_title = f"REMINDER {process.flow_class.process_title}"
                    days = 7
                else:
                    # not in time ranges
                    continue
                link = reverse(
                    f"viewflow:forms:osm:{function_task.flow_task.name}",
                    kwargs={
                        "process_pk": process.pk,
                        "task_pk": function_task.pk,
                    },
                )
                link = host + link
                complete_step = "Outstanding Student Member Selected"
                next_step = "Officer Verification"
                state = "Pending Verification"
                message = (
                    "This is a reminder that, per the form filed on "
                    f"{created}, your chapter selected an outstanding student member."
                    f"It has been over {days} days since the selection date. Please remember that {owner} must verify the selection "
                    f"by filling out the form located at: <a href='{link}'>OSM Process Form</a>. (This link will only work for the assigned member)"
                    f"<br><b>If {owner} is no longer available or the OSM information has changed or anything needs to be updated"
                    f", please reach out to the Central Office. {extra}"
                    f" Please fill out the next form or updated the central office ASAP.</b><br>"
                    " If you have questions, please email or call the Central Office "
                    "at central.office@thetatau.org // 512-472-1904."
                )
            elif process.flow_class.process_title == "Resignation Process":
                if created <= date_30:
                    process_title = f"URGENT {process.flow_class.process_title}"
                    days = 30
                    email_officers = True
                    extra_emails = {chapter.region.email}
                    extra = "<i>This email will continue to be sent daily until the form is submitted or someone contacts the central office with an update.</i>"
                elif created == date_14:
                    process_title = f"REMINDER {process.flow_class.process_title}"
                    days = 14
                    email_officers = True
                elif created == date_7:
                    process_title = f"REMINDER {process.flow_class.process_title}"
                    days = 7
                else:
                    # not in time ranges
                    continue
                link = reverse(
                    f"viewflow:forms:resignation:{function_task.flow_task.name}",
                    kwargs={
                        "process_pk": process.pk,
                        "task_pk": function_task.pk,
                    },
                )
                link = host + link
                complete_step = "Resignation Submitted"
                next_step = "Officer Verification"
                state = "Pending Verification"
                fields = []
                # attachments = ["letter"]
                message = (
                    "This is a reminder that, per the form filed on "
                    f"{created}, your chapter member has submitted a resignation form. "
                    f"It has been over {days} days since the submission date. Please remember that {owner} must review the resignation "
                    f"by filling out the form located at: <a href='{link}'>Resignation Process Form</a>. (This link will only work for the assigned member)"
                    f"<br><b>If {owner} is no longer available or the resignation has changed or anything needs to be updated"
                    f", please reach out to the Central Office. {extra}"
                    f" Please fill out the next form or updated the central office ASAP.</b><br>"
                    " If you have questions, please email or call the Central Office "
                    "at central.office@thetatau.org // 512-472-1904."
                )
            else:
                print(f"{process.flow_class.process_title} Type not accounted for")
            print(
                f"Send update for: {days} {process} for {owner} at {chapter} created {created} {function_task.status}"
            )
            EmailProcessUpdate(
                process,
                complete_step=complete_step,
                next_step=next_step,
                state=state,
                message=message,
                fields=fields,
                direct_user=owner,
                process_title=process_title,
                email_officers=email_officers,
                attachments=attachments,
                extra_emails=extra_emails,
            ).send()
