import csv
import datetime
import zipfile
from io import BytesIO, StringIO
from django import forms
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.http.request import QueryDict
from django.http.response import HttpResponseRedirect
from django.http import HttpResponse
from django.urls import reverse
from django.forms.models import modelformset_factory
from django.shortcuts import render, redirect
from django.utils.http import is_safe_url, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib import messages
from django.views.generic import RedirectView, FormView, DetailView, UpdateView
from crispy_forms.layout import Submit
from allauth.account.views import LoginView
from extra_views import FormSetView, ModelFormSetView
import viewflow
from watson import search as watson
from core.address import isinradius
from core.views import (
    PagedFilteredTableView,
    RequestConfig,
    NatOfficerRequiredMixin,
    OfficerRequiredMixin,
    LoginRequiredMixin,
    group_required,
)
from core.forms import MultiFormsView
from core.models import BIENNIUM_YEARS, annotate_rmp_status
from dal import autocomplete
from .models import (
    User,
    UserAlter,
    UserSemesterGPA,
    UserSemesterServiceHours,
    UserOrgParticipate,
    UserDemographic,
    MemberUpdate,
)
from .tables import UserTable
from .filters import UserListFilter, UserListFilterBase
from .forms import (
    CaptchaLoginForm,
    UserListFormHelper,
    UserLookupForm,
    UserAlterForm,
    UserGPAForm,
    UserForm,
    UserServiceForm,
    UserOrgForm,
    UserLookupSearchForm,
    UserLookupSelectForm,
    UserUpdateForm,
)
from .notifications import MemberInfoUpdate
from forms.forms import PledgeDemographicsForm
from chapters.models import Chapter
from submissions.tables import SubmissionTable
from notes.tables import UserNoteTable


class UserRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse("users:detail")


@group_required(["officer", "natoff"])
def user_verify(request):
    user_pk = request.GET.get("user_pk")
    user = User.objects.get(pk=user_pk)
    form = UserForm(instance=user, verify=True)
    return render(request, "users/user_verify_form.html", {"form": form})


class UserDetailView(LoginRequiredMixin, NatOfficerRequiredMixin, DetailView):
    slug_field = "username"
    slug_url_kwarg = "username"
    template_name = "users/user_info.html"
    model = User

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        table = UserNoteTable(self.object.notes.all())
        RequestConfig(self.request).configure(table)
        context["note_table"] = table
        return context


class UserDetailUpdateView(LoginRequiredMixin, MultiFormsView):
    template_name = "users/user_detail.html"
    form_classes = {
        "gpa": UserGPAForm,
        "service": UserServiceForm,
        "user": UserForm,
        "demo": PledgeDemographicsForm,
        "orgs": None,
    }

    # send the user back to their own page after a successful update
    def get_success_url(self, form_name=None):
        return reverse("users:detail")

    def get_gpa_initial(self):
        user = self.request.user
        initial = {"user": user.name}
        user_gpas = user.gpas.filter(year__gte=BIENNIUM_YEARS[0]).values(
            "year", "term", "gpa"
        )
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
        return HttpResponseRedirect(self.get_success_url() + "#member_gpaservice")

    def user_form_valid(self, form):
        if form.has_changed():
            form.save()
        return HttpResponseRedirect(self.get_success_url() + "#user")

    def demo_form_valid(self, form):
        if form.has_changed():
            user = self.request.user
            form.instance.user = user
            form.save()
        return HttpResponseRedirect(self.get_success_url() + "#demo")

    def orgs_form_valid(self, formset):
        if formset.has_changed():
            formset.save()
        return HttpResponseRedirect(self.get_success_url() + "#member_orgs")

    def create_orgs_form(self, **kwargs):
        orgs = self.request.user.orgs.all()
        extra = 0
        if not orgs:
            extra = 1
        factory = modelformset_factory(
            UserOrgParticipate, form=UserOrgForm, **{"can_delete": True, "extra": extra}
        )
        factory.form.base_fields["user"].queryset = User.objects.filter(
            pk=self.request.user.pk
        )
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
        user_service = user.service_hours.filter(year__gte=BIENNIUM_YEARS[0]).values(
            "year", "term", "service_hours"
        )
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


