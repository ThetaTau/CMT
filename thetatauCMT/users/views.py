from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.forms import PasswordResetForm
from django.db import models
from django.urls import reverse
from django.shortcuts import redirect
from django.utils.http import is_safe_url
from django.contrib import messages
from django.views.generic import DetailView, RedirectView, UpdateView, FormView
from core.views import PagedFilteredTableView, RequestConfig, OfficerMixin,\
    NatOfficerRequiredMixin
from core.models import TODAY_END, annotate_role_status, combine_annotations
from dal import autocomplete
from .models import User, UserAlterChapter
from .tables import UserTable
from .filters import UserListFilter
from .forms import UserListFormHelper, UserLookupForm, UserAlterForm
from chapters.models import Chapter


class UserDetailView(LoginRequiredMixin, OfficerMixin, DetailView):
    model = User
    # These next two lines tell the view to index lookups by username
    slug_field = 'username'
    slug_url_kwarg = 'username'


class UserRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse('users:detail',
                       kwargs={'username': self.request.user.username})


class UserUpdateView(LoginRequiredMixin, OfficerMixin, UpdateView):

    fields = ['name', 'chapter', 'major', 'graduation_year', 'phone_number', 'address']

    # we already imported User in the view code above, remember?
    model = User

    # send the user back to their own page after a successful update
    def get_success_url(self):
        return reverse('users:detail',
                       kwargs={'username': self.request.user.username})

    def get_object(self):
        # Only get the User record for the user making the request
        return User.objects.get(username=self.request.user.username)


class UserListView(LoginRequiredMixin, OfficerMixin, PagedFilteredTableView):
    model = User
    # These next two lines tell the view to index lookups by username
    slug_field = 'username'
    slug_url_kwarg = 'username'
    context_object_name = 'user'
    ordering = ['-badge_number']
    table_class = UserTable
    filter_class = UserListFilter
    formhelper_class = UserListFormHelper
    template_name = "users/user_list.html"

    def get_queryset(self):
        qs = self.model._default_manager.all()
        ordering = self.get_ordering()
        if ordering:
            if isinstance(ordering, str):
                ordering = (ordering,)
                qs = qs.order_by(*ordering)
        members = annotate_role_status(qs.filter(
            chapter=self.request.user.current_chapter,
            status__status="active",
            status__start__lte=TODAY_END,
            status__end__gte=TODAY_END), combine=False)
        pledges = annotate_role_status(qs.filter(
            chapter=self.request.user.current_chapter,
            status__status="pnm",
            status__start__lte=TODAY_END,
            status__end__gte=TODAY_END
            ), combine=False)
        qs = members | pledges
        self.filter = self.filter_class(self.request.GET,
                                        queryset=qs)
        self.filter.form.helper = self.formhelper_class()
        qs = combine_annotations(self.filter.qs)
        return qs


class PasswordResetFormNotActive(PasswordResetForm):
    def get_users(self, email):
        return [User.objects.get(email=email)]


class UserLookupView(FormView):
    form_class = UserLookupForm
    template_name = "users/lookup.html"

    def form_valid(self, form):
        chapter = Chapter.objects.get(pk=form.cleaned_data['university'])
        badge_number = form.cleaned_data['badge_number']
        try:
            user = User.objects.get(user_id=f"{chapter.greek}{badge_number}")
        except User.DoesNotExist:
            chapter_name = chapter.name
            messages.add_message(
                self.request, messages.ERROR,
                f"No user/email associated with chapter: {chapter_name} and badge number: {badge_number}")
        else:
            orig_email = user.email
            email = self.hide_email(orig_email)
            messages.add_message(
                self.request, messages.INFO,
                f"Email for account is: {email}")
            form = PasswordResetFormNotActive({'email': orig_email})
            # This does not work because not active user
            # form = PasswordResetForm({'email': orig_email})
            form.is_valid()
            form.save()
        return super().form_valid(form)

    def hide_email(self, email):
        email_start, email_domain = email.split("@")
        email_start = email_start[:4]
        return ''.join([email_start, "****@", email_domain])

    def get_success_url(self):
        return reverse('users:lookup')


class UserAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if (not self.request.user.is_authenticated or
                not self.request.user.is_officer_group()):
            return User.objects.none()
        qs = User.objects.filter(chapter=self.request.user.current_chapter)
        if self.q:
            qs = qs.filter(name__istartswith=self.q)
        return qs


class UserAlterView(NatOfficerRequiredMixin, LoginRequiredMixin, FormView):
    model = UserAlterChapter
    form_class = UserAlterForm

    def get_success_url(self):
        redirect_to = self.request.POST.get('next', '')
        url_is_safe = is_safe_url(redirect_to)
        if redirect_to and url_is_safe:
            return redirect_to
        return reverse('chapters:detail',
                       kwargs={'slug': self.request.user.current_chapter.slug})

    def form_valid(self, form):
        user = self.request.user
        form.instance.user = user
        try:
            instance = UserAlterChapter.objects.get(user=user)
        except UserAlterChapter.DoesNotExist:
            instance = None
        if self.request.POST['alter-action'] == 'Reset':
            form.instance.chapter = self.request.user.chapter  # This should remain origin chapter
        form.is_valid()
        if instance:
            instance.chapter = form.instance.chapter
            instance.save()
        else:
            form.save()
        return super().form_valid(form)
