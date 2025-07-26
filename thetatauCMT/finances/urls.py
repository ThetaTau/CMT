from django.urls import path

from . import views

app_name = "finances"
urlpatterns = [
    path("", views.InvoiceListView.as_view(), name="list"),
    path(
        "chapters/",
        views.ChapterBalancesListView.as_view(),
        name="chapters",
    ),
]
