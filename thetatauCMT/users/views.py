import csv
import datetime
import zipfile
from io import BytesIO, StringIO

import viewflow
from allauth.account.views import LoginView
from crispy_forms.layout import Submit
from dal import autocomplete
from django import forms
from django.contrib import messages
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core import signing
from django.forms.models import modelformset_factory
from django.http import HttpResponse
from django.http.request import QueryDict
from django.http.response import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_encode
from django.views.generic import DetailView, FormView, RedirectView, TemplateView, UpdateView, View
from extra_views import FormSetView, ModelFormSetView
from watson import search as watson

from core.address import isinradius
from core.forms import MultiFormsView
from core.models import (
    BIENNIUM_YEARS,
    academic_encompass_start_end_date,
    annotate_rmp_status,
    semester_encompass_start_end_date,
)
from core.views import (
    LoginRequiredMixin,
    NatOfficerRequiredMixin,
    OfficerRequiredMixin,
    PagedFilteredTableView,
    RequestConfig,
    group_required,
)
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.forms.forms import PledgeDemographicsForm
from thetatauCMT.notes.tables import UserNoteTable
from thetatauCMT.submissions.tables import SubmissionTable

from .filters import UserListFilter, UserListFilterBase
from .forms import (
    CaptchaLoginForm,
    EmailPreferencesForm,
    UserAlterForm,
    UserForm,
    UserGPAForm,
    UserListFormHelper,
    UserLookupForm,
    UserLookupSearchForm,
    UserLookupSelectForm,
    UserOrgForm,
    UserServiceForm,
    UserUpdateForm,
)
from .models import (
    MemberUpdate,
    User,
    UserAlter,
    UserDemographic,
    UserOrgParticipate,
    UserSemesterGPA,
    UserSemesterServiceHours,
    UserStatusChange,
)
from .notifications import MemberInfoUpdate
from .tables import UserTable
from .unsubscribe import CATEGORY_ALL, UNSUBSCRIBE_CATEGORIES, get_category, is_unsubscribed


class UserRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse("users:detail")


UNSUBSCRIBE_SALT = "users.unsubscribe.v1"


def make_unsubscribe_token(user, category=None):
    """Return a signed, tamper-resistant token that identifies ``user``.

    When ``category`` is provided it is embedded in the token so the
    confirmation page can pre-select that mailing list. Unknown category
    slugs are silently dropped so a mis-typed slug in an email footer does
    not blow up the recipient's unsubscribe page.
    """
    payload = {"user_pk": user.pk}
    if category and get_category(category) is not None:
        payload["category"] = category
    return signing.dumps(payload, salt=UNSUBSCRIBE_SALT)


class UnsubscribeConfirmView(TemplateView):
    """Public unsubscribe manager.

    GET renders one checkbox per registered category plus an "unsubscribe
    from all optional email" toggle. When the token embeds a category, that
    box is pre-checked so the one-click flow (from the email footer) still
    just needs a single form submission to opt out of that mailing list.
    POST persists the choices. Requiring a POST prevents mail-scanner
    prefetch (Gmail/Outlook/etc.) from silently unsubscribing users.
    """

    template_name = "users/unsubscribe_confirm.html"
    http_method_names = ["get", "post"]

    def _load_payload(self):
        token = self.kwargs.get("token", "")
        try:
            data = signing.loads(token, salt=UNSUBSCRIBE_SALT)
        except signing.BadSignature:
            return None, None
        user = User.objects.filter(pk=data.get("user_pk")).first()
        category_slug = data.get("category")
        return user, category_slug

    def _category_rows(self, user, focus_slug, *, preselect_focus):
        rows = []
        for category in UNSUBSCRIBE_CATEGORIES:
            unsubscribed = is_unsubscribed(user, category.slug) if user else False
            focused = category.slug == focus_slug
            checked = unsubscribed or (preselect_focus and focused)
            rows.append(
                {
                    "slug": category.slug,
                    "label": category.label,
                    "description": category.description,
                    "checked": checked,
                    "focused": focused,
                }
            )
        return rows

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user, focus_slug = self._load_payload()
        ctx["user_obj"] = user
        ctx["focus_slug"] = focus_slug
        ctx["focus_category"] = get_category(focus_slug) if focus_slug else None
        ctx["categories"] = self._category_rows(user, focus_slug, preselect_focus=True)
        ctx["all_checked"] = bool(user and user.unsubscribe_email)
        ctx["category_all"] = CATEGORY_ALL
        ctx["done"] = False
        return ctx

    def post(self, request, *args, **kwargs):
        user, focus_slug = self._load_payload()
        if user is None:
            ctx = super().get_context_data(**kwargs)
            ctx["user_obj"] = None
            ctx["done"] = False
            return self.render_to_response(ctx)

        selected = set(request.POST.getlist("categories"))
        unsubscribe_all = CATEGORY_ALL in selected
        update_fields = []

        if unsubscribe_all != user.unsubscribe_email:
            user.unsubscribe_email = unsubscribe_all
            update_fields.append("unsubscribe_email")

        current = list(user.unsubscribe_categories or [])
        new_list = [c.slug for c in UNSUBSCRIBE_CATEGORIES if c.slug in selected]
        # Keep any legacy/unknown slugs the model may already hold instead
        # of silently discarding them on an unrelated save.
        preserved = [slug for slug in current if slug not in {c.slug for c in UNSUBSCRIBE_CATEGORIES}]
        new_list.extend(preserved)
        if set(new_list) != set(current):
            user.unsubscribe_categories = new_list
            update_fields.append("unsubscribe_categories")

        if update_fields:
            user.save(update_fields=update_fields)

        # When a member opts out of all optional email, mirror the opt-out to
        # the other organization's MailerLite list (best-effort, never fatal).
        if unsubscribe_all and "unsubscribe_email" in update_fields:
            from thetatauCMT.email_tracking import mailerlite_sync

            mailerlite_sync.unsubscribe_user(user)

        ctx = super().get_context_data(**kwargs)
        ctx["user_obj"] = user
        ctx["focus_slug"] = focus_slug
        ctx["focus_category"] = get_category(focus_slug) if focus_slug else None
        ctx["categories"] = self._category_rows(user, focus_slug, preselect_focus=False)
        ctx["all_checked"] = user.unsubscribe_email
        ctx["category_all"] = CATEGORY_ALL
        ctx["done"] = True
        return self.render_to_response(ctx)


