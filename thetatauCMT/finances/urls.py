from django.conf.urls import url

from . import views

app_name = 'finances'
urlpatterns = [
    url(
        regex=r'^$',
        view=views.TransactionListView.as_view(),
        name='list'
    ),
]
