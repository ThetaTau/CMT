import pytest
from django.contrib import admin
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from thetatauCMT.biglittle.admin import BigLittleAdmin
from thetatauCMT.biglittle.models import BigLittle
from thetatauCMT.users.tests.factories import UserFactory


def test_biglittle_is_registered_with_its_admin():
    assert isinstance(admin.site._registry[BigLittle], BigLittleAdmin)


@pytest.mark.django_db
@override_settings(DEBUG=True)  # superusers bypass RequireSuperuser2FAMiddleware only when DEBUG
def test_changelist_filters_current_and_former(auto_login_user, admin_user):
    client, _ = auto_login_user(user=admin_user)
    little = UserFactory()
    current = BigLittle.objects.create(big=UserFactory(chapter=little.chapter), little=little, chapter=little.chapter)
    former = BigLittle.objects.create(
        big=UserFactory(chapter=little.chapter),
        little=little,
        chapter=little.chapter,
        ended=timezone.now(),
    )
    url = reverse("admin:biglittle_biglittle_changelist")

    response = client.get(url, {"current": "yes"})
    assert response.status_code == 200
    assert list(response.context["cl"].queryset) == [current]

    response = client.get(url, {"current": "no"})
    assert list(response.context["cl"].queryset) == [former]


@pytest.mark.django_db
def test_adding_in_admin_records_who_added_it(admin_user):
    little = UserFactory()
    pairing = BigLittle(big=UserFactory(chapter=little.chapter), little=little, chapter=little.chapter)
    request = RequestFactory().post("/")
    request.user = admin_user

    BigLittleAdmin(BigLittle, admin.site).save_model(request, pairing, form=None, change=False)

    pairing.refresh_from_db()
    assert pairing.created_by == admin_user