@group_required(["officer", "natoff"])
def user_verify(request):
    user_pk = request.GET.get("user_pk")
    user = User.objects.get(pk=user_pk)
    form = UserForm(instance=user, verify=True)
    return render(request, "users/user_verify_form.html", {"form": form})


RESIGNED_STATUSES = {"resigned", "resignedCC"}
EXPELLED_STATUSES = {"expelled", "pendexpul"}
DISCIPLINE_STATUSES = {"suspended", "probation"}


class UserProfileView(LoginRequiredMixin, DetailView):
    """Public member profile visible to any authenticated Theta Tau member.

    Sensitive natoff-only content (notes, submissions, job postings, task
    completions) is added to the context only for national officers. Owner
    and superuser get edit shortcuts in the template.
    """

    slug_field = "username"
    slug_url_kwarg = "username"
    template_name = "users/user_profile.html"
    model = User

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("chapter", "major", "address__locality__state__country")
            .prefetch_related("roles", "orgs", "ritual_proficiency")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target = self.object
        viewer = self.request.user

        is_owner = viewer.is_authenticated and viewer.pk == target.pk
        is_natoff = viewer.is_national_officer_group
        is_officer = viewer.is_officer_group
        is_superuser = viewer.is_superuser

        try:
            initiation = target.initiation
        except Exception:
            initiation = None

        # Per-field contact visibility. National Officers, superusers, and the
        # member themselves always see the information; everyone else is subject
        # to the member's chosen visibility level.
        show_email = target.contact_visible_to(viewer, target.email_visibility)
        show_phone = target.contact_visible_to(viewer, target.phone_visibility)
        show_address = target.contact_visible_to(viewer, target.address_visibility)
        has_email = bool(target.email) or bool(target.email_school)
        has_hidden_contact = (
            (has_email and not show_email)
            or (bool(target.phone_number) and not show_phone)
            or (bool(target.address_id) and not show_address)
        )

        context.update(
            {
                "is_owner": is_owner,
                "is_natoff": is_natoff,
                "is_officer": is_officer,
                "is_superuser": is_superuser,
                "can_view_sensitive": is_natoff or is_superuser,
                "current_status_label": (
                    UserStatusChange.STATUS.get_value(target.current_status) if target.current_status else ""
                ),
                "is_resigned": target.current_status in RESIGNED_STATUSES,
                "is_expelled": target.current_status in EXPELLED_STATUSES,
                "is_discipline": target.current_status in DISCIPLINE_STATUSES,
                "initiation": initiation,
                "roles_history": target.roles.all().order_by("-end", "-start"),
                "orgs": target.orgs.all().order_by("-start", "org_name"),
                "ritual_records": target.ritual_proficiency.all().order_by("-date", "-level"),
                "role_labels": _role_labels(target.current_roles),
                "show_email": show_email,
                "show_phone": show_phone,
                "show_address": show_address,
                "has_hidden_contact": has_hidden_contact,
                # Regions this member directs (Region.directors M2M). Drives the
                # prominent "Regional Director" card + generic region contact info.
                "director_regions": (target.regional_director.all().prefetch_related("chapters").order_by("name")),
            }
        )

        # Volunteer nominations (#2/#3/#9/#14). Anyone can nominate a member;
        # the member (owner) and National Officers can see the status of the
        # member's nominations. A member may nominate themselves, which
        # overrides a previous "not interested" response.
        target_nominations = list(target.nominations.select_related("nominator").order_by("-created"))
        context["nominee_nominations"] = target_nominations
        context["has_active_nomination"] = any(n.finished is None for n in target_nominations)
        context["target_declined_nomination"] = target.declined_nomination
        context["can_view_nomination_status"] = is_owner or is_natoff or is_superuser
        context["nominate_url"] = reverse("viewflow:nominations:nomination:start") + f"?nominee={target.pk}"

        # WI-8 — member attendance (visible to any authenticated member). The
        # add-missing-attendance form is only offered to the member themselves
        # or a National Officer.
        from thetatauCMT.attendance.forms import MemberAttendanceForm
        from thetatauCMT.attendance.services import member_attendance

        records = list(member_attendance(target))
        # Classify each record into date buckets for the client-side filters
        # (this semester / last semester / this academic year).
        this_sem_start, this_sem_end = (d.date() for d in semester_encompass_start_end_date())
        _last_ref = this_sem_start - datetime.timedelta(days=1)
        last_sem_start, last_sem_end = (
            d.date()
            for d in semester_encompass_start_end_date(
                given_date=datetime.datetime(_last_ref.year, _last_ref.month, _last_ref.day)
            )
        )
        year_start, year_end = (d.date() for d in academic_encompass_start_end_date())
        present_chapters = {}
        has_national = False
        for rec in records:
            event_date = rec.event.date
            tokens = []
            if this_sem_start <= event_date < this_sem_end:
                tokens.append("this-semester")
            if last_sem_start <= event_date < last_sem_end:
                tokens.append("last-semester")
            if year_start <= event_date < year_end:
                tokens.append("this-year")
            rec.period_tokens = " ".join(tokens)
            if rec.event.chapter_id:
                present_chapters[rec.event.chapter.slug] = rec.event.chapter.name
            if rec.event.is_national:
                has_national = True

        context["attendance_records"] = records
        context["attendance_chapters"] = sorted(present_chapters.items(), key=lambda kv: kv[1])
        context["has_national_attendance"] = has_national
        context["can_add_attendance"] = is_owner or is_natoff or is_superuser
        if context["can_add_attendance"]:
            context["attendance_form"] = MemberAttendanceForm(member=target)
            context["attendance_add_url"] = reverse("attendance:member_add", kwargs={"username": target.username})

        if is_natoff or is_superuser:
            note_table = UserNoteTable(target.notes.all())
            RequestConfig(self.request, paginate={"per_page": 15}).configure(note_table)
            context["note_table"] = note_table

            submission_table = SubmissionTable(target.submissions.all())
            RequestConfig(self.request, paginate={"per_page": 15}).configure(submission_table)
            context["submission_table"] = submission_table

            from thetatauCMT.jobs.models import Job
            from thetatauCMT.jobs.tables import JobTable

            job_qs = Job.objects.filter(created_by=target).order_by("-publish_start")
            job_table = JobTable(job_qs)
            RequestConfig(self.request, paginate={"per_page": 15}).configure(job_table)
            context["job_table"] = job_table

            from thetatauCMT.tasks.models import TaskChapter

            context["task_completions"] = (
                TaskChapter.objects.filter(created_by=target)
                .select_related("task__task", "chapter")
                .order_by("-date")[:100]
            )

        return context


