from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import DetailView, ListView, RedirectView
from core.views import RequestConfig, OfficerMixin, OfficerRequiredMixin
from .models import Chapter
from users.tables import UserTable


class ChapterDetailView(LoginRequiredMixin, OfficerMixin, DetailView):
    model = Chapter
    # These next two lines tell the view to index lookups by username
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chapter_officers = self.object.get_current_officers()
        table = UserTable(data=chapter_officers)
        RequestConfig(self.request, paginate={'per_page': 100}).configure(table)
        context['table'] = table
        email_list = ', '.join([x.email for x in chapter_officers])
        context['email_list'] = email_list
        return context


class ChapterRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse('users:detail',
                       kwargs={'username': self.request.user.username})


class ChapterListView(OfficerRequiredMixin,
                      LoginRequiredMixin, OfficerMixin, ListView):
    model = Chapter
    # These next two lines tell the view to index lookups by username
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
