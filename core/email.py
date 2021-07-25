import datetime
from itertools import zip_longest
from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from bandit.backends.base import HijackBackendMixin
from django_middleware_global_request.middleware import get_request
import moosend_api_wrapper
from moosend_api_wrapper.rest import ApiException
from report_builder.admin import Report
from .views import group_required

if settings.DJANGO_EMAIL_LIVE:
    from anymail.backends.mailjet import EmailBackend
else:
    from django.core.mail.backends.console import EmailBackend


class MyHijackBackend(HijackBackendMixin, EmailBackend):
    """
    This backend intercepts outgoing messages drops them to a single email
    address, using the SendgridBackend
    """

    def send_messages(self, email_messages):
        request = get_request()
        # Test is needed to trick bandit with an unapproved email
        if request is None or request.user.is_anonymous:
            email = "cmt@thetatau.org"
        else:
            email = request.user.email
        setattr(settings, "BANDIT_EMAIL", [email, "test@thetatau.org"])
        for message in email_messages:
            message.subject = f"[TEST] {message.subject}"
            try:
                message.alternatives = [
                    (
                        message.alternatives[0][0].replace(
                            '<div id="hijacked"></div>',
                            "<br>HIJACKED EMAIL! Email only send to you as a test.<br>",
                        ),
                        "text/html",
                    )
                ]
            except:  # noqa: E722
                pass
        super().send_messages(email_messages)


@group_required(["officer", "natoff"])
def sync_email_provider(request, report_id):
    report = get_object_or_404(Report, pk=report_id)
    if report.root_model.name == "user":
        values = ["name", "email"]
    elif "user" in [
        field.name for field in report.root_model.model_class()._meta.fields
    ]:
        values = ["user__name", "user__email"]
    else:
        messages.add_message(
            request,
            messages.ERROR,
            f"Sync with email provider only set up for user root model",
        )
        return redirect(reverse("admin:report_builder_report_changelist"))
    queryset = report.get_query()
    subscribers = queryset.values(*values)
    subscribers = [
        {key.title().replace("User__", ""): val for key, val in subscriber_dict.items()}
        for subscriber_dict in subscribers
    ]
    # objects_list = report.report_to_list(user=request.user, preview=True,)
    mailing_api_instance = moosend_api_wrapper.MailingListsApi()
    subscriber_api_instance = moosend_api_wrapper.SubscribersApi()
    format = "json"
    apikey = settings.MOOSEND_API_KEY
    time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    mailing_body = moosend_api_wrapper.CreatingAMailingListRequest(
        name=f"{report.name} {time_str}"
    )
    subscriber_bodies = []
    # Maximum number of subscribers per request is 1000
    subscriber_groups = list(zip_longest(*(iter(subscribers),) * 999))
    for subscriber_group in subscriber_groups:
        subscribers = [subscriber for subscriber in subscriber_group if subscriber]
        subscriber_body = moosend_api_wrapper.AddingMultipleSubscribersRequest(
            subscribers=subscribers
        )
        subscriber_bodies.append(subscriber_body)
    try:
        # Creating a mailing list
        create_mailing_response = mailing_api_instance.creating_a_mailing_list(
            format, apikey, mailing_body
        )
        subscriber_mailing_responses = [create_mailing_response]
        for subscriber_body in subscriber_bodies:
            subscriber_mailing_response = (
                subscriber_api_instance.adding_multiple_subscribers(
                    format, apikey, create_mailing_response.context, subscriber_body
                )
            )
            subscriber_mailing_responses.append(subscriber_mailing_response)
    except ApiException as e:
        messages.add_message(
            request,
            messages.ERROR,
            f"Error sync with email provider {e}",
        )
    else:
        errors = [
            response.error
            for response in subscriber_mailing_responses
            if response.error
        ]
        if errors:
            messages.add_message(
                request,
                messages.ERROR,
                f"Error sync with email provider {errors}",
            )
        else:
            messages.add_message(
                request,
                messages.INFO,
                "Report sync with email provider complete",
            )
    return redirect(reverse("admin:report_builder_report_changelist"))