# Backward-compat alias so any external imports keep working.
UserDetailView = UserProfileView


def _role_labels(current_roles):
    """Return a list of ``(slug, label)`` pairs for the user's current roles."""
    if not current_roles:
        return []
    return [(slug, slug.title()) for slug in current_roles]


class ProfilePictureUpdateView(LoginRequiredMixin, UpdateView):
    """Owner-only view for uploading / clearing a profile picture."""

    model = User
    template_name = "users/profile_picture_form.html"
    fields = ("profile_picture",)

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        return reverse("users:profile", kwargs={"username": self.request.user.username})

    def form_valid(self, form):
        if self.request.POST.get("clear") == "1":
            if form.instance.profile_picture:
                form.instance.profile_picture.delete(save=False)
            form.instance.profile_picture = None
            form.instance.save(update_fields=["profile_picture"])
            messages.success(self.request, "Profile picture removed.")
            return HttpResponseRedirect(self.get_success_url())
        response = super().form_valid(form)
        messages.success(self.request, "Profile picture updated.")
        return response


class UserDetailUpdateView(LoginRequiredMixin, MultiFormsView):
    template_name = "users/user_detail.html"
    form_classes = {
        "gpa": UserGPAForm,
        "service": UserServiceForm,
        "user": UserForm,
        "demo": PledgeDemographicsForm,
        "prefs": EmailPreferencesForm,
        "orgs": None,
    }

    # send the user back to their own page after a successful update
    def get_success_url(self, form_name=None):
        return reverse("users:detail")

    def get_gpa_initial(self):
        user = self.request.user
        initial = {"user": user.name}
        user_gpas = user.gpas.filter(year__gte=BIENNIUM_YEARS[0]).values("year", "term", "gpa")
        if user_gpas:
            for i in range(4):
                semester = "sp" if i % 2 else "fa"
                year = BIENNIUM_YEARS[i]
                try:
                    gpa = user_gpas.get(term=semester, year=year)
                except UserSemesterGPA.DoesNotExist:
                    continue
                else:
                    initial[f"gpa{i + 1}"] = gpa["gpa"]
        for key in ["gpa1", "gpa2", "gpa3", "gpa4"]:
            if key not in initial:
                initial[key] = 0.0
        return initial

    def gpa_form_valid(self, form):
        if form.has_changed():
            form.save()
            messages.success(self.request, "Your GPA and service hours were updated.")
        else:
            messages.info(self.request, "No changes were made.")
        return HttpResponseRedirect(self.get_success_url() + "#member_gpaservice")

    def user_form_valid(self, form):
        if form.has_changed():
            form.save()
            messages.success(self.request, "Your member information was updated.")
        else:
            messages.info(self.request, "No changes were made.")
        return HttpResponseRedirect(self.get_success_url() + "#user")

    def prefs_form_valid(self, form):
        if form.has_changed():
            form.save()
            messages.success(self.request, "Your email preferences were updated.")
        else:
            messages.info(self.request, "No changes were made.")
        return HttpResponseRedirect(self.get_success_url() + "#email_prefs")

    def demo_form_valid(self, form):
        if form.has_changed():
            user = self.request.user
            form.instance.user = user
            form.save()
            messages.success(self.request, "Your demographic information was updated.")
        else:
            messages.info(self.request, "No changes were made.")
        return HttpResponseRedirect(self.get_success_url() + "#demo")

    def orgs_form_valid(self, formset):
        if formset.has_changed():
            formset.save()
            messages.success(self.request, "Your external organizations were updated.")
        else:
            messages.info(self.request, "No changes were made.")
        return HttpResponseRedirect(self.get_success_url() + "#member_orgs")

    def create_orgs_form(self, **kwargs):
        orgs = self.request.user.orgs.all()
        extra = 0
        if not orgs:
            extra = 1
        factory = modelformset_factory(UserOrgParticipate, form=UserOrgForm, **{"can_delete": True, "extra": extra})
        factory.form.base_fields["user"].queryset = User.objects.filter(pk=self.request.user.pk)
        formset_kwargs = {
            "queryset": orgs,
            "form_kwargs": {"hide_user": True, "initial": {"user": self.request.user}},
        }
        if self.request.method in ("POST", "PUT"):
            if self.request.POST.get("action") == "orgs":
                formset_kwargs.update(
                    {
                        "data": self.request.POST.copy(),
                    }
                )
        return factory(**formset_kwargs)

    def get_service_initial(self):
        user = self.request.user
        initial = {"user": user.name}
        user_service = user.service_hours.filter(year__gte=BIENNIUM_YEARS[0]).values("year", "term", "service_hours")
        if user_service:
            for i in range(4):
                semester = "sp" if i % 2 else "fa"
                year = BIENNIUM_YEARS[i]
                try:
                    service = user_service.get(term=semester, year=year)
                except UserSemesterServiceHours.DoesNotExist:
                    continue
                else:
                    initial[f"service{i + 1}"] = service["service_hours"]
        for key in ["service1", "service2", "service3", "service4"]:
            if key not in initial:
                initial[key] = 0.0
        return initial

    def service_form_valid(self, form):
        if form.has_changed():
            form.save()
        return HttpResponseRedirect(self.get_success_url() + "#member_gpaservice")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "object": self.get_object(),
            }
        )
        headers = [""]
        for i in range(4):
            year = BIENNIUM_YEARS[i]
            semester = "Spring" if i % 2 else "Fall"
            headers.append(f"{semester} {year}")
        context["table_headers"] = headers
        submissions = self.request.user.submissions.all()
        table = SubmissionTable(submissions)
        RequestConfig(self.request, paginate={"per_page": 30}).configure(table)
        context["submission_table"] = table
        return context

    def _get_form_kwargs(self, form_name, bind_form=False):
        kwargs = super()._get_form_kwargs(form_name, bind_form)
        if form_name == "user":
            kwargs.update(
                {
                    "instance": self.get_object(),
                }
            )
        if form_name == "prefs":
            kwargs.update(
                {
                    "instance": self.get_object(),
                }
            )
        if form_name == "demo":
            instance = UserDemographic.objects.filter(user=self.request.user).first()
            if instance:
                kwargs.update(
                    {
                        "instance": instance,
                    }
                )
        if form_name in ["gpa", "service"]:
            kwargs.update(
                {
                    "hide_user": True,
                }
            )
        return kwargs

    def get_object(self):
        # Only get the User record for the user making the request
        return User.objects.get(username=self.request.user.username)


