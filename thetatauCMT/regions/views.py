from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import DetailView, ListView, RedirectView
from core.views import OfficerMixin
from .models import Region


class RegionDetailView(LoginRequiredMixin, OfficerMixin, DetailView):
    model = Region
    # These next two lines tell the view to index lookups by username
    slug_field = 'slug'
    slug_url_kwarg = 'slug'


class RegionRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse('users:detail',
                       kwargs={'username': self.request.user.username})


class RegionListView(LoginRequiredMixin, OfficerMixin, ListView):
    model = Region
    # These next two lines tell the view to index lookups by username
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
