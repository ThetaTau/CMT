from django.conf import settings
from django.utils.safestring import mark_safe
from django.urls import reverse
from report_builder.admin import ReportAdmin


def user_chapter(obj):
    return obj.user.chapter


class ReportAdminSync(ReportAdmin):
    ReportAdmin.list_display += ("sync_mail",)

    def sync_mail(self, model_object):
        return mark_safe(
            f'<a href="{reverse("users:sync_email_provider", kwargs={"report_id": model_object.id})}"'
            f" onclick=\"alert('Start sync with email provider, this may take some time...');\">"
            '<img style="width: 26px; margin: -6px" src="'
            f'{getattr(settings, "STATIC_URL", "/static/")}report_builder/img/reorder.svg"/></a>'
        )

    sync_mail.short_description = "Email Sync"
    sync_mail.allow_tags = True
