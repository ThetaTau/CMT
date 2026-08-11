"""Static choice lists reused across forms.  Kept in a dedicated module so
form modules can import them without dragging in extra dependencies."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

US_STATE_CHOICES = [
    ("AL", "Alabama"),
    ("AK", "Alaska"),
    ("AZ", "Arizona"),
    ("AR", "Arkansas"),
    ("CA", "California"),
    ("CO", "Colorado"),
    ("CT", "Connecticut"),
    ("DE", "Delaware"),
    ("DC", "District of Columbia"),
    ("FL", "Florida"),
    ("GA", "Georgia"),
    ("HI", "Hawaii"),
    ("ID", "Idaho"),
    ("IL", "Illinois"),
    ("IN", "Indiana"),
    ("IA", "Iowa"),
    ("KS", "Kansas"),
    ("KY", "Kentucky"),
    ("LA", "Louisiana"),
    ("ME", "Maine"),
    ("MD", "Maryland"),
    ("MA", "Massachusetts"),
    ("MI", "Michigan"),
    ("MN", "Minnesota"),
    ("MS", "Mississippi"),
    ("MO", "Missouri"),
    ("MT", "Montana"),
    ("NE", "Nebraska"),
    ("NV", "Nevada"),
    ("NH", "New Hampshire"),
    ("NJ", "New Jersey"),
    ("NM", "New Mexico"),
    ("NY", "New York"),
    ("NC", "North Carolina"),
    ("ND", "North Dakota"),
    ("OH", "Ohio"),
    ("OK", "Oklahoma"),
    ("OR", "Oregon"),
    ("PA", "Pennsylvania"),
    ("PR", "Puerto Rico"),
    ("RI", "Rhode Island"),
    ("SC", "South Carolina"),
    ("SD", "South Dakota"),
    ("TN", "Tennessee"),
    ("TX", "Texas"),
    ("UT", "Utah"),
    ("VT", "Vermont"),
    ("VA", "Virginia"),
    ("WA", "Washington"),
    ("WV", "West Virginia"),
    ("WI", "Wisconsin"),
    ("WY", "Wyoming"),
]

US_STATE_CODE_TO_NAME = dict(US_STATE_CHOICES)
US_STATE_NAME_TO_CODE = {name: code for code, name in US_STATE_CHOICES}

CA_PROVINCE_CHOICES = [
    ("AB", "Alberta"),
    ("BC", "British Columbia"),
    ("MB", "Manitoba"),
    ("NB", "New Brunswick"),
    ("NL", "Newfoundland and Labrador"),
    ("NT", "Northwest Territories"),
    ("NS", "Nova Scotia"),
    ("NU", "Nunavut"),
    ("ON", "Ontario"),
    ("PE", "Prince Edward Island"),
    ("QC", "Quebec"),
    ("SK", "Saskatchewan"),
    ("YT", "Yukon"),
]

CA_PROVINCE_CODE_TO_NAME = dict(CA_PROVINCE_CHOICES)
CA_PROVINCE_NAME_TO_CODE = {name: code for code, name in CA_PROVINCE_CHOICES}

UK_REGION_CHOICES = [
    ("ENG", "England"),
    ("SCT", "Scotland"),
    ("WLS", "Wales"),
    ("NIR", "Northern Ireland"),
]

UK_REGION_NAME_TO_CODE = {name: code for code, name in UK_REGION_CHOICES}

COUNTRY_CHOICES = [
    ("United States", "United States"),
    ("Canada", "Canada"),
    ("Mexico", "Mexico"),
    ("United Kingdom", "United Kingdom"),
    ("Australia", "Australia"),
    ("Germany", "Germany"),
    ("France", "France"),
    ("India", "India"),
    ("China", "China"),
    ("Japan", "Japan"),
    ("Other", "Other"),
]

# All state/province/region names, used for the datalist suggestions on the
# free-text state input in the address widget.  Order doesn't matter — the
# datalist is presented alphabetically by the browser regardless.
ADDRESS_REGION_SUGGESTIONS = (
    [name for _code, name in US_STATE_CHOICES]
    + [name for _code, name in CA_PROVINCE_CHOICES]
    + [name for _code, name in UK_REGION_CHOICES]
)

# IANA zones that cover essentially every chapter, surfaced first so the common
# case is one click.  The full list stays available underneath.
COMMON_TIME_ZONES = [
    ("America/New_York", "Eastern"),
    ("America/Chicago", "Central"),
    ("America/Denver", "Mountain"),
    ("America/Phoenix", "Arizona (no DST)"),
    ("America/Los_Angeles", "Pacific"),
    ("America/Anchorage", "Alaska"),
    ("Pacific/Honolulu", "Hawaii"),
    ("America/Puerto_Rico", "Puerto Rico"),
    ("Pacific/Guam", "Guam"),
    ("UTC", "UTC"),
]


def time_zone_choices(blank_label="Site default"):
    """Grouped ``<select>`` choices: the common US zones, then every IANA zone."""
    common_keys = [key for key, _label in COMMON_TIME_ZONES]
    rest = sorted(available_timezones() - set(common_keys))
    return [
        ("", blank_label),
        ("Common", [(key, f"{label} ({key})") for key, label in COMMON_TIME_ZONES]),
        ("All time zones", [(key, key) for key in rest]),
    ]


def is_valid_time_zone(value):
    """True when ``value`` names an IANA zone (blank is allowed = site default)."""
    if not value:
        return True
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True
