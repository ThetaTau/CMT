from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.conf import settings
from django.views.generic import DetailView, FormView, RedirectView, UpdateView
from core.views import PagedFilteredTableView, RequestConfig
from .tables import UserTable
from .filters import UserListFilter
from .forms import UserListFormHelper, InitiationForm


class UserDetailView(LoginRequiredMixin, DetailView):
    model = settings.AUTH_USER_MODEL
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
    model = settings.AUTH_USER_MODEL

    # send the user back to their own page after a successful update
    def get_success_url(self):
        return reverse('users:detail',
                       kwargs={'username': self.request.user.username})

    def get_object(self):
        # Only get the User record for the user making the request
        return User.objects.get(username=self.request.user.username)


class UserListView(LoginRequiredMixin, PagedFilteredTableView):
    model = settings.AUTH_USER_MODEL
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
