from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.forms import PasswordResetForm
from django.urls import reverse
from django.contrib import messages
from django.views.generic import DetailView, RedirectView, UpdateView, FormView
from core.views import PagedFilteredTableView, RequestConfig
from .models import User
from .tables import UserTable
from .filters import UserListFilter
from .forms import UserListFormHelper, UserLookupForm
from chapters.models import Chapter


class UserDetailView(LoginRequiredMixin, DetailView):
    model = User
    # These next two lines tell the view to index lookups by username
    slug_field = 'username'
    slug_url_kwarg = 'username'


class UserRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse('users:detail',
                       kwargs={'username': self.request.user.username})


class UserUpdateView(LoginRequiredMixin, UpdateView):

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


class UserListView(LoginRequiredMixin, PagedFilteredTableView):
    model = User
    # These next two lines tell the view to index lookups by username
    slug_field = 'username'
    slug_url_kwarg = 'username'
    context_object_name = 'user'
    ordering = ['-badge_number']
    table_class = UserTable
    filter_class = UserListFilter
    formhelper_class = UserListFormHelper

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(chapter=self.request.user.chapter)


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
