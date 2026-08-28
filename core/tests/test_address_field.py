"""Regression tests for the address form/field stack.

Covers two historical Rollbar crashes:

* Issue #854 -- ``AttributeError: 'dict' object has no attribute 'raw'``.
  The legacy ``clean_address`` did ``address.raw == "None"`` against the value
  cleaned by the old ``django-address`` ``AddressField``, which could hand back a
  plain ``dict`` instead of an ``Address`` instance.

* Issue #815 -- ``MultipleObjectsReturned: get() returned more than one Address``.
  The same old field resolved a submitted address to a row via
  ``Address.objects.get(...)`` (``_to_python``), which raised whenever duplicate
  ``Address`` rows existed -- surfaced most often through a Django admin change
  form.

Both were reworked to a typed-components ``ComponentAddressField`` /
``ComponentAddressWidget`` whose ``compress()`` funnels through
``get_or_create_address()`` and only ever returns an ``Address`` instance or
``None`` (never a ``dict``), returning the OLDEST matching row instead of raising
on duplicates. These tests lock that contract in so neither crash can come back.
"""

import pytest
from address.models import Address
from django import forms

from core.address import get_or_create_address
from core.forms import ComponentAddressField

pytestmark = pytest.mark.django_db


class AddressOnlyForm(forms.Form):
    """Minimal form that exercises the real bound-form validation path the
    original traceback crashed on (``is_valid()`` -> field ``clean``)."""

    address = ComponentAddressField(required=True)


class TestGetOrCreateAddress:
    def test_all_empty_components_return_none(self):
        # This is the exact condition the old ``clean_address`` tried to detect
        # via ``address.raw``. It must now resolve to ``None`` up front.
        assert get_or_create_address("", "", "", "", "") is None

    def test_valid_components_return_address_instance(self):
        addr = get_or_create_address(
            street="123 Main St",
            city="Austin",
            state="Texas",
            postal_code="78701",
            country="United States",
            state_code="TX",
        )
        assert isinstance(addr, Address)
        assert not isinstance(addr, dict)

    def test_matching_components_reuse_the_same_row(self):
        first = get_or_create_address(
            street="500 W 5th St",
            city="Austin",
            state="Texas",
            postal_code="78701",
            country="United States",
            state_code="TX",
        )
        second = get_or_create_address(
            street="500 W 5th St",
            city="Austin",
            state="Texas",
            postal_code="78701",
            country="United States",
            state_code="TX",
        )
        assert first.pk == second.pk


class TestComponentAddressFieldNeverReturnsDict:
    def test_clean_empty_components_returns_none(self):
        field = ComponentAddressField(required=False)
        result = field.clean(["", "", "", "", ""])
        assert result is None
        assert not isinstance(result, dict)

    def test_clean_valid_components_returns_address(self):
        field = ComponentAddressField(required=False)
        result = field.clean(["123 Main St", "Austin", "Texas", "78701", "United States"])
        assert isinstance(result, Address)
        assert not isinstance(result, dict)

    def test_bound_form_with_empty_address_fails_cleanly(self):
        # Required address + all-empty components used to crash with
        # ``AttributeError: 'dict' object has no attribute 'raw'``. It must now
        # simply be invalid, never raise.
        form = AddressOnlyForm(
            data={
                "address_0": "",
                "address_1": "",
                "address_2": "",
                "address_3": "",
                "address_4": "",
            }
        )
        assert form.is_valid() is False
        assert "address" in form.errors

    def test_bound_form_with_valid_address_compresses_to_address(self):
        form = AddressOnlyForm(
            data={
                "address_0": "123 Main St",
                "address_1": "Austin",
                "address_2": "Texas",
                "address_3": "78701",
                "address_4": "United States",
            }
        )
        assert form.is_valid() is True
        cleaned = form.cleaned_data["address"]
        assert isinstance(cleaned, Address)
        assert not isinstance(cleaned, dict)


def _make_duplicate_addresses(n=3):
    """Create ``n`` `Address` rows sharing the same street/route/locality -- the
    exact condition that made django-address's ``Address.objects.get(...)`` raise
    ``MultipleObjectsReturned`` in issue #815."""
    from address.models import Country, Locality, State

    country = Country.objects.create(name="United States", code="US")
    state = State.objects.create(name="Texas", code="TX", country=country)
    locality = Locality.objects.create(name="Austin", postal_code="78701", state=state)
    return [
        Address.objects.create(
            street_number="123",
            route="Main St",
            locality=locality,
            raw=f"123 Main St #{i}",
        )
        for i in range(n)
    ]


