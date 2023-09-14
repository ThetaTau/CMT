from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.forms.models import modelformset_factory
from django.http.response import HttpResponseRedirect
from django.views.generic import RedirectView
from django.utils.safestring import mark_safe
from core.views import (
    RequestConfig,
    OfficerRequiredMixin,
    LoginRequiredMixin,
    PagedFilteredTableView,
)
from core.forms import MultiFormsView
from .models import Chapter
from .forms import ChapterForm, ChapterFormHelper
from .filters import ChapterListFilter
from .tables import ChapterCurriculaTable, ChapterTable, AuditTable
from users.tables import UserTable
from users.models import User, Role
from users.forms import ExternalUserForm
from tasks.models import Task
from submissions.models import Submission
from forms.notifications import EmailAdvisorWelcome
from forms.models import Audit
from notes.tables import ChapterNoteTable


class ChapterDetailView(LoginRequiredMixin, MultiFormsView):
    template_name = "chapters/chapter_detail.html"
    form_classes = {
        "chapter": ChapterForm,
        "faculty": ExternalUserForm,
    }

    def faculty_form_valid(self, formset):
        if formset.has_changed():
            for form in formset.forms:
                if form.changed_data and "DELETE" not in form.changed_data:
                    chapter = self.request.user.current_chapter
                    if form.instance.badge_number == 999999999:
                        form.instance.chapter = chapter
                        form.instance.badge_number = chapter.next_advisor_number
                    try:
                        # This is either a previous faculty or alumni
                        user = User.objects.get(username=form.instance.email)
                    except User.DoesNotExist:
                        user = form.save()
                    if not user.is_advisor:
                        user.set_current_status(status="advisor")
                        EmailAdvisorWelcome(user).send()
                    else:
                        messages.add_message(
                            self.request,
                            messages.INFO,
                            f"Advisor {user} already exists.",
                        )
                elif form.changed_data and "DELETE" in form.changed_data:
                    user = form.instance
                    user.set_current_status(None)
        return HttpResponseRedirect(self.get_success_url())

    def create_faculty_form(self, **kwargs):
        chapter = self.request.user.current_chapter
        facultys = chapter.advisors_external
        extra = 0
        min_num = 0
        if not facultys:
            extra = 0
            min_num = 1
        factory = modelformset_factory(
            User,
            form=ExternalUserForm,
            **{
                "can_delete": True,
                "extra": extra,
                "min_num": min_num,
                "validate_min": True,
            },
        )
        # factory.form.base_fields['chapter'].queryset = chapter
        formset_kwargs = {
            "queryset": facultys,
            "form_kwargs": {"initial": {"chapter": chapter}},
        }
        if self.request.method in ("POST", "PUT"):
            if self.request.POST.get("action") == "faculty":
                formset_kwargs.update(
                    {
                        "data": self.request.POST.copy(),
                    }
                )
        return factory(**formset_kwargs)

    def get_success_url(self, form_name=None):
        return reverse("chapters:detail", kwargs={"slug": self.kwargs["slug"]})

    def get_chapter_kwargs(
        self,
    ):
        return {"instance": get_object_or_404(Chapter, slug=self.kwargs["slug"])}

    def chapter_form_valid(self, form):
        if form.has_changed():
            form.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Can not use Task model as no guarantee that Task was completed
        # Use audit instead and get the officers
        chapter = self.request.user.current_chapter
        row_names = [
            "user",
            "modified",
            "dues_member",
            "dues_pledge",
            "frequency",
            "payment_plan",
            "cash_book",
            "cash_book_reviewed",
            "cash_register",
            "cash_register_reviewed",
            "member_account",
            "member_account_reviewed",
            "balance_checking",
            "balance_savings",
            "debit_card",
            "debit_card_access",
        ]
        audits = (
            Audit.objects.filter(user__chapter=chapter)
            .order_by("-modified")
            .values(*row_names)
        )
        audit_items = []
        audit_data = {}
        for audit in audits:
            user = User.objects.get(id=audit["user"])
            role = user.get_officer_role_on_date(audit["modified"])
            if role is not None:
                role = role.role
            if (role not in audit_data) and (role in Role.officers("chapter")):
                audit["user"] = user
                audit_data[role] = audit
            if len(audit_data) == len(Role.officers("chapter")):
                break
        for name in row_names:
            audit_item = {
                "item": Audit._meta.get_field(name).verbose_name.title(),
            }
            for officer in Role.officers("chapter"):
                audit = audit_data.get(officer, None)
                value = "Incomplete"
                if audit is not None:
                    value = audit.get(name, "Incomplete")
                audit_item.update({officer.replace(" ", "_"): value})
            audit_items.append(audit_item)
            # {
            #     'item': 'Debit Card Access',
            #     'corresponding_secretary': 'Incomplete',
            #     'treasurer': ['regent', 'treasurer'],
            #     'scribe': 'Incomplete',
            #     'vice_regent': ['regent', 'treasurer'],
            #     'regent': ['regent', 'treasurer']
            # }
        audit_table = AuditTable(data=audit_items)
        RequestConfig(self.request).configure(audit_table)
        context["audit_table"] = audit_table
        chapter = self.get_object()
        note_table = ChapterNoteTable(data=chapter.notes_filtered(self.request.user))
        RequestConfig(self.request).configure(note_table)
        context["note_table"] = note_table
        context.update(
            {
                "object": chapter,
            }
        )
        chapter_officers = chapter.get_current_officers()
        natoff = False
        if self.request.user.is_national_officer():
            natoff = True
        admin = self.request.user.is_superuser
        table = UserTable(data=chapter_officers, natoff=natoff, admin=admin)
        table.exclude = ("badge_number", "graduation_year")
        RequestConfig(self.request, paginate={"per_page": 100}).configure(table)
        context["table"] = table
        majors = chapter.curricula.filter(approved=True).order_by("major")
        major_table = ChapterCurriculaTable(data=majors)
        context["majors"] = major_table
        email_list = ", ".join([x.email for x in chapter_officers])
        email_list += f", {chapter.region.email}"
        context["email_list"] = email_list
        return context

    def get_form_kwargs(self, form_name, bind_form=False):
        kwargs = super()._get_form_kwargs(form_name, bind_form)
        if form_name == "chapter":
            kwargs.update(
                {
                    "instance": self.get_object(),
                }
            )
        return kwargs

    def get_object(self):
        # Only get the User record for the user making the request
        return Chapter.objects.get(slug=self.kwargs["slug"])


class ChapterRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse(
            "chapters:detail", kwargs={"slug": self.request.user.current_chapter.slug}
        )


class ChapterListView(LoginRequiredMixin, OfficerRequiredMixin, PagedFilteredTableView):
    model = Chapter
    context_object_name = "chapter"
    ordering = ["name"]
    table_class = ChapterTable
    filter_class = ChapterListFilter
    formhelper_class = ChapterFormHelper
    table_pagination = False

    def get_table_kwargs(self):
        return {
            "officer": self.request.user.is_national_officer(),
        }


class DuesSyncMixin:
    def sync_dues(self, request, queryset):
        message = "Sync complete for chapters: <br>"
        for chapter in queryset.all():
            invoice_number = chapter.sync_dues(request)
            message += f"{chapter}: {invoice_number}<br>"
        messages.add_message(request, messages.INFO, mark_safe(message))

    sync_dues.short_description = "Sync selected chapters dues to Quickbooks"

    def reminder_dues(self, request, queryset):
        message = "Sent reminders to chapters: <br>"
        for chapter in queryset.all():
            result = chapter.reminder_dues()
            message += f"{chapter}: {result}<br>"
        messages.add_message(request, messages.INFO, mark_safe(message))

    reminder_dues.short_description = "Send selected chapters dues reminder"
