from django.urls import path

from . import views

app_name = "guides"
urlpatterns = [
    path("", views.CatalogView.as_view(), name="catalog"),
    path("role/", views.RoleGuideIndexView.as_view(), name="role-guides"),
    path("role/<slug:slug>/", views.RoleGuideDetailView.as_view(), name="role-guide"),
    path("ack/", views.AcknowledgeView.as_view(), name="acknowledge"),
    path("whats-new/", views.WhatsNewArchiveView.as_view(), name="whats-new"),
    path("whats-new/seen/", views.WhatsNewSeenView.as_view(), name="whats-new-seen"),
]
