from django.conf.urls import url
from . import views


app_name = 'forms'
urlpatterns = [
    url(
        regex=r'^audit/$',
        view=views.AuditFormView.as_view(),
        name='audit'),
    url(
        regex=r'^audit/(?P<pk>\d+)/$',
        view=views.AuditFormView.as_view(),
        name='audit_complete'
    ),
    url(
        regex=r'^report/$',
        view=views.ChapterInfoReportView.as_view(),
        name='report'
    ),
    url(
        regex=r'^report-list/$',
        view=views.ChapterReportListView.as_view(),
        name='report_list'),
    url(
        regex=r'^convention-list/$',
        view=views.ConventionListView.as_view(),
        name='convention_list'),
    url(
        regex=r'^audit-list/$',
        view=views.AuditListView.as_view(),
        name='audit_list'),
    url(
        regex=r'^pledgeform/$',
        view=views.pledge_form,
        name='pledge_form'),
    url(
        regex=r'^load-majors/$',
        view=views.load_majors,
        name='ajax_load_majors'),
    url(
        regex=r'^pledgeform_full/$',
        view=views.PledgeFormView.as_view(),
        name='pledgeform'),
    url(
        regex=r'^pledgeprogram/$',
        view=views.PledgeProgramFormView.as_view(),
        name='pledge_program'),
    url(
        regex=r'^pledge-program-list/$',
        view=views.PledgeProgramListView.as_view(),
        name='pledge_program_list'),
    url(
        regex=r'^initiation/$',
        view=views.InitiationView.as_view(),
        name='initiation'
    ),
    url(
        regex=r'^initiation-selection/$',
        view=views.InitDeplSelectView.as_view(),
        name='init_selection'
    ),
    url(
        regex=r'^initiation-csv/(?P<process_pk>\d+)/(?P<csv_type>[\w.@+-]+)$',
        view=views.badge_shingle_init_csv,
        name='init_csv'
    ),
    url(
        regex=r'^pledge-csv/(?P<process_pk>\d+)/(?P<csv_type>[\w.@+-]+)$',
        view=views.pledge_process_csvs,
        name='pledge_csv'
    ),
    url(
        regex=r'^status/$',
        view=views.StatusChangeView.as_view(),
        name='status'
    ),
    url(
        regex=r'^status-selection/$',
        view=views.StatusChangeSelectView.as_view(),
        name='status_selection'
    ),
    url(
        regex=r'^officer/$',
        view=views.RoleChangeView.as_view(),
        name='officer'
    ),
    url(
        regex=r'^national-officer/$',
        view=views.RoleChangeNationalView.as_view(),
        name='natoff'
    ),
    url(
        regex=r'^rmp/$',
        view=views.RiskManagementFormView.as_view(),
        name='rmp'
    ),
    url(
        regex=r'^rmp-complete/(?P<pk>\d+)/$',
        view=views.RiskManagementDetailView.as_view(),
        name='rmp_complete'
    ),
    url(
        regex=r'^rmp-list/$',
        view=views.RiskManagementListView.as_view(),
        name='rmp_list'),
    # url(
    #     regex=r'^~status-change/$',
    #     view=views.StatusChangeView.as_view(),
    #     name='redirect'
    # ),
    # url(
    #     regex=r'^~/$',
    #     view=views.FormUpdateView.as_view(),
    #     name='update'
    # ),
    # url(
    #     regex=r'^(?P<year>d{4})/(?P<month>[0-9]{2})/(?P<day>[0-9]{2})/(?P<slug>[-w]+)/$',
    #     view=views.EventDetailView.as_view(),
    #     name='detail'
    # ),
]
