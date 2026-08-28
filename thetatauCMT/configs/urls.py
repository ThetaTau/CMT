from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import include, re_path
from report_builder import views
from report_builder.api import views as api_views
from rest_framework import routers

from .report_views import SafeDownloadFileView, SafeGenerateReport

router = routers.DefaultRouter()
router.register(r"reports", api_views.ReportViewSet)
# For some reason there is a conflict with the basename report so need to override it
router.register(r"report", api_views.ReportNestedViewSet, basename="report-nested")
router.register(r"formats", api_views.FormatViewSet)
router.register(r"filterfields", api_views.FilterFieldViewSet)
router.register(r"contenttypes", api_views.ContentTypeViewSet)

urlpatterns = [
    re_path(
        r"^report/(?P<pk>\d+)/download_file/$",
        SafeDownloadFileView.as_view(),
        name="report_download_file",
    ),
    re_path(
        r"^report/(?P<pk>\d+)/download_file/(?P<filetype>.+)/$",
        SafeDownloadFileView.as_view(),
        name="report_download_file",
    ),
    re_path(
        r"^report/(?P<pk>\d+)/check_status/(?P<task_id>.+)/$",
        views.check_status,
        name="report_check_status",
    ),
    re_path(r"^report/(?P<pk>\d+)/add_star/$", views.ajax_add_star, name="ajax_add_star"),
    re_path(
        r"^report/(?P<pk>\d+)/create_copy/$",
        views.create_copy,
        name="report_builder_create_copy",
    ),
    re_path(r"^export_to_report/$", views.ExportToReport.as_view(), name="export_to_report"),
    re_path(r"^api/", include(router.urls)),
    re_path(r"^api/config/", api_views.ConfigView.as_view()),
    re_path(r"^api/api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    re_path(
        r"^api/related_fields",
        staff_member_required(api_views.RelatedFieldsView.as_view()),
        name="related_fields",
    ),
    re_path(
        r"^api/fields",
        staff_member_required(api_views.FieldsView.as_view()),
        name="fields",
    ),
    re_path(
        r"^api/report/(?P<report_id>\w+)/generate/",
        staff_member_required(SafeGenerateReport.as_view()),
        name="generate_report",
    ),
    re_path(
        r"^api/report/(?P<pk>\d+)/download_file/(?P<filetype>.+)/$",
        SafeDownloadFileView.as_view(),
        name="report_download_file",
    ),
    re_path(
        r"^api/report/(?P<pk>\d+)/check_status/(?P<task_id>.+)/$",
        views.check_status,
        name="report_check_status",
    ),
    re_path(
        r"^report/(?P<pk>\d+)/$",
        views.ReportSPAView.as_view(),
        name="report_update_view",
    ),
]

if not hasattr(settings, "REPORT_BUILDER_FRONTEND") or settings.REPORT_BUILDER_FRONTEND:
    urlpatterns += [
        re_path(
            r"^",
            staff_member_required(views.ReportSPAView.as_view()),
            name="report_builder",
        ),
    ]
