from email_signals.models import EmailSignalMixin, Signal
from email_signals.forms import SignalAdminForm
from email_signals.admin import SignalAdmin


class SignalAdminFormFix(SignalAdminForm):
    def _clean_mailing_list(self):
        mailing_list = self.cleaned_data["mailing_list"]
        return mailing_list


class SignalAdminFix(SignalAdmin):
    form = SignalAdminFormFix


class EmailSignalDefaultMixin(EmailSignalMixin):
    def email_signal_recipients(self, emails: str):
        """Return a list of email addresses to send the signal to.
        will assume email provided
        """
        return {email.strip() for email in emails.split(",")}
