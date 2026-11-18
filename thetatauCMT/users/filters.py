# filters.py
import datetime
import re

import django_filters
from dal import autocomplete
from django import forms
from django.db.models import CharField, F, Func, Q, Value
from django.db.models.functions import ExtractMonth, ExtractYear
from watson import search as watson

from core.address import isinradius
from core.filters import DateRangeFilter, DynamicScopeFilterSetMixin
from core.models import (
    ACTIVE_STATUSES,
    ADVISOR_ROLES,
    CHAPTER_OFFICER,
    COMMITTEE_CHAIR,
    COUNCIL,
    NATIONAL_OFFICER,
    SEMESTER,
    SUPPORT_ROLES,
    semester_encompass_start_end_date,
    semester_label,
)
from thetatauCMT.chapters.models import Chapter, ChapterCurricula
from thetatauCMT.regions.models import Region

from .models import User, UserOrgParticipate, UserRoleChange

# Spells out what the watson member index (registered in users/apps.py) holds, so the
# quick search box says exactly what it looks through.
QUICK_SEARCH_HELP = (
    "Searches name (full, first, last, preferred, nickname and maiden), badge #, email, school email, "
    "username, member ID, pronouns and chapter. Each word you type must match the start of a word in one "
    'of those, so "jo smi" finds John Smith.'
)

MEMBER_STATUS_CHOICES = [
    ("active", "Active"),
    ("pnm", "Prospective"),
    ("away", "Away"),
    ("activepend", "Active Pending"),
    ("alumnipend", "Alumni Pending"),
]
OFFICER_STATUS_CHOICES = [
    ("alumni", "Alumni"),
    ("suspended", "Suspended"),
    ("other", "Other Status"),
]
# The stored statuses each status choice also covers.
STATUS_GROUPS = {
    "active": ["activeCC"],
    "alumni": ["alumniCC", "deceased"],
    "suspended": ["pendexpul", "probation"],
    "other": ["advisor", "expelled", "friend", "nonmember", "resigned", "resignedCC"],
}

RANGE_FILTER_LABELS = {
    "graduation_year__icontains": "Grad Year",
    "graduation_year__gte": "Grad Year \u2265",
    "graduation_year__lte": "Grad Year \u2264",
    "badge_number__gte": "Badge # \u2265",
    "badge_number__lte": "Badge # \u2264",
}

NAME_FIELDS = ("name", "first_name", "middle_name", "last_name", "preferred_name", "nickname", "maiden_name")
ADDRESS_FIELDS = (
    "address__raw",
    "address__formatted",
    "address__street_number",
    "address__route",
    "address__locality__name",
    "address__locality__postal_code",
    "address__locality__state__name",
    "address__locality__state__code",
    "address__locality__state__country__name",
)

ROLE_GROUPS = (
    ("Chapter Officers", CHAPTER_OFFICER),
    ("Chairs & Appointees", COMMITTEE_CHAIR),
    ("Advisers", ADVISOR_ROLES),
    ("National Officers", NATIONAL_OFFICER),
    ("Grand Council", COUNCIL),
    ("Chapter Support", SUPPORT_ROLES),
)
ROLE_CHOICES = [(group, [(role, role.title()) for role in sorted(roles)]) for group, roles in ROLE_GROUPS]


def filter_name_or_maiden_name(queryset, field_name, value):
    """Match ``value`` against the denormalized ``name`` OR ``maiden_name``.

    Members who change their last name (e.g. after marriage) keep their prior
    name in ``maiden_name``, so a search on either name still finds them.
    """
    return queryset.filter(Q(name__icontains=value) | Q(maiden_name__icontains=value))


def every_word_in_any(queryset, fields, value):
    """Keep rows where each word of ``value`` appears (any case) in at least one of ``fields``."""
    for word in value.split():
        anywhere = Q()
        for field in fields:
            anywhere |= Q(**{f"{field}__icontains": word})
        queryset = queryset.filter(anywhere)
    return queryset


def filter_any_name(queryset, field_name, value):
    """Every word of ``value`` must appear in one of the member's names.

    So "Kevin Smith" finds a member who goes by his middle name Henry
    (``name`` = "Henry Smith"), and a maiden name still finds a married member.
    """
    return every_word_in_any(queryset, NAME_FIELDS, value)


def filter_address(queryset, field_name, value):
    """Every word of ``value`` must appear somewhere in the member's address, e.g. "Austin TX"."""
    return every_word_in_any(queryset, ADDRESS_FIELDS, value)


