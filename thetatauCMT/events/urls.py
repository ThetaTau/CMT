from django.urls import path

from . import views

app_name = "events"
urlpatterns = [
    path("", views.EventListView.as_view(), name="list"),
    path("all/", views.EventListAllView.as_view(), name="list_all"),
    path("add/", views.EventCreateView.as_view(), name="add"),
    path("copy/<int:pk>/", views.EventCopyView.as_view(), name="copy"),
    path("redirect/", views.EventRedirectView.as_view(), name="redirect"),
    path("update/<int:pk>/", views.EventUpdateView.as_view(), name="update"),
    # Converted to path with int and slug converters
    path(
        "~<int:year>/<int:month>/<int:day>/<slug:slug>/",
        views.EventDetailView.as_view(),
        name="detail",
    ),
]
