from django.conf import settings
from address.models import (
    InconsistentDictError,
    State,
    Locality,
    Country,
    unicode,
)
from pygeocoder import Geocoder, GeocoderError


def xstr(s):
    return s or ""


def update_address(value, address_obj):
    """
    from address.models import _to_python
    Original function from django_address does not allow
        for updating existing address with new address data
    :param value:
    :param address_obj:
    :return:
    """
    raw = xstr(value.get("raw", ""))
    country = xstr(value.get("country", ""))
    country_code = xstr(value.get("country_code", ""))
    state = xstr(value.get("state", ""))
    state_code = xstr(value.get("state_code", ""))
    locality = xstr(value.get("locality", ""))
    sublocality = xstr(value.get("sublocality", ""))
    postal_code = xstr(value.get("postal_code", ""))
    street_number = xstr(value.get("street_number", ""))
    route = xstr(value.get("route", ""))
    formatted = xstr(value.get("formatted", ""))
    latitude = value.get("latitude", None)
    longitude = value.get("longitude", None)

    # If there is no value (empty raw) then return None.
    if not raw:
        return None

    # Fix issue with NYC boroughs (https://code.google.com/p/gmaps-api-issues/issues/detail?id=635)
    if not locality and sublocality:
        locality = sublocality

    # If we have an inconsistent set of value bail out now.
    if (country or state or locality) and not (country and state and locality):
        raise InconsistentDictError

    # Handle the country.
    try:
        country_obj = Country.objects.get(name=country)
    except Country.DoesNotExist:
        if country:
            if len(country_code) > Country._meta.get_field("code").max_length:
                if country_code != country:
                    raise ValueError(
                        "Invalid country code (too long): %s" % country_code
                    )
                country_code = ""
            country_obj = Country.objects.create(name=country, code=country_code)
        else:
            country_obj = None

    # Handle the state.
    try:
        state_obj = State.objects.get(name=state, country=country_obj)
    except State.DoesNotExist:
        if state:
            if len(state_code) > State._meta.get_field("code").max_length:
                if state_code != state:
                    raise ValueError("Invalid state code (too long): %s" % state_code)
                state_code = ""
            state_obj = State.objects.create(
                name=state, code=state_code, country=country_obj
            )
        else:
            state_obj = None

    # Handle the locality.
    try:
        locality_obj = Locality.objects.get(
            name=locality, postal_code=postal_code, state=state_obj
        )
    except Locality.DoesNotExist:
        if locality:
            locality_obj = Locality.objects.create(
                name=locality, postal_code=postal_code, state=state_obj
            )
        else:
            locality_obj = None

    # Handle the address.
    address_obj.street_number = street_number
    address_obj.route = route
    address_obj.raw = raw
    address_obj.locality = locality_obj
    address_obj.formatted = formatted
    address_obj.latitude = latitude
    address_obj.longitude = longitude
    # If "formatted" is empty try to construct it from other values.
    if not address_obj.formatted:
        address_obj.formatted = unicode(address_obj)

    # Need to save.
    address_obj.save()

    # Done.
    return address_obj


def fix_address(address):
    coder = Geocoder(settings.GOOGLE_API_KEY)
    try:
        parsed = coder.geocode(address.raw)
    except GeocoderError:
        print("    !!! Bad address")
        address.delete()
        return None
    print("    ", address.raw, parsed.formatted_address, sep="\n    ")
    postal_code = parsed.postal_code
    if parsed.postal_code_suffix:
        postal_code = f"{postal_code}-{parsed.postal_code_suffix}"
    parsed_values = dict(
        raw=address.raw,
        country=parsed.country,
        state=parsed.state,
        locality=parsed.locality,
        sublocality=parsed.county,
        postal_code=postal_code,
        street_number=parsed.street_number,
        route=parsed.route,
        formatted=parsed.formatted_address,
        latitude=parsed.latitude,
        longitude=parsed.longitude,
    )
    address = update_address(parsed_values, address)
    return address
