from django.conf.urls import url

from . import views

app_name = "chapters"
urlpatterns = [
    url(regex=r"^$", view=views.ChapterListView.as_view(), name="list"),
    url(
        regex=r"^~redirect/$", view=views.ChapterRedirectView.as_view(), name="redirect"
    ),
    url(
        regex=r"^(?P<slug>[\w.@+-]+)/$",
        view=views.ChapterDetailView.as_view(),
        name="detail",
    ),
]
