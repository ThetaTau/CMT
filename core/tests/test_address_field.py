"""Regression tests for GitHub issue #854.

    AttributeError: 'dict' object has no attribute 'raw'

The legacy user/pledge/chapter forms defined a ``clean_address`` method that did
``if address.raw == "None" or address.raw == "":`` against the value cleaned by
the old ``django-address`` ``AddressField``. That field could hand back a plain
``dict`` (of address components) instead of an ``Address`` instance, so the
``.raw`` attribute access blew up during form validation.

The address handling was later reworked to a typed-components
``ComponentAddressField``/``ComponentAddressWidget`` whose ``compress()`` funnels
through ``get_or_create_address()`` and only ever returns an ``Address`` instance
or ``None`` -- never a ``dict`` -- and the ``clean_address`` methods were removed.

These tests lock that contract in so the crash cannot come back.
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