class UserSearchView(
    LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView
):
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
            user_pks = [
                user.pk for address in addressess for user in address.user_set.all()
            ]
            if not queryset:
                queryset = User.objects
            queryset = queryset.filter(pk__in=user_pks)
        return queryset

    def get_table_kwargs(self):
        return {
            "chapter": True,
            "extra_info": True,
            "natoff": self.request.user.is_national_officer(),
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
        response = HttpResponse(
            zip_io.getvalue(), content_type="application/x-zip-compressed"
        )
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
        if (csv_action or email_action) and not request.user.is_officer:
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
        qs = self.model._default_manager.filter(
            chapter=self.request.user.current_chapter
        )
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
                    f"Please provide email",
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
            users_chapter = User.objects.all()  # Natoff search of users
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
            updated = {
                key: value
                for key, value in form.cleaned_data.items()
                if value and key != "captcha"
            }
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
            user_info["preferred_pronouns"] = (
                user.preferred_pronouns if user.preferred_pronouns else ""
            )
            user_info["preferred_name"] = (
                user.preferred_name if user.preferred_name else ""
            )
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
                user.birth_date.month
                if user.birth_date != datetime.date(1904, 10, 15)
                else "Unknown"
            )
            user_info["phone_number"] = (
                f"XXXXXX{user.phone_number[-4:]}" if user.phone_number else "Unknown"
            )
            user_info["graduation_year"] = (
                user.graduation_year if user.graduation_year else "Unknown"
            )
            user_info["degree"] = user.get_degree_display()
            user_info["major"] = user.major if user.major else "Unknown"
            user_info["employer"] = user.employer if user.employer else "Unknown"
            user_info["employer_position"] = (
                user.employer_position if user.employer_position else "Unknown"
            )
            user_info["employer_address"] = (
                user.employer_address if user.employer_address else "Unknown"
            )
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
    # users:autocomplete This is the view
    def get_queryset(self):
        if (
            not self.request.user.is_authenticated
            or not self.request.user.is_officer_group
        ):
            return User.objects.none()
        chapter = self.forwarded.get("chapter", "true")
        actives = self.forwarded.get("actives", "false")
        alumni = self.forwarded.get("alumni", "false")
        qs = User.objects.all()
        if chapter == "true":
            chapter = self.request.user.current_chapter
            if actives == "true":
                qs = chapter.active_actives()
            elif alumni == "true":
                qs = chapter.alumni()
            else:
                qs = qs.filter(chapter=chapter)
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs.order_by("name")


class UserAlterView(LoginRequiredMixin, NatOfficerRequiredMixin, FormView):
    model = UserAlter
    form_class = UserAlterForm
    template_name = "users/lookup.html"  # dummy template should not be seen

    def get_success_url(self):
        redirect_to = self.request.POST.get("next", "")
        url_is_safe = is_safe_url(redirect_to, allowed_hosts=None)
        if self.request.user.is_anonymous:
            return reverse("home")
        if redirect_to and url_is_safe and "chapters" not in redirect_to:
            return redirect_to
        return reverse(
            "chapters:detail", kwargs={"slug": self.request.user.current_chapter.slug}
        )

    def form_valid(self, form):
        user = self.request.user
        form.instance.user = user
        try:
            instance = UserAlter.objects.filter(user=user).first()
        except UserAlter.DoesNotExist:
            instance = None
        if self.request.POST["alter-action"] == "Reset":
            form.instance.chapter = (
                self.request.user.chapter
            )  # This should remain origin chapter
            form.instance.role = None
        form.is_valid()
        if instance:
            instance.chapter = form.instance.chapter
            instance.role = form.instance.role
            instance.save()
        else:
            form.save()
        return super().form_valid(form)


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
                user_gpas = user.gpas.filter(year__gte=BIENNIUM_YEARS[0]).values(
                    "year", "term", "gpa"
                )
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
                user_service_hours = user.service_hours.filter(
                    year__gte=BIENNIUM_YEARS[0]
                ).values("year", "term", "service_hours")
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
