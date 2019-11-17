from django.conf.urls import url

from . import views

app_name = 'scores'
urlpatterns = [
    url(
        regex=r'^$',
        view=views.ScoreListView.as_view(),
        name='list'
    ),
    url(
        regex=r'^chapters/$',
        view=views.ChapterScoreListView.as_view(),
        name='chapterlist'
    ),
    url(
        regex=r'^~redirect/$',
        view=views.ScoreRedirectView.as_view(),
        name='redirect'
    ),
    url(
        regex=r'^(?P<slug>[\w.@+-]+)/$',
        view=views.ScoreDetailView.as_view(),
        name='detail'
    ),
]