class UserSearchView(LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView):
    model = User
    # These next two lines tell the view to index lookups by username
    slug_field = "username"
    slug_url_kwarg = "username"
    context_object_name = "user"
    ordering = ["-badge_number"]
    table_class = UserTable
    template_name = "users/user_search.html"

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        if request.GET.get("csv", "False").lower() == "download csv":
            response = HttpResponse(content_type="text/csv")
            context = self.get_context_data()
            time_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ThetaTauSearchExport_{time_name}.csv"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            writer = csv.writer(response)
            for row in context["table"].as_values():
                writer.writerow(row)
        return response

    def get_queryset(self):
        queryset = User.objects.none()
        q = self.request.GET.get("q", "")
        zip = self.request.GET.get("zip", "")
        if q:
            queryset = watson.filter(User, q)
        if zip:
            distance = self.request.GET.get("dist", "1")
            addressess = isinradius(zip, distance)
            user_pks = [user.pk for address in addressess for user in address.user_set.all()]
            if not queryset:
                queryset = User.objects
            queryset = queryset.filter(pk__in=user_pks)
        return queryset

    def get_table_kwargs(self):
        return {
            "chapter": True,
            "extra_info": True,
            "natoff": self.request.user.is_national_officer() and not self.request.user.natoff_hidden,
            "admin": self.request.user.is_superuser,
        }


class ExportActiveMixin:
    def export_chapter_actives(self, request, queryset):
        time_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"ThetaTauActiveExport_{time_name}.zip"
        zip_io = BytesIO()
        qs = self.model._default_manager.filter(
            current_status__in=[
                "active",
                "activepend",
                "alumnipend",
                "away",
                "activeCC",
            ],
        )
        with zipfile.ZipFile(zip_io, "w") as zf:
            active_chapters = Chapter.objects.exclude(active=False)
            total = active_chapters.count()
            for count, chapter in enumerate(active_chapters):
                print(f"Export {chapter} {count+1}/{total}")
                members = qs.filter(chapter=chapter)
                table = UserTable(data=members, chapter=True)
                writer_file = StringIO()
                writer = csv.writer(writer_file)
                writer.writerows(table.as_values())
                zf.writestr(
                    f"{chapter}_{chapter.school}_activeexport_{time_name}.csv",
                    writer_file.getvalue(),
                )
        response = HttpResponse(zip_io.getvalue(), content_type="application/x-zip-compressed")
        response["Cache-Control"] = "no-cache"
        response["Content-Disposition"] = f"attachment; filename={zip_filename}"
        return response

    export_chapter_actives.short_description = "Export Chapter Actives"