def filter_phone(queryset, field_name, value):
    """Compare digits only, so "(512) 472-1904" finds "+15124721904"."""
    digits = re.sub(r"\D", "", value)
    if not digits:
        return queryset.none()
    phone_digits = Func(
        F("phone_number"), Value(r"\D"), Value(""), Value("g"), function="regexp_replace", output_field=CharField()
    )
    return queryset.annotate(phone_digits=phone_digits).filter(phone_digits__contains=digits)


def filter_status_groups(queryset, field_name, value):
    """Match the chosen statuses, each widened by its group (e.g. Alumni includes Deceased)."""
    if not value:
        return queryset
    statuses = [status for choice in value for status in [choice, *STATUS_GROUPS.get(choice, [])]]
    return queryset.filter(current_status__in=statuses)


def initiation_semester_choices(queryset):
    """Newest-first ``("fa-2024", "Fall 2024")`` choices, one per semester someone in ``queryset`` was initiated."""
    months = (
        queryset.order_by()
        .filter(initiation__date__isnull=False)
        .annotate(init_year=ExtractYear("initiation__date"), init_month=ExtractMonth("initiation__date"))
        .values_list("init_year", "init_month")
        .distinct()
    )
    starts = sorted(
        {semester_encompass_start_end_date(datetime.date(year, month, 1))[0] for year, month in months},
        reverse=True,
    )
    return [(f"{SEMESTER[start.month]}-{start.year}", semester_label(start)) for start in starts]


def all_chapter_choices():
    """Every chapter, inactive ones marked, so alumni of a closed chapter can still be found."""
    chapters = Chapter.objects.order_by("name").values_list("slug", "name", "active")
    return [(slug, name.title() if active else f"{name.title()} (inactive)") for slug, name, active in chapters]


