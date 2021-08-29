from django.conf.urls import url

from . import views

app_name = "finances"
urlpatterns = [
    url(regex=r"^$", view=views.InvoiceListView.as_view(), name="list"),
    url(
        regex=r"^chapters/$",
        view=views.ChapterBalancesListView.as_view(),
        name="chapters",
    ),
]