class UserListView(LoginRequiredMixin, PagedFilteredTableView):
    model = User
    # These next two lines tell the view to index lookups by username
    slug_field = "username"
    slug_url_kwarg = "username"
    context_object_name = "user"
    ordering = ["-badge_number"]
    table_class = UserTable
    filter_class = UserListFilter
    formhelper_class = UserListFormHelper
    template_name = "users/user_list.html"

    def get(self, request, *args, **kwargs):
        csv_action = request.GET.get("csv", "False").lower() == "download csv"
        email_action = request.GET.get("email", "False").lower() == "email all"
        if (csv_action or email_action) and not getattr(request, "is_officer", False):
            messages.add_message(
                self.request,
                messages.ERROR,
                "Only chapter officers can email members through this method.",
            )
            return super().get(request, *args, **kwargs)
        if csv_action:
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            response = HttpResponse(content_type="text/csv")
            time_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ThetaTauMemberExport_{time_name}.csv"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            writer = csv.writer(response)
            if self.object_list:
                table = context["table"]
                writer.writerows(table.as_values())
                return response
            else:
                messages.add_message(
                    self.request,
                    messages.ERROR,
                    "All members are filtered! Clear or change filter.",
                )
        elif email_action:
            self.object_list = self.get_queryset()
            total = len(self.object_list)
            if self.object_list:
                for user in self.object_list:
                    if user.email:
                        MemberInfoUpdate(user, request.user).send()
                messages.add_message(
                    self.request,
                    messages.INFO,
                    f"Email sent to {total} members.",
                )
            else:
                messages.add_message(
                    self.request,
                    messages.ERROR,
                    "All members are filtered! Clear or change filter.",
                )
        return super().get(request, *args, **kwargs)

    def get_queryset(self, **kwargs):
        qs = self.model._default_manager.filter(chapter=self.request.user.current_chapter)
        ordering = self.get_ordering()
        if ordering:
            if isinstance(ordering, str):
                ordering = (ordering,)
                qs = qs.order_by(*ordering)
        if not self.request.user.chapter_officer():
            qs = qs.filter(
                current_status__in=[
                    "active",
                    "activepend",
                    "alumnipend",
                    "activeCC",
                    "away",
                    "pnm",
                ],
            )
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        if not request_get:
            # Create a mutable QueryDict object, default is immutable
            request_get = QueryDict(mutable=True)
            request_get.setlist(
                "current_status",
                [
                    "active",
                    "pnm",
                    "activepend",
                    "alumnipend",
                ],
            )
        if not cancel:
            current_status = request_get.get("current_status", "")
            if current_status == "":
                request_get.setlist(
                    "current_status",
                    [
                        "active",
                        "pnm",
                        "activepend",
                        "alumnipend",
                    ],
                )
        qs = annotate_rmp_status(qs)
        self.filter = self.filter_class(request_get, queryset=qs, request=self.request)
        self.filter.form.helper = self.formhelper_class(rmp_complete=True)
        return self.filter.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        natoff = False
        if self.request.user.is_national_officer():
            natoff = True
        admin = self.request.user.is_superuser
        table = UserTable(data=self.object_list, natoff=natoff, admin=admin, rmp=True)
        table.exclude = ("current_roles",)
        RequestConfig(self.request, paginate={"per_page": 30}).configure(table)
        context["table"] = table
        return context


class PasswordResetFormNotActive(PasswordResetForm):
    def get_users(self, email):
        return [User.objects.filter(email=email).first()]

    def save(
        self,
        domain_override=None,
        subject_template_name="registration/password_reset_subject.txt",
        email_template_name="registration/password_reset_email.html",
        use_https=False,
        token_generator=default_token_generator,
        from_email=None,
        request=None,
        html_email_template_name=None,
        extra_email_context=None,
    ):
        """
        Generate a one-use only link for resetting password and send it to the
        user.
        """
        email = self.cleaned_data.get("email", None)
        if email is None:
            if request:
                messages.add_message(
                    request,
                    messages.ERROR,
                    "Please provide email",
                )
            return
        for user in self.get_users(email):
            if not domain_override:
                current_site = get_current_site(request)
                site_name = current_site.name
                domain = current_site.domain
            else:
                site_name = domain = domain_override
            user_email = user.email
            context = {
                "email": user_email,
                "domain": domain,
                "site_name": site_name,
                "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                "user": user,
                "token": token_generator.make_token(user),
                "protocol": "https" if use_https else "http",
                **(extra_email_context or {}),
            }
            self.send_mail(
                subject_template_name,
                email_template_name,
                context,
                from_email,
                user_email,
                html_email_template_name=html_email_template_name,
            )
            user_email_school = user.email_school
            if user_email_school != user_email:
                context = {
                    "email": user_email_school,
                    "domain": domain,
                    "site_name": site_name,
                    "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                    "user": user,
                    "token": token_generator.make_token(user),
                    "protocol": "https" if use_https else "http",
                    **(extra_email_context or {}),
                }
                self.send_mail(
                    subject_template_name,
                    email_template_name,
                    context,
                    from_email,
                    user_email_school,
                    html_email_template_name=html_email_template_name,
                )


class CaptchaLoginView(LoginView):
    form_class = CaptchaLoginForm


