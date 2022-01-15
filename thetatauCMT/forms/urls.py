from django.urls import path
from django.conf.urls import url
from django.views.generic import RedirectView
from . import views


app_name = "forms"
urlpatterns = [
    path("", views.FormLanding.as_view(), name="landing"),
    url(regex=r"^audit/$", view=views.AuditFormView.as_view(), name="audit"),
    url(
        regex=r"^audit/(?P<pk>\d+)/$",
        view=views.AuditFormView.as_view(),
        name="audit_complete",
    ),
    url(regex=r"^report/$", view=views.ChapterInfoReportView.as_view(), name="report"),
    url(
        regex=r"^report-list/$",
        view=views.ChapterReportListView.as_view(),
        name="report_list",
    ),
    url(
        regex=r"^convention-list/$",
        view=views.ConventionListView.as_view(),
        name="convention_list",
    ),
    url(regex=r"^osm-list/$", view=views.OSMListView.as_view(), name="osm_list"),
    url(regex=r"^audit-list/$", view=views.AuditListView.as_view(), name="audit_list"),
    url(regex=r"^load-majors/$", view=views.load_majors, name="ajax_load_majors"),
    url(
        regex=r"^pledgeform_full/$",
        view=views.PledgeFormView.as_view(),
        name="pledgeform",
    ),
    url(
        regex=r"^pledgeform_alt/$",
        view=views.PledgeFormView.as_view(),
        name="pledgeform-alt",
        kwargs={"alt_form": True},
    ),
    url(
        regex=r"^pledge-program-list/$",
        view=views.PledgeProgramListView.as_view(),
        name="pledge_program_list",
    ),
    path(
        "pledgeprogram-detail/<int:pk>/",
        view=views.PledgeProgramProcessDetailView.as_view(),
        name="pledge_program_detail",
    ),
    url(regex=r"^initiation/$", view=views.InitiationView.as_view(), name="initiation"),
    url(
        regex=r"^initiation-selection/$",
        view=views.InitDeplSelectView.as_view(),
        name="init_selection",
    ),
    url(
        regex=r"^initiation-csv/(?P<process_pk>\d+)/(?P<csv_type>[\w.@+-]+)$",
        view=views.badge_shingle_init_csv,
        name="init_csv",
    ),
    url(
        regex=r"^initiation-sync/(?P<process_pk>\d+)/(?P<invoice_number>\d+)$",
        view=views.badge_shingle_init_sync,
        name="init_sync",
    ),
    url(
        regex=r"^pledge-csv/(?P<process_pk>\d+)/(?P<csv_type>[\w.@+-]+)$",
        view=views.pledge_process_csvs,
        name="pledge_csv",
    ),
    url(
        regex=r"^pledge-sync/(?P<process_pk>\d+)/(?P<invoice_number>\d+)$",
        view=views.pledge_process_sync,
        name="pledge_sync",
    ),
    url(regex=r"^status/$", view=views.StatusChangeView.as_view(), name="status"),
    url(
        regex=r"^status-selection/$",
        view=views.StatusChangeSelectView.as_view(),
        name="status_selection",
    ),
    url(regex=r"^officer/$", view=views.RoleChangeView.as_view(), name="officer"),
    url(
        regex=r"^national-officer/$",
        view=views.RoleChangeNationalView.as_view(),
        name="natoff",
    ),
    path(
        "bill-of-rights-pdf/<int:pk>/",
        view=views.BillOfRightsPDFView.as_view(),
        name="bill_of_rights_pdf",
    ),
    path(
        "bill-of-rights/<int:pk>/",
        view=views.BillOfRightsDetailView.as_view(),
        name="bill_of_rights",
    ),
    path(
        "rool-book-page/<int:pk>/",
        view=views.RollBookPDFView.as_view(),
        name="roll_book_page",
    ),
    url(regex=r"^rmp/$", view=views.RiskManagementFormView.as_view(), name="rmp"),
    url(
        regex=r"^rmp-complete/(?P<pk>\d+)/$",
        view=views.RiskManagementDetailView.as_view(),
        name="rmp_complete",
    ),
    url(
        regex=r"^rmp-list/$",
        view=views.RiskManagementListView.as_view(),
        name="rmp_list",
    ),
    url(
        r"^discipline/$",
        RedirectView.as_view(
            pattern_name="viewflow:forms:disciplinaryprocess:start", permanent=True
        ),
        name="discipline",
    ),
    url(
        r"^pledgeprogram/$",
        RedirectView.as_view(
            pattern_name="viewflow:forms:pledgeprogramprocess:start", permanent=True
        ),
        name="pledge_program",
    ),
    url(
        regex=r"^discipline/outcome-pdf/(?P<pk>\d+)/$",
        view=views.DisciplinaryPDFTest.as_view(),
        name="discipline_pdftest",
    ),
    url(
        regex=r"^discipline/download_files/(?P<process_pk>\d+)/$",
        view=views.disciplinary_process_files,
        name="discipline_download",
    ),
    url(
        regex=r"^collection/$",
        view=views.CollectionReferralFormView.as_view(),
        name="collection",
    ),
    url(
        r"^resignation/$",
        RedirectView.as_view(
            pattern_name="viewflow:forms:resignation:start", permanent=True
        ),
        name="resignation",
    ),
    url(
        regex=r"^resignation-list/$",
        view=views.ResignationListView.as_view(),
        name="resign_list",
    ),
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
