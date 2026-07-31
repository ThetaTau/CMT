from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "forms"
urlpatterns = [
    path("", views.FormLanding.as_view(), name="landing"),
    path(
        "pledge-pins/",
        view=views.PledgePinsView.as_view(),
        name="pledge_pins",
    ),
    path("bylaws", views.BylawsCreateView.as_view(), name="bylaws"),
    path("bylaws-list", views.BylawsListView.as_view(), name="bylaws_list"),
    path("audit/", view=views.AuditFormView.as_view(), name="audit"),
    path(
        "audit/<int:pk>/",
        view=views.AuditFormView.as_view(),
        name="audit_complete",
    ),
    path(
        "education-list/",
        view=views.HSEducationListView.as_view(),
        name="education_list",
    ),
    path(
        "convention-list/",
        view=views.ConventionListView.as_view(),
        name="convention_list",
    ),
    path("osm-list/", view=views.OSMListView.as_view(), name="osm_list"),
    path("audit-list/", view=views.AuditListView.as_view(), name="audit_list"),
    path("load-majors/", view=views.load_majors, name="ajax_load_majors"),
    path(
        "pledgeform_full/",
        view=views.PledgeFormView.as_view(),
        name="pledgeform",
    ),
    path(
        "pledgeform_alt/",
        view=views.PledgeFormView.as_view(),
        name="pledgeform-alt",
        kwargs={"alt_form": True},
    ),
    path(
        "pledge-program-list/",
        view=views.PledgeProgramListView.as_view(),
        name="pledge_program_list",
    ),
    path(
        "pledge-program-request-revision/<int:process_pk>/",
        view=views.pledge_program_request_revision,
        name="pledge_program_request_revision",
    ),
    path(
        "pledgeprogram-detail/<int:pk>/",
        view=views.PledgeProgramProcessDetailView.as_view(),
        name="pledge_program_detail",
    ),
    path(
        "alumniexclusion-detail/<int:pk>/",
        view=views.AlumniExclusionDetailView.as_view(),
        name="alumniexclusion_detail",
    ),
    path(
        "alumniexclusion-list/",
        view=views.AlumniExclusionListView.as_view(),
        name="alumniexclusion_list",
    ),
    path("initiation/", view=views.InitiationView.as_view(), name="initiation"),
    path(
        "initiation-selection/",
        view=views.InitDeplSelectView.as_view(),
        name="init_selection",
    ),
    path(
        "initiation-csv/<int:process_pk>/<str:csv_type>/",
        view=views.badge_shingle_init_csv,
        name="init_csv",
    ),
    path(
        "initiation-csv/<int:process_pk>/<str:csv_type>/<str:response_type>/",
        view=views.badge_shingle_init_csv,
        name="init_csv",
    ),
    path(
        "post-shingle/<int:process_pk>/",
        view=views.badge_shingle_post,
        name="shingle_post",
    ),
    path(
        "initiation-sync/<int:process_pk>/<int:invoice_number>/",
        view=views.badge_shingle_init_sync,
        name="init_sync",
    ),
    path(
        "pledge-csv/<int:process_pk>/<str:csv_type>/",
        view=views.pledge_process_csvs,
        name="pledge_csv",
    ),
    path(
        "pledge-sync/<int:process_pk>/<int:invoice_number>/",
        view=views.pledge_process_sync,
        name="pledge_sync",
    ),
    path(
        "status/",
        view=RedirectView.as_view(pattern_name="forms:landing", permanent=False),
        name="status",
    ),
    path(
        "status-selection/",
        view=RedirectView.as_view(pattern_name="forms:landing", permanent=False),
        name="status_selection",
    ),
    path(
        "status/history/<str:reason>/",
        view=views.StatusChangeHistoryListView.as_view(),
        name="status_history",
    ),
    path(
        "status/new/<str:reason>/",
        view=views.StatusChangeCreateView.as_view(),
        name="status_new",
    ),
    path(
        "status/graduate/select/",
        view=views.GraduateSelectView.as_view(),
        name="status_graduate_select",
    ),
    path(
        "status/graduate/fill/",
        view=views.GraduateFillView.as_view(),
        name="status_graduate",
    ),
    path(
        "otherschool-autocomplete/",
        view=views.OtherSchoolAutocomplete.as_view(create_field="name"),
        name="otherschool-autocomplete",
    ),
    path(
        "employer-autocomplete/",
        view=views.EmployerAutocomplete.as_view(create_field="name"),
        name="employer-autocomplete",
    ),
    path("officer/", view=views.RoleChangeListView.as_view(), name="officer"),
    path("officer/add/", view=views.RoleChangeCreateView.as_view(), name="officer_add"),
    path(
        "role/<int:pk>/edit/",
        view=views.RoleChangeEditView.as_view(),
        name="role_edit",
    ),
    path(
        "national-officer/",
        view=views.RoleChangeNationalListView.as_view(),
        name="natoff",
    ),
    path(
        "national-officer/add/",
        view=views.RoleChangeNationalCreateView.as_view(),
        name="natoff_add",
    ),
    path(
        "national-officer/contacts/",
        view=RedirectView.as_view(pattern_name="forms:natoff", permanent=False),
        name="national_officer_contacts",
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
        "roll-book-page/<int:pk>/",
        view=views.RollBookPDFView.as_view(),
        name="roll_book_page",
    ),
    path(
        "roll-book-download-all",
        view=views.download_all_rollbook,
        name="roll_book_download_all",
    ),
    path(
        "set-init-date/",
        view=views.set_init_date,
        name="set_init_date",
    ),
    path("rmp/", view=views.RiskManagementFormView.as_view(), name="rmp"),
    path(
        "rmp-complete/<int:pk>/",
        view=views.RiskManagementDetailView.as_view(),
        name="rmp_complete",
    ),
    path(
        "rmp-list/",
        view=views.RiskManagementListView.as_view(),
        name="rmp_list",
    ),
    path(
        "discipline/",
        RedirectView.as_view(pattern_name="viewflow:forms:disciplinaryprocess:start", permanent=True),
        name="discipline",
    ),
    path(
        "pledgeprogram/",
        RedirectView.as_view(pattern_name="viewflow:forms:pledgeprogramprocess:start", permanent=True),
        name="pledge_program",
    ),
    path(
        "discipline/outcome-pdf/<int:pk>/",
        view=views.DisciplinaryPDFTest.as_view(),
        name="discipline_pdftest",
    ),
    path(
        "discipline/download_files/<int:process_pk>/",
        view=views.disciplinary_process_files,
        name="discipline_download",
    ),
    path(
        "collection/",
        view=views.CollectionReferralFormView.as_view(),
        name="collection",
    ),
    path(
        "resignation/",
        RedirectView.as_view(pattern_name="viewflow:forms:resignation:start", permanent=True),
        name="resignation",
    ),
    path(
        "resignation-list/",
        view=views.ResignationListView.as_view(),
        name="resign_list",
    ),
    path(
        "ritual/",
        view=views.RitualProficiencyCreateView.as_view(),
        name="ritual_proficiency",
    ),
    path(
        "ritual/user-table/",
        view=views.RitualProficiencyUserTableView.as_view(),
        name="ritual_proficiency_user_table",
    ),
]
