from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib.auth.views import PasswordResetConfirmView, PasswordResetCompleteView, PasswordResetView, \
    PasswordResetDoneView
from allauth.account.views import LogoutView
from django.contrib import admin
from django.views.generic import TemplateView, RedirectView
from material.frontend.urls import modules
from core.views import HomeView
from users.views import UserLookupLoginView
from django.views import defaults as default_views

urlpatterns = [
    url(r'^$', HomeView.as_view(template_name='pages/home.html'), name='home'),
    url(r'^about/$', TemplateView.as_view(template_name='pages/about.html'), name='about'),
    url(r'^help/$', TemplateView.as_view(template_name='pages/help.html'), name='help'),
    url(r'^electronic_terms/$', TemplateView.as_view(template_name='pages/electronic_terms.html'), name='electronic_terms'),
    url(r'^reset_password/confirm/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$',
        PasswordResetConfirmView.as_view(template_name='account/password_reset_confirm.html', ),
        name='password_reset_confirm'),
    url(r'^reset/done/$',
        PasswordResetCompleteView.as_view(template_name='account/password_reset_complete.html'),
        name='password_reset_complete',),
    url(r'^password_reset/$',
        PasswordResetView.as_view(template_name='account/password_reset.html'), name='password_reset',),
    url(r'^password_reset/done/$',
        PasswordResetDoneView.as_view(template_name='account/password_reset_done.html'), name='password_reset_done',),
    # Django Admin, use {% url 'admin:index' %}
    url(settings.ADMIN_URL, admin.site.urls),

    # User management
    url(r'^users/', include('users.urls', namespace='users')),
    url(r'^accounts/login/$', UserLookupLoginView.as_view(), name='login'),
    url(r'^accounts/logout/$', LogoutView.as_view(), name='logout'),
    url(r'^accounts/', include('allauth.urls')),

    # Your stuff: custom urls includes go here
    url(r'^$', RedirectView.as_view(url='/workflow/', permanent=False)),
    url(r'', include((modules.urls))),
    url(r'^regions/', include('regions.urls', namespace='regions')),
    url(r'^chapters/', include('chapters.urls', namespace='chapters')),
    url(r'^events/', include('events.urls', namespace='events')),
    url(r'^finances/', include('finances.urls', namespace='finances')),
    url(r'^scores/', include('scores.urls', namespace='scores')),
    url(r'^submissions/', include('submissions.urls', namespace='submissions')),
    url(r'^forms/', include('forms.urls', namespace='forms')),
    url(r'^tasks/', include('tasks.urls', namespace='tasks')),
    url(r'^ballots/', include('ballots.urls', namespace='ballots')),
    # url(r'^rmp/$',
    #     RedirectView.as_view(pattern_name='forms:rmp',
    #                          permanent=True)),
    url(r'^initiation/$',
        RedirectView.as_view(pattern_name='forms:initiation',
                             permanent=True)),
    url(r'^officer/$',
        RedirectView.as_view(pattern_name='forms:officer',
                             permanent=True)),
    url(r'^status/$',
        RedirectView.as_view(pattern_name='forms:status',
                             permanent=True)),
    url(r'^pledgeform/$',
        RedirectView.as_view(pattern_name='forms:pledgeform',
                             permanent=True)),
    url(r'^report/$',
        RedirectView.as_view(pattern_name='forms:report',
                             permanent=True)),
    url(r'^conventionform/$',
        RedirectView.as_view(pattern_name='viewflow:forms:convention:start',
                             permanent=True),
        name='conventionform'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        url(r'^400/$', default_views.bad_request, kwargs={'exception': Exception('Bad Request!')}),
        url(r'^403/$', default_views.permission_denied, kwargs={'exception': Exception('Permission Denied')}),
        url(r'^404/$', default_views.page_not_found, kwargs={'exception': Exception('Page not Found')}),
        url(r'^500/$', default_views.server_error),
    ]
    if 'debug_toolbar' in settings.INSTALLED_APPS:
        import debug_toolbar
        urlpatterns = [
            url(r'^__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns

if settings.DEBUG or 'staging' in settings.SETTINGS_MODULE:
    urlpatterns += [
        url(r'^herald/', include('herald.urls')),
    ]
