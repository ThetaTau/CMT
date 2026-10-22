from django.urls import path

from . import views

app_name = "support"

urlpatterns = [
    path("", views.CSSDirectoryView.as_view(), name="list"),
    path("my-chapters/", views.CSSLandingView.as_view(), name="my_chapters"),
    path("new/", views.CSSCreateView.as_view(), name="create"),
    path("<int:pk>/", views.CSSDetailView.as_view(), name="detail"),
    path("<int:pk>/assign/", views.CSSAssignView.as_view(), name="assign"),
    path("<int:pk>/remove/", views.CSSRemoveView.as_view(), name="remove"),
    path("assignments/<int:pk>/end/", views.CSSEndAssignmentView.as_view(), name="end"),
    path("switch/", views.CSSChapterSwitchView.as_view(), name="switch"),
]