class TestDuplicateAddressesDoNotCrash:
    """Regression for issue #815 -- ``MultipleObjectsReturned: get() returned
    more than one Address``.

    The legacy django-address form field resolved a submitted address to a row
    via ``Address.objects.get(...)`` (in ``_to_python``), which raised whenever
    duplicate rows existed -- surfaced most often through a Django admin change
    form. The current stack resolves via ``get_or_create_address`` /
    ``ComponentAddressField``, which returns the OLDEST matching row instead of
    raising.
    """

    def test_get_or_create_address_returns_oldest_when_duplicates_exist(self):
        addrs = _make_duplicate_addresses(3)
        # Must not raise MultipleObjectsReturned.
        result = get_or_create_address(
            street="123 Main St",
            city="Austin",
            state="Texas",
            postal_code="78701",
            country="United States",
            state_code="TX",
        )
        assert result.pk == addrs[0].pk

    def test_bound_form_with_duplicate_addresses_does_not_raise(self):
        addrs = _make_duplicate_addresses(3)
        form = AddressOnlyForm(
            data={
                "address_0": "123 Main St",
                "address_1": "Austin",
                "address_2": "Texas",
                "address_3": "78701",
                "address_4": "United States",
            }
        )
        # Previously this raised MultipleObjectsReturned inside field cleaning.
        assert form.is_valid() is True
        assert form.cleaned_data["address"].pk == addrs[0].pk


class TestPreviouslyVulnerableFormsUseComponentAddressField:
    """Every form/admin that edits an ``address.models.AddressField`` must route
    through ``ComponentAddressField`` rather than django-address's default
    (crashing) field, so the #815 traceback cannot recur."""

    def test_user_update_form_address_fields_are_component(self):
        from thetatauCMT.users.forms import UserUpdateForm

        assert isinstance(UserUpdateForm.base_fields["address"], ComponentAddressField)
        assert isinstance(UserUpdateForm.base_fields["employer_address"], ComponentAddressField)

    def test_disciplinary_process_admin_uses_component_address_field(self):
        from django.contrib.admin.sites import AdminSite

        from thetatauCMT.forms.admin import DisciplinaryProcessAdmin
        from thetatauCMT.forms.models import DisciplinaryProcess

        admin_obj = DisciplinaryProcessAdmin(DisciplinaryProcess, AdminSite())
        db_field = DisciplinaryProcess._meta.get_field("address")
        formfield = admin_obj.formfield_for_dbfield(db_field, request=None)
        assert isinstance(formfield, ComponentAddressField)

    def test_member_update_admin_uses_component_address_field(self):
        from django.contrib.admin.sites import AdminSite

        from thetatauCMT.users.admin import MemberUpdateAdmin
        from thetatauCMT.users.models import MemberUpdate

        admin_obj = MemberUpdateAdmin(MemberUpdate, AdminSite())
        for field_name in ("address", "employer_address"):
            db_field = MemberUpdate._meta.get_field(field_name)
            formfield = admin_obj.formfield_for_dbfield(db_field, request=None)
            assert isinstance(formfield, ComponentAddressField), field_name


class TestSelect2ListCreateMultipleChoiceFieldLocality:
    """Regression for a prod crash on the jobs "location" field
    (``Select2ListCreateMultipleChoiceField`` bound to ``Locality``).

    The select2 tagging widget lets a user type free text instead of picking
    a suggestion (e.g. a browser autofilled "Durham, North Carolina, United
    States"). ``to_python`` used ``re.search(...).group(0)`` unconditionally,
    which raised ``AttributeError: 'NoneType' object has no attribute 'group'``
    whenever the typed text had no 5-digit zip code.
    """

    def test_typed_text_without_zip_matches_existing_city_by_name(self):
        from address.models import Country, Locality, State

        from core.forms import Select2ListCreateMultipleChoiceField

        country = Country.objects.create(name="United States", code="US")
        state = State.objects.create(name="North Carolina", code="NC", country=country)
        locality = Locality.objects.create(name="Durham", postal_code="27701", state=state)

        field = Select2ListCreateMultipleChoiceField(queryset=Locality.objects.all(), required=False)
        result = field.to_python(["Durham, North Carolina, United States"])
        assert result == [locality]

    def test_typed_text_with_no_match_raises_validation_error_not_crash(self):
        from address.models import Locality

        from core.forms import Select2ListCreateMultipleChoiceField

        field = Select2ListCreateMultipleChoiceField(queryset=Locality.objects.all(), required=False)
        with pytest.raises(forms.ValidationError):
            field.to_python(["Nowhereville, Atlantis"])

    def test_typed_text_with_zip_still_resolves_by_postal_code(self):
        from address.models import Country, Locality, State

        from core.forms import Select2ListCreateMultipleChoiceField

        country = Country.objects.create(name="United States", code="US")
        state = State.objects.create(name="Texas", code="TX", country=country)
        locality = Locality.objects.create(name="Austin", postal_code="78701", state=state)

        field = Select2ListCreateMultipleChoiceField(queryset=Locality.objects.all(), required=False)
        result = field.to_python(["Austin, TX 78701"])
        assert result == [locality]
