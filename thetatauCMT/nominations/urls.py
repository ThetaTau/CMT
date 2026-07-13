from django.urls import path

from . import views

app_name = "nominations"

urlpatterns = [
    # National-officer review list of all nominations.
    path("", views.NominationListView.as_view(), name="list"),
    # Tokenized, no-login nominee consent landing page.
    path("consent/<uuid:token>/", views.NomineeConsentView.as_view(), name="consent"),
    # Manual training mark-complete screen (TrainingAdministrator).
    path("training/<int:process_pk>/", views.TrainingView.as_view(), name="training"),
    # Appointment processing checklist (AppointmentProcessor).
    path("appointment/<int:process_pk>/", views.AppointmentView.as_view(), name="appointment"),
    # Central Office denial letter (CentralOffice).
    path("denial/<int:process_pk>/", views.DenialCentralOfficeView.as_view(), name="denial"),
]