class UserLookupLoginView(CaptchaLoginView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["lookup_form"] = UserLookupForm()
        return context


def mask_email(email):
    """Return an email masked as ``f****l@domain.tld``: first + '****' + last of
    the local part, then the unaltered ``@domain`` so users can recognise which
    inbox to check without exposing the full address."""
    if not email or "@" not in email:
        return ""
    local, _, domain = email.partition("@")
    if len(local) < 2:
        return f"{local}****@{domain}"
    return f"{local[0]}****{local[-1]}@{domain}"


class UserBadgeLookupView(FormView):
    """Login-page badge-number lookup: find the user by university + badge,
    trigger a password-reset email via PasswordResetFormNotActive, and report
    back on the login page with a masked email address."""

    form_class = UserLookupForm
    http_method_names = ["post"]

    def form_valid(self, form):
        chapter_id = form.cleaned_data["university"]
        badge = form.cleaned_data["badge_number"]
        qs = User.objects.filter(badge_number=badge)
        if chapter_id and chapter_id != "-1":
            qs = qs.filter(chapter_id=chapter_id)
        user = qs.first()
        if user is None:
            messages.add_message(
                self.request,
                messages.ERROR,
                f"No member was found with badge number {badge}. "
                "Double-check the university and badge number, or contact cmt@thetatau.org.",
            )
            return HttpResponseRedirect(reverse("account_login"))
        if not user.email:
            messages.add_message(
                self.request,
                messages.ERROR,
                "Member found but no email is on file. Please contact cmt@thetatau.org.",
            )
            return HttpResponseRedirect(reverse("account_login"))
        reset = PasswordResetFormNotActive({"email": user.email})
        if reset.is_valid():
            reset.save(
                request=self.request,
                use_https=self.request.is_secure(),
            )
        messages.add_message(
            self.request,
            messages.INFO,
            f"Password reset instructions were sent to {mask_email(user.email)}. "
            "Check your inbox (and spam folder).",
        )
        return HttpResponseRedirect(reverse("account_login"))

    def form_invalid(self, form):
        for err in form.non_field_errors():
            messages.add_message(self.request, messages.ERROR, err)
        for field, errs in form.errors.items():
            if field == "__all__":
                continue
            for err in errs:
                messages.add_message(self.request, messages.ERROR, f"{field}: {err}")
        return HttpResponseRedirect(reverse("account_login"))


class UserLookupSearchView(FormView):
    form_class = UserLookupSearchForm
    template_name = "users/lookup_search.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.request.session["user"] = None
        return kwargs

    def form_valid(self, form):
        school_id = form.cleaned_data["university"]
        chapter = None
        if school_id != "-1":
            chapter = Chapter.objects.get(pk=school_id)
        search = ""
        for search_term, value in form.cleaned_data.items():
            if search_term in ["university", "captcha"] or not value:
                continue
            search = f"{search} {value}"
        if chapter:
            users_chapter = User.objects.filter(chapter=chapter)
            chapter_name = chapter.full_name
        else:
            users_chapter = User.objects.all()
            chapter_name = "Unknown"
        users = watson.filter(users_chapter, search)
        total = users.count()
        if total > 5:
            messages.add_message(
                self.request,
                messages.ERROR,
                f"Found {total} members, please provide more details, searched {search} at {chapter_name}",
            )
            response = super().form_invalid(form)
        elif total == 0:
            messages.add_message(
                self.request,
                messages.ERROR,
                f"Found {total} members, maybe provide LESS details, searched {search} at {chapter_name}",
            )
            response = super().form_invalid(form)
        else:
            self.request.session["users"] = list(users.values_list("id", flat=True))
            response = super().form_valid(form)
        return response

    def get_success_url(self):
        return reverse("users:lookup_select")


class UserLookupSelectView(FormView):
    form_class = UserLookupSelectForm
    template_name = "users/lookup_select.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        users = self.request.session.get("users", None)
        if users:
            users = User.objects.filter(id__in=users)
            kwargs["users"] = users
        self.request.session["user"] = None
        return kwargs

    def form_valid(self, form):
        user = form.cleaned_data["users"]
        if user.is_officer:
            messages.add_message(
                self.request,
                messages.ERROR,
                f"Officers must login to update member info. {user} is: {user.current_roles}",
            )
            return HttpResponseRedirect(reverse("users:lookup_search"))
        self.request.session["user"] = user.id
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("users:update")


def hide_email(email):
    if "@" in email:
        email_start, email_domain = email.split("@")
        email_start = email_start[:4]
        return "".join([email_start, "****@", email_domain])
    else:
        # Likely the email is empty
        return ""


class UserLookupUpdateView(FormView):
    form_class = UserUpdateForm
    template_name = "users/update.html"

    def get(self, request, *args, **kwargs):
        user = self.request.session.get("user", None)
        if user:
            user = User.objects.get(id=user)
            if user.is_officer:
                messages.add_message(
                    self.request,
                    messages.ERROR,
                    f"Officers must login to update member info. {user} is: {user.current_roles}",
                )
                return HttpResponseRedirect(reverse("users:lookup_search"))
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        updated = dict()
        user = self.request.session.get("user", None)
        if user:
            user = User.objects.get(id=user)
        if user is None:
            # When no user, all supplied values are updates
            updated = {key: value for key, value in form.cleaned_data.items() if value and key != "captcha"}
        else:
            # When there is an actual user look for only updated values
            for key, value in form.cleaned_data.items():
                if value:
                    skip = ["school_name", "captcha", "major_other"]
                    if user and key not in skip and getattr(user, key) != value:
                        updated[key] = value
            if "major_other" in form.cleaned_data and form.cleaned_data["major_other"]:
                # Can't get current value, but need to use for update
                updated["major_other"] = form.cleaned_data["major_other"]
        if updated:
            messages.add_message(
                self.request,
                messages.INFO,
                f"Information update member: {user} submitted: {updated}",
            )
            from .flows import MemberUpdateFlow

            MemberUpdateFlow.start.run(user=user, updated=updated)
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.session.get("user", None)
        user_info = dict()
        if user:
            user = User.objects.get(id=user)
            user_info["badge_number"] = user.badge_number
            user_info["title"] = user.get_title_display()
            user_info["first_name"] = user.first_name
            user_info["middle_name"] = user.middle_name
            user_info["last_name"] = user.last_name
            user_info["maiden_name"] = user.maiden_name
            user_info["preferred_pronouns"] = user.preferred_pronouns if user.preferred_pronouns else ""
            user_info["preferred_name"] = user.preferred_name if user.preferred_name else ""
            user_info["nickname"] = user.nickname
            user_info["suffix"] = user.suffix
            user_info["email"] = hide_email(user.email)
            user_info["email_school"] = hide_email(user.email_school)
            address = "Unknown"
            if user.address:
                if user.address.locality:
                    zipcode = user.address.locality.postal_code
                    address = f"XXXXXXXX {zipcode}"
            user_info["address"] = address if address else "Unknown"
            user_info["birth_date"] = (
                user.birth_date.month if user.birth_date != datetime.date(1904, 10, 15) else "Unknown"
            )
            user_info["phone_number"] = f"XXXXXX{user.phone_number[-4:]}" if user.phone_number else "Unknown"
            user_info["graduation_year"] = user.graduation_year if user.graduation_year else "Unknown"
            user_info["degree"] = user.get_degree_display()
            user_info["major"] = user.major if user.major else "Unknown"
            user_info["employer"] = user.employer if user.employer else "Unknown"
            user_info["employer_position"] = user.employer_position if user.employer_position else "Unknown"
            user_info["employer_address"] = user.employer_address if user.employer_address else "Unknown"
            user_info["school_name"] = user.chapter.school
            user_info["unsubscribe_paper_gear"] = user.unsubscribe_paper_gear
            user_info["unsubscribe_email"] = user.unsubscribe_email
            context["form"].fields["school_name"].initial = user.chapter
            context["form"].fields["school_name"].widget = forms.HiddenInput()
        else:
            # There is no user automatically added se we need some mandatory fields
            mandatory = [
                "school_name",
                "email",
                "graduation_year",
                "first_name",
                "last_name",
            ]
            for field in mandatory:
                context["form"].fields[field].required = True
        context["user"] = user_info
        return context

    def get_success_url(self):
        return reverse("users:update")


class UserUpdateDirectReview(UpdateView):
    model = MemberUpdate
    template_name = "users/update_review.html"
    fields = [
        "approved",
    ]

    def form_valid(self, form):
        """If the form is valid, save the associated model."""
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data()
        from .flows import MemberUpdateFlow

        try:
            self.object.get_task(MemberUpdateFlow.delay)
        except viewflow.models.Task.DoesNotExist:
            complete = True
        else:
            complete = False
        context_data["complete"] = complete
        user_info = dict()
        if not complete:
            user_info = MemberUpdateFlow.get_updated(self.object, perform_update=False)
            if "email" in user_info:
                user_info["email"] = hide_email(user_info["email"])
            if "email_school" in user_info:
                user_info["email_school"] = hide_email(user_info["email_school"])
            if "address" in user_info:
                address = "XXXXXXXX"
                address_obj = user_info["address"]
                if address_obj.locality:
                    zipcode = address_obj.locality.postal_code
                    address = f"XXXXXXXX {zipcode}"
                user_info["address"] = address if address else "Unknown"
            if "birth_date" in user_info:
                user_info["birth_date"] = user_info["birth_date"].month
            if "phone_number" in user_info:
                user_info["phone_number"] = f"XXXXXX{user_info['phone_number'][-4:]}"
            out_info = dict()
            for key, value in user_info.items():
                new_key = key.replace("_", " ").title()
                out_info[new_key] = value
            user_info = out_info
        context_data["user_info"] = user_info
        return context_data

    def get_success_url(self):
        """Detect the submit button used and act accordingly"""
        from .flows import MemberUpdateFlow

        if "deny" in self.request.POST:
            self.object.approved = False
            state = "denied"
        else:
            self.object.approved = True
            state = "approved"
        self.object.save()
        messages.add_message(
            self.request,
            messages.INFO,
            f"Member update was successfully {state}",
        )
        MemberUpdateFlow.continue_process(self.object.pk)
        return reverse("users:update_review", kwargs={"pk": self.object.pk})


class UserAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated or not self.request.user.is_officer_group:
            return User.objects.none()
        # users:autocomplete comes here
        chapter = self.forwarded.get("chapter", "true")
        actives = self.forwarded.get("actives", "false")
        alumni = self.forwarded.get("alumni", "false")
        exclude_self = self.forwarded.get("exclude_self", "false")
        qs = User.objects.all()
        if chapter == "true":
            chapter = self.request.user.current_chapter
            if actives == "true":
                qs = chapter.active_actives()
            elif alumni == "true":
                qs = chapter.alumni()
            else:
                qs = qs.filter(chapter=chapter)
        if exclude_self == "true":
            qs = qs.exclude(pk=self.request.user.pk)
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs.order_by("name")


class UserAlterView(LoginRequiredMixin, NatOfficerRequiredMixin, FormView):
    model = UserAlter
    form_class = UserAlterForm
    template_name = "users/lookup.html"  # dummy template should not be seen

    def check_membership(self, groups):
        # The chapter/role switcher must stay usable even while national-officer
        # functionality is hidden (that is how a National Officer switches to
        # viewing the site as a chapter officer), so gate on *raw* group
        # membership rather than the hide-aware NatOfficerRequiredMixin check.
        return self.request.user.in_national_officer_group

    def get_success_url(self):
        redirect_to = self.request.POST.get("next", "")
        url_is_safe = url_has_allowed_host_and_scheme(redirect_to, allowed_hosts=None)
        if self.request.user.is_anonymous:
            return reverse("home")
        if redirect_to and url_is_safe and "chapters" not in redirect_to:
            return redirect_to
        return reverse("chapters:detail", kwargs={"slug": self.request.user.current_chapter.slug})

    def form_valid(self, form):
        user = self.request.user
        form.instance.user = user
        try:
            instance = UserAlter.objects.filter(user=user).first()
        except UserAlter.DoesNotExist:
            instance = None
        reset = self.request.POST.get("alter-action") == "Reset"
        if reset:
            form.instance.chapter = self.request.user.chapter  # This should remain origin chapter
            form.instance.role = None
        form.is_valid()
        if instance:
            instance.chapter = form.instance.chapter
            instance.role = form.instance.role
            if reset:
                # Reset returns the National Officer to the full national view.
                instance.hide_natoff = False
            instance.save()
        else:
            form.save()
        return super().form_valid(form)


class ToggleNatoffView(LoginRequiredMixin, View):
    """Flip the National Officer "view as member" toggle (``UserAlter.hide_natoff``).

    Gated on *raw* ``natoff``-group membership (not :class:`NatOfficerRequiredMixin`,
    which now treats hidden officers as non-members) so the National Officer can
    always switch back while national-officer functionality is hidden.
    """

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        user = request.user
        if not user.in_national_officer_group:
            return HttpResponseRedirect(reverse("home"))
        instance = UserAlter.objects.filter(user=user).first()
        if instance is None:
            instance = UserAlter(user=user, chapter=user.chapter, role=None)
        instance.hide_natoff = not instance.hide_natoff
        instance.save()
        if instance.hide_natoff:
            messages.info(
                request,
                "National officer functionality is now hidden — you are viewing the "
                "site as a member. Use the account menu to show it again.",
            )
        else:
            messages.info(request, "National officer functionality restored.")
        redirect_to = request.POST.get("next", "")
        if redirect_to and url_has_allowed_host_and_scheme(redirect_to, allowed_hosts=None):
            return HttpResponseRedirect(redirect_to)
        return HttpResponseRedirect(reverse("home"))


class UserGPAFormSetView(LoginRequiredMixin, OfficerRequiredMixin, FormSetView):
    template_name = "users/gpa_formset.html"
    form_class = UserGPAForm
    factory_kwargs = {"extra": 0}
    success_url = "users:gpas"

    def get_success_url(self):
        return self.request.get_full_path()

    def get_initial(self):
        # return whatever you'd normally use as the initial data for your formset.
        users_with_gpas = self.request.user.current_chapter.gpas()
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        self.filter = UserListFilterBase(
            request_get,
            queryset=self.request.user.current_chapter.current_members(),
            request=self.request,
        )
        all_members = self.filter.qs
        initials = []
        for user in all_members:
            init_dict = {"user": user.name}
            if user in users_with_gpas:
                user_gpas = user.gpas.filter(year__gte=BIENNIUM_YEARS[0]).values("year", "term", "gpa")
                if user_gpas:
                    for i in range(4):
                        semester = "sp" if i % 2 else "fa"
                        year = BIENNIUM_YEARS[i]
                        try:
                            gpa = user_gpas.get(term=semester, year=year)
                        except UserSemesterGPA.DoesNotExist:
                            continue
                        else:
                            init_dict[f"gpa{i + 1}"] = gpa["gpa"]
            for key in ["gpa1", "gpa2", "gpa3", "gpa4"]:
                if key not in init_dict:
                    init_dict[key] = 0.0
            initials.append(init_dict)
        return initials

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        headers = ["Member Name"]
        for i in range(4):
            year = BIENNIUM_YEARS[i]
            semester = "Spring" if i % 2 else "Fall"
            headers.append(f"{semester} {year}")
        context["table_headers"] = headers
        self.filter.form.helper = UserListFormHelper()
        context["filter"] = self.filter
        return context

    def formset_valid(self, formset):
        for form in formset:
            if form.has_changed():
                form.save()
        return super().formset_valid(formset)


class UserServiceFormSetView(LoginRequiredMixin, FormSetView):
    template_name = "users/service_formset.html"
    form_class = UserServiceForm
    factory_kwargs = {"extra": 0}
    success_url = "users:service"

    def get_success_url(self):
        return self.request.get_full_path()

    def get_initial(self):
        # return whatever you'd normally use as the initial data for your formset.
        users_with_service = self.request.user.current_chapter.service_hours()
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        self.filter = UserListFilterBase(
            request_get,
            queryset=self.request.user.current_chapter.current_members(),
            request=self.request,
        )
        all_members = self.filter.qs
        initials = []
        for user in all_members:
            init_dict = {"user": user.name}
            if user in users_with_service:
                user_service_hours = user.service_hours.filter(year__gte=BIENNIUM_YEARS[0]).values(
                    "year", "term", "service_hours"
                )
                if user_service_hours:
                    for i in range(4):
                        semester = "sp" if i % 2 else "fa"
                        year = BIENNIUM_YEARS[i]
                        try:
                            service = user_service_hours.get(term=semester, year=year)
                        except UserSemesterServiceHours.DoesNotExist:
                            continue
                        else:
                            init_dict[f"service{i + 1}"] = service["service_hours"]
            for key in ["service1", "service2", "service3", "service4"]:
                if key not in init_dict:
                    init_dict[key] = 0.0
            initials.append(init_dict)
        return initials

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        headers = ["Member Name"]
        for i in range(4):
            year = BIENNIUM_YEARS[i]
            semester = "Spring" if i % 2 else "Fall"
            headers.append(f"{semester} {year}")
        context["table_headers"] = headers
        self.filter.form.helper = UserListFormHelper()
        context["filter"] = self.filter
        return context

    def formset_valid(self, formset):
        for form in formset:
            if form.has_changed():
                form.save()
        return super().formset_valid(formset)


class UserOrgsFormSetView(LoginRequiredMixin, ModelFormSetView):
    template_name = "users/orgs_formset.html"
    model = UserOrgParticipate
    form_class = UserOrgForm
    factory_kwargs = {"extra": 0, "can_delete": True}

    def get_success_url(self):
        return self.request.get_full_path()

    def get_factory_kwargs(self):
        kwargs = super().get_factory_kwargs()
        if self.get_queryset():
            kwargs["extra"] = 0
        else:
            kwargs["extra"] = 1
        return kwargs

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests, instantiating a formset instance with the passed
        POST variables and then checked for validity.
        """
        self.object_list = self.get_queryset()
        formset = self.construct_formset()
        if formset.is_valid():
            return self.formset_valid(formset)
        else:
            return self.formset_invalid(formset)

    def get_formset(self):
        actives = self.request.user.current_chapter.actives()
        formset = super().get_formset()
        formset.form.base_fields["user"].queryset = actives
        return formset

    def get_queryset(self):
        users_with_orgs = self.request.user.current_chapter.orgs()
        orgs = UserOrgParticipate.objects.filter(user__in=users_with_orgs)
        return orgs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        formset = kwargs.get("formset", None)
        if formset is None:
            formset = self.construct_formset()
        actives = self.request.user.current_chapter.actives()
        formset.form.base_fields["user"].queryset = actives
        context["formset"] = formset
        context["input"] = Submit("action", "Submit")
        return context
