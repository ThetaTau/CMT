import csv
from address.models import Locality, State, Country, Address
from django.conf import settings


def run(*args):
    """
    python manage.py runscript build_zipcode_database

    """
    csv_path = settings.ROOT_DIR / "database_backups/zip_code_database.csv"
    country = Country.objects.get(name="United States")
    name_codes = [
        ("Maine", "ME"),
        ("Vermont", "VT"),
        ("Washington, D.C.", "DC"),
        ("West Virginia", "WV"),
        ("North Dakota", "ND"),
        ("Missouri", "MO"),
        ("Nebraska", "NE"),
        ("Wyoming", "WY"),
        ("Idaho", "ID"),
        ("Utah", "UT"),
        ("New Mexico", "NM"),
        ("Alaska", "AK"),
    ]
    for name_code in name_codes:
        name, code = name_code
        try:
            state = State.objects.get(name=name)
            state.code = code
            state.save()
        except State.DoesNotExist:
            State(name=name, code=code, country=country).save()
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        """
        zip	                        ZIP Code (USPS)
        type	                    Military, PO Box, Standard, or Unique (USPS)
        decommissioned	            Whether this zip has been decommissioned (USPS)
        primary_city	            Primary city (USPS)
        acceptable_cities           Acceptable cities (USPS)
        unacceptable_cities         Unacceptable cities (USPS)
        state                       U.S. state abbreviation (USPS)
        county                      County with the largest percentage of the ZIP population (Derived from 2020 Census)
        timezone                    Timezone name (Derived)
        area_codes                  Telephone area codes within this ZIP (Derived)
        world_region                World region. Most useful for military ZIPs (MPSA and FVAP Absentee Ballots)
        country                     Alpha-2 country code. Most useful for military ZIPs (MPSA and FVAP Absentee Ballots)
        latitude                    Precise to approximately 1 mile radius (National Weather Service, derived, hand-picked)
        longitude                   Precise to approximately 1 mile radius (National Weather Service, derived, hand-picked)
        irs_estimated_population    Estimated population (2018 IRS exemptions)
        """
        for i, row in enumerate(reader):
            print(row)
            if row["decommissioned"] == "1":
                continue
            if row["country"] != "US":
                continue
            state_abb = row["state"]
            if row["type"] == "MILITARY":
                continue
            if state_abb in [
                "VI",
                "AE",
                "AA",
                "AP",
                "AS",
                "GU",
                "FM",
                "MP",
                "MH",
                "PW",
            ]:
                continue
            state, _ = State.objects.get_or_create(
                code=state_abb,
                country=country,
                defaults=dict(code=state_abb, country=country),
            )
            city_name = row["primary_city"]
            zipcode = row["zip"]
            try:
                locality, _ = Locality.objects.get_or_create(
                    postal_code=zipcode,
                    defaults=dict(state=state, name=city_name, postal_code=zipcode),
                )
            except Locality.MultipleObjectsReturned:
                locality = Locality.objects.filter(postal_code=zipcode).first()
            lat = row["latitude"]
            lng = row["longitude"]
            address_raw = f"{city_name}, {state} {zipcode}, US"
            address, created = Address.objects.get_or_create(
                raw=address_raw,
                defaults=dict(
                    latitude=lat, longitude=lng, locality=locality, raw=address_raw
                ),
            )
            if not created:
                # Need to verify that the lat/long are correct
                update = False
                if address.latitude != lat:
                    address.latitude = lat
                    update = True
                if address.longitude != lng:
                    address.longitude = lng
                    update = True
                if update:
                    address.save()