class UserListFilterBase(django_filters.FilterSet):
    name__icontains = django_filters.CharFilter(
        method=filter_name_or_maiden_name,
        label="Member Name contains",
    )
    current_status = django_filters.MultipleChoiceFilter(
        choices=MEMBER_STATUS_CHOICES,
        method=filter_status_groups,
    )
    major = django_filters.ModelChoiceFilter(
        queryset=ChapterCurricula.objects.none(),
        method="filter_major",
    )

    class Meta:
        model = User
        fields = {
            "name": ["icontains"],
            "major": ["exact"],
            "graduation_year": ["icontains", "gte", "lte"],
            "badge_number": ["gte", "lte"],
        }
        order_by = ["name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters["major"].queryset = ChapterCurricula.objects.filter(chapter=self.request.user.current_chapter)
        for filter_name, label in RANGE_FILTER_LABELS.items():
            self.filters[filter_name].label = label
        if self.request.user.chapter_officer():
            self.filters["current_status"].field.choices.choices.extend(OFFICER_STATUS_CHOICES)

    def filter_major(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(major=value)
        return queryset


class MemberSearchFilterSet(django_filters.FilterSet):
    """The boxes the chapter roster and Search all Members share: one box per condition."""

    q = django_filters.CharFilter(method="filter_quick_search", label="Quick Search", help_text=QUICK_SEARCH_HELP)
    name = django_filters.CharFilter(
        method=filter_any_name,
        label="Name",
        help_text="First, middle, last, preferred, nickname or maiden name.",
    )
    email = django_filters.CharFilter(
        method="filter_email",
        label="Email",
        help_text="Email or school email, or part of one.",
    )
    badge_number = django_filters.NumberFilter(label="Badge #")
    initiation_semester = django_filters.ChoiceFilter(
        label="Initiation Semester",
        method="filter_initiation_semester",
        empty_label="Any semester",
        help_text="Spring is January to June, Fall is July to December.",
    )
    initiation_date__gte = django_filters.DateFilter(
        field_name="initiation__date",
        lookup_expr="gte",
        label="Initiation Date \u2265",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    initiation_date__lte = django_filters.DateFilter(
        field_name="initiation__date",
        lookup_expr="lte",
        label="Initiation Date \u2264",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters["initiation_semester"].extra["choices"] = initiation_semester_choices(self.queryset)

    def filter_quick_search(self, queryset, name, value):
        # Filters the given queryset, so the roster's search stays inside its own chapter.
        return watson.filter(queryset, value)

    def filter_email(self, queryset, name, value):
        return queryset.filter(Q(email__icontains=value) | Q(email_school__icontains=value))

    def filter_initiation_semester(self, queryset, name, value):
        term, year = value.split("-")
        start, end = semester_encompass_start_end_date(term=term, year=int(year))
        return queryset.filter(initiation__date__gte=start.date(), initiation__date__lt=end.date())


class UserListFilter(MemberSearchFilterSet, UserListFilterBase):
    """The chapter roster: the shared member boxes plus major, RMP and badge/grad year ranges."""

    name__icontains = None
    current_status = django_filters.MultipleChoiceFilter(
        label="Status",
        choices=MEMBER_STATUS_CHOICES,
        method=filter_status_groups,
        widget=forms.CheckboxSelectMultiple,
    )
    rmp_complete = django_filters.ChoiceFilter(
        label="RMP Status",
        choices=[
            ("True", "Complete"),
            ("False", "Incomplete"),
        ],
    )

    class Meta(UserListFilterBase.Meta):
        fields = {field: lookups for field, lookups in UserListFilterBase.Meta.fields.items() if field != "name"}


class UserSearchForm(forms.Form):
    """Own ids for the boxes: the National Officer region bar's chapter picker is already ``id_chapter``."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("auto_id", "id_search_%s")
        super().__init__(*args, **kwargs)


class UserSearchFilter(MemberSearchFilterSet):
    """Search all Members (National Officers): the shared member boxes across every chapter."""

    phone = django_filters.CharFilter(
        label="Phone",
        method=filter_phone,
        help_text="Any part of the number; spaces, dashes and brackets are ignored.",
    )
    current_roles = django_filters.MultipleChoiceFilter(
        label="Current Roles",
        choices=ROLE_CHOICES,
        method="filter_current_roles",
        widget=autocomplete.Select2Multiple(attrs={"data-placeholder": "Any role", "data-minimum-input-length": 0}),
        help_text="Members holding any of the roles you pick.",
    )
    chapter = django_filters.ChoiceFilter(label="Chapter", method="filter_chapter", empty_label="Any chapter")
    school = django_filters.CharFilter(
        field_name="chapter__school",
        lookup_expr="icontains",
        label="School",
        help_text="The chapter's school, or part of its name.",
    )
    region = django_filters.ChoiceFilter(label="Region", method="filter_region", empty_label="Any region")
    major = django_filters.CharFilter(field_name="major__major", lookup_expr="icontains", label="Major")
    current_status = django_filters.MultipleChoiceFilter(
        label="Status",
        choices=MEMBER_STATUS_CHOICES + OFFICER_STATUS_CHOICES,
        method=filter_status_groups,
        widget=forms.CheckboxSelectMultiple,
    )
    address = django_filters.CharFilter(
        label="Address",
        method=filter_address,
        help_text="Street, city, state or zip code. Every word must appear in the address.",
    )
    zip = django_filters.CharFilter(
        label="Zip Code",
        method="filter_zip",
        help_text="Members with an address within the distance of this zip code.",
    )
    dist = django_filters.NumberFilter(
        label="Distance (mi)",
        method="filter_distance",
        help_text="Miles from the zip code; 1 if left empty.",
    )

    class Meta:
        model = User
        form = UserSearchForm
        fields = {
            "graduation_year": ["icontains", "gte", "lte"],
            "badge_number": ["gte", "lte"],
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for filter_name, label in RANGE_FILTER_LABELS.items():
            self.filters[filter_name].label = label
        self.filters["chapter"].extra["choices"] = all_chapter_choices()
        # "National" means every region, the same as leaving the box empty.
        self.filters["region"].extra["choices"] = [
            choice for choice in Region.region_choices() if choice[0] != "national"
        ]

    def has_conditions(self):
        """Whether any box narrows the search; a distance means nothing without a zip code."""
        if not self.is_bound:
            return False
        self.form.is_valid()  # fills cleaned_data with every box that has a valid value
        return any(value not in (None, "", []) for name, value in self.form.cleaned_data.items() if name != "dist")

    def filter_chapter(self, queryset, name, value):
        return queryset.filter(chapter__slug=value)

    def filter_current_roles(self, queryset, name, value):
        return queryset.filter(current_roles__overlap=value)

    def filter_region(self, queryset, name, value):
        if value == "candidate_chapter":
            return queryset.filter(chapter__candidate_chapter=True)
        return queryset.filter(chapter__region__slug=value)

    def filter_zip(self, queryset, name, value):
        addresses = isinradius(value, self.form.cleaned_data.get("dist"))
        user_pks = [user.pk for address in addresses for user in address.user_set.all()]
        return queryset.filter(pk__in=user_pks)

    def filter_distance(self, queryset, name, value):
        # Only used by filter_zip.
        return queryset


class UserRoleListFilter(DynamicScopeFilterSetMixin, django_filters.FilterSet):
    name__icontains = django_filters.CharFilter(
        method=filter_name_or_maiden_name,
        label="Member Name contains",
    )
    current_status = django_filters.ChoiceFilter(
        choices=[
            ("active", "active"),
            ("pnm", "prospective"),
        ],
        method="filter_current_status",
    )
    current_roles = django_filters.MultipleChoiceFilter(choices=UserRoleChange.ROLES, method="filter_current_roles")
    region = django_filters.ChoiceFilter(label="Region", choices=Region.region_choices(), method="filter_region")
    major = django_filters.ModelChoiceFilter(
        queryset=ChapterCurricula.objects.none(),
        method="filter_major",
    )
    chapter = django_filters.ChoiceFilter(
        label="Chapter",
        choices=Chapter.chapter_choices(),
        method="filter_chapter",
    )

    class Meta:
        model = User
        fields = {
            "name": ["icontains"],
            "major": ["exact"],
            "graduation_year": ["icontains", "gte", "lte"],
            "badge_number": ["gte", "lte"],
            "chapter": ["exact"],
        }
        order_by = ["name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters["major"].queryset = ChapterCurricula.objects.values_list(
            "major",
            flat=True,
        ).distinct()
        self.filters["graduation_year__icontains"].label = "Grad Year"
        self.filters["graduation_year__gte"].label = "Grad Year \u2265"
        self.filters["graduation_year__lte"].label = "Grad Year \u2264"
        self.filters["badge_number__gte"].label = "Badge # \u2265"
        self.filters["badge_number__lte"].label = "Badge # \u2264"

    def filter_current_status(self, queryset, field_name, value):
        if value:
            if value == "active":
                values = ["active", "activeCC"]
            else:
                values = ["pnm"]
            queryset = queryset.filter(current_status__in=values)
        return queryset

    def filter_current_roles(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(current_roles__overlap=value)
        return queryset

    def filter_region(self, queryset, field_name, value):
        if value == "national":
            return queryset
        elif value == "candidate_chapter":
            queryset = queryset.filter(chapter__candidate_chapter=True)
        else:
            queryset = queryset.filter(chapter__region__slug=value)
        return queryset

    def filter_major(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(major__major=value.major)
        return queryset

    def filter_chapter(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(chapter__slug=value)
        return queryset


class AdvisorListFilter(DynamicScopeFilterSetMixin, django_filters.FilterSet):
    name__icontains = django_filters.CharFilter(
        method=filter_name_or_maiden_name,
        label="Member Name contains",
    )
    region = django_filters.ChoiceFilter(label="Region", choices=Region.region_choices(), method="filter_region")
    chapter = django_filters.ChoiceFilter(
        label="Chapter",
        choices=Chapter.chapter_choices(),
        method="filter_chapter",
    )

    class Meta:
        model = User
        fields = {
            "name": ["icontains"],
            "chapter": ["exact"],
        }
        order_by = ["name"]

    def filter_region(self, queryset, field_name, value):
        if value == "national":
            return queryset
        elif value == "candidate_chapter":
            queryset = queryset.filter(chapter__candidate_chapter=True)
        else:
            queryset = queryset.filter(chapter__region__slug=value)
        return queryset

    def filter_chapter(self, queryset, field_name, value):
        # The declared ``chapter`` ChoiceFilter references this method; without
        # it django-filter raised AssertionError when the advisor list rendered
        # (issue #827).
        if value:
            queryset = queryset.filter(chapter__slug=value)
        return queryset


ALUMNI_STATUSES = ["alumni", "alumniCC"]


class UserOrgListFilter(django_filters.FilterSet):
    """Filter the chapter external-organization table.

    Mirrors the events list filter: a member-status toggle (defaulting to
    active members), an organization-name search, and start/end date ranges.
    """

    status = django_filters.ChoiceFilter(
        label="Member Status",
        choices=(("active", "Active"), ("alumni", "Alumni"), ("all", "All")),
        method="filter_status",
        empty_label=None,
    )
    organization = django_filters.CharFilter(
        field_name="organization__name",
        lookup_expr="icontains",
        label="Organization",
    )
    start = DateRangeFilter(field_name="start", label="Start")
    end = DateRangeFilter(field_name="end", label="End")

    class Meta:
        model = UserOrgParticipate
        fields = ["status", "organization", "start", "end"]
        order_by = ["-start"]

    def __init__(self, data=None, *args, **kwargs):
        # Default to showing active members' participation when the page loads
        # with no explicit status choice (including after "Clear").
        if data is not None:
            data = data.copy()
            data.setdefault("status", "active")
        super().__init__(data, *args, **kwargs)

    def filter_status(self, queryset, field_name, value):
        if value == "active":
            return queryset.filter(user__current_status__in=ACTIVE_STATUSES)
        if value == "alumni":
            return queryset.filter(user__current_status__in=ALUMNI_STATUSES)
        return queryset
