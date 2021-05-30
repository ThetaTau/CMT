from django.conf.urls import url

from . import views

app_name = "notes"
urlpatterns = [
    url(
        regex=r"^add/(?P<slug>[\w.@+-]+)/$",
        view=views.ChapterNoteCreateView.as_view(),
        name="add",
    ),
    url(
        regex=r"^add_user/(?P<user_id>[\w.@+-]+)/$",
        view=views.UserNoteCreateView.as_view(),
        name="add_user",
    ),
]
