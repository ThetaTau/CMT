import io
import csv
import warnings
import datetime
from pathlib import Path
from enum import Enum
from datetime import timedelta
from django.contrib import messages
from django.utils.timezone import make_aware
from django.db import models
from django.db.models.functions import Concat
from django.core.validators import RegexValidator
from django.db.utils import ProgrammingError
from address.models import AddressField
from email.mime.base import MIMEBase
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from quickbooks.objects.customer import Customer
from quickbooks.objects.attachable import Attachable, AttachableRef
from herald.models import SentNotification
from core.finances import get_quickbooks_client, invoice_search, create_line
from email_signals.models import EmailSignalMixin
from core.models import (
    TODAY_END,
    annotate_role_status,
    CHAPTER_OFFICER,
    CHAPTER_ROLES,
    semester_encompass_start_end_date,
    BIENNIUM_START,
    BIENNIUM_START_DATE,
    BIENNIUM_DATES,
    ADVISOR_ROLES,
    EnumClass,
)
from regions.models import Region
from configs.models import Config
from .notifications import DuesReminder

GREEK_ABR = {
    "a": "alpha",
    "albany": "ua colony",
    "ua": "ua colony",
    "b": "beta",
    "csf": "csf colony",
    "cslb": "cslb colony",
    "d": "delta",
    "dg": "delta gamma",
    "dxl": "drexel colony",
    "e": "epsilon",
    "eb": "epsilon beta",
    "ed": "epsilon delta",
    "eg": "epsilon gamma",
    "fit": "fit colony",
    "gb": "gamma beta",
    "h": "eta",
    "hd": "eta delta",
    "he": "eta epsilon",
    "hg": "eta gamma",
    "id": "iota delta",
    "ie": "iota epsilon",
    "ig": "iota gamma",
    "jmu": "jmu colony",
    "k": "kappa",
    "kb": "kappa beta",
    "kd": "kappa delta",
    "ke": "kappa epsilon",
    "kg": "kappa gamma",
    "lb": "lambda beta",
    "ld": "lambda delta",
    "le": "lambda epsilon",
    "lg": "lambda gamma",
    "m": "mu",
    "md": "mu delta",
    "me": "mu epsilon",
    "mg": "mu gamma",
    "nau": "nau colony",
    "nd": "nu delta",
    "ne": "nu epsilon",
    "ng": "nu gamma",
    "njit": "njit colony",
    "o": "omicron",
    "ob": "omicron beta",
    "od": "omicron delta",
    "og": "omicron gamma",
    "omb": "omega beta",
    "omg": "omega",
    "omga": "omega gamma",
    "omgd": "omega delta",
    "p": "rho",
    "pb": "rho beta",
    "pd": "rho delta",
    "pg": "rho gamma",
    "phd": "phi delta",
    "phg": "phi gamma",
    "phi": "phi",
    "pi": "pi",
    "pid": "pi delta",
    "pig": "pi gamma",
    "psb": "psi beta",
    "psd": "psi delta",
    "psg": "psi gamma",
    "row": "row colony",
    "s": "sigma",
    "scu": "scu colony",
    "sd": "sigma delta",
    "sg": "sigma gamma",
    "t": "tau",
    "tb": "tau beta",
    "td": "tau delta",
    "test": "test",
    "tg": "tau gamma",
    "thd": "theta delta",
    "the": "theta epsilon",
    "thg": "theta gamma",
    "tu": "tu colony",
    "u": "upsilon",
    "ub": "upsilon beta",
    "ucsb": "ucsb colony",
    "ud": "upsilon delta",
    "ug": "upsilon gamma",
    "unh": "unh colony",
    "uw": "uw colony",
    "vic": "victoria colony",
    "x": "chi",
    "xb": "chi beta",
    "xd": "chi delta",
    "xg": "chi gamma",
    "xi": "xi",
    "xib": "xi beta",
    "xid": "xi delta",
    "xig": "xi gamma",
    "z": "zeta",
    "zd": "zeta delta",
    "ze": "zeta epsilon",
    "zg": "zeta gamma",
}


class Chapter(models.Model, EmailSignalMixin):
    class Meta:
        ordering = [
            "name",
        ]

    TYPES = [
        ("semester", "Semester"),
        ("quarter", "Quarter"),
    ]

    class RECOGNITION(Enum):
        fraternity = ("fraternity", "Recognized as a Fraternity")
        org = ("org", "Recognized as a Student Organization NOT a Fraternity")
        other = ("other", "Recognized but not as a Fraternity or Student Organization")
        not_rec = ("not_rec", "Not Recognized by University")

        @classmethod
        def get_value(cls, member):
            if member == "not":
                member = "not_rec"
            return cls[member.lower()].value[1]

    class SURCHARGE(EnumClass):
        L1a = (
            "L1a",
            "Between 51% and 75% of prior-year new members completed the online health and safety programming",
        )
        L1b = (
            "L1b",
            "Between 26% and 50% of prior-year new members completed the online health and safety programming",
        )
        L1c = (
            "L1c",
            "Between 0% and 25% of prior-year new members completed the online health and safety programming",
        )
        none = (
            "none",
            ">75% of prior-year new members completed the online health and safety programming",
        )

    name = models.CharField(max_length=50)
    modified = models.DateTimeField(auto_now=True)
    region = models.ForeignKey(
        Region, on_delete=models.PROTECT, related_name="chapters"
    )
    slug = models.SlugField(max_length=50, null=True, default=None, unique=True)
    email = models.EmailField(_("email address"), blank=True)
    email_regent = models.EmailField(
        _("Regent Generic email address"),
        blank=True,
        help_text="A generic email used for communication, NOT the member email",
    )
    house = models.BooleanField(
        _("Does your chapter have a house?"),
        default=False,
        blank=True,
        null=True,
    )
    email_vice_regent = models.EmailField(
        _("Vice Regent Generic email address"),
        blank=True,
        help_text="A generic email used for communication, NOT the member email",
    )
    email_treasurer = models.EmailField(
        _("Treasurer Generic email address"),
        blank=True,
        help_text="A generic email used for communication, NOT the member email",
    )
    email_scribe = models.EmailField(
        _("Scribe Generic email address"),
        blank=True,
        help_text="A generic email used for communication, NOT the member email",
    )
    email_corresponding_secretary = models.EmailField(
        _("Corresponding Secretary Generic email address"),
        blank=True,
        help_text="A generic email used for communication, NOT the member email",
    )
    website = models.URLField(
        blank=True,
        help_text="You must include the full URL including https:// or http://",
    )
    facebook = models.URLField(
        blank=True,
        help_text="You must include the full URL including https:// or http://",
    )
    address_contact = models.CharField(
        max_length=100,
        help_text="Name of person to contact at address for deliveries",
    )
    phone_regex = RegexValidator(
        regex=r"^\+?1?\d{9,15}$",
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.",
    )
    address_phone_number = models.CharField(
        validators=[phone_regex],
        max_length=17,
        help_text="Phone number to contact at address for deliveries."
        "Format: 9999999999 no spaces, dashes, etc.",
    )
    address = AddressField(
        verbose_name=_("Mailing Address"),
        help_text="We periodically need to mail things (shingles, badges, etc) to your chapter.",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    balance = models.DecimalField(
        default=0, decimal_places=2, max_digits=7, help_text="Balance chapter owes."
    )
    balance_date = models.DateField(auto_now_add=True)
    tax = models.PositiveIntegerField(
        blank=True,
        null=True,
        unique=True,
        help_text="Tax number, if chapter participates in group exemption.",
    )
    greek = models.CharField(
        max_length=10, blank=True, help_text="Greek letter abbreviation"
    )
    active = models.BooleanField(default=True)
    candidate_chapter = models.BooleanField(default=False)
    extra_approval = models.BooleanField(
        default=False,
        help_text="Does this chapter require extra approval of automated tasks",
    )
    school = models.CharField(max_length=50, blank=True, unique=True)
    latitude = models.DecimalField(
        max_digits=22, decimal_places=16, blank=True, null=True
    )
    longitude = models.DecimalField(
        max_digits=22, decimal_places=16, blank=True, null=True
    )
    school_type = models.CharField(default="semester", max_length=10, choices=TYPES)
    council = models.CharField(
        verbose_name=_("Name of Council"),
        help_text="The name of the council of which your Chapter is a member, "
        + "for example the IFC or PFC.  Please write 'none' if you "
        + "are not recognized as a Fraternity or not a member of a council.",
        default="none",
        max_length=55,
    )
    recognition = models.CharField(
        verbose_name=_("University Recognition"),
        help_text="Please indicate if your chapter is recognized by your host college or university.",
        default="not_rec",
        max_length=10,
        choices=[x.value for x in RECOGNITION],
    )
    health_safety_surcharge = models.CharField(
        help_text="Surcharge for chapters not completing X% online health and safety programming",
        max_length=10,
        default="none",
        choices=[x.value for x in SURCHARGE],
    )
    nme_file_id = models.CharField(
        verbose_name=_("NME File ID"),
        help_text="The Google Drive file id for the new member education program",
        default="none",
        max_length=55,
    )

    def __str__(self):
        return f"{self.name}"  # in {self.region} Region at {self.school}

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def account(self):
        suffix = "Ch"
        if self.candidate_chapter:
            suffix = "Co"
        return f"{self.greek}0{suffix}"

    @property
    def full_name(self):
        suffix = "Chapter"
        if self.candidate_chapter:
            suffix = "Candidate Chapter"
        return f"{self.name} {suffix}"

    @classmethod
    def chapter_choices(cls):
        chapters = []
        try:
            chapters = [
                (chapter.slug, chapter.name.title())
                for chapter in cls.objects.exclude(active=False)
            ]
        except ProgrammingError:
            # Likely the database hasn't been setup yet?
            warnings.warn("Could not find chapter relation")
        chapters.sort(key=lambda tup: tup[1])
        return chapters

    def get_actives_for_date(self, date):
        # Do not annotate, need the queryset not a list
        return self.members.filter(
            status__status__in=[
                "active",
                "activepend",
                "alumnipend",
                "pendexpul",
                "activeCC",
            ],
            status__start__lte=date,
            status__end__gte=date,
        ).distinct()

    def notes_filtered(self, current_user):
        notes = self.notes.exclude(parent__isnull=False)
        if not current_user.is_council_officer():
            notes = notes.exclude(restricted=True)
        return notes

    def events_by_semester_biennium(self):
        semester_events = {}
        for names, dates in BIENNIUM_DATES.items():
            events = self.events.filter(
                date__lte=dates["end"], date__gte=dates["start"]
            )
            semester_events[names] = events

    def events_last_month(self):
        return self.events.filter(
            date__lte=TODAY_END, date__gte=TODAY_END - timedelta(30)
        )

    def events_semester(self):
        semester_start, semester_end = semester_encompass_start_end_date()
        return self.events.filter(date__lte=semester_end, date__gte=semester_start)

    def initiations_semester(self, given_date):
        semester_start, semester_end = semester_encompass_start_end_date(
            given_date=given_date
        )
        return self.initiations.filter(date__lte=semester_end, date__gte=semester_start)

    def pledges_with_no_init_last_x_months(self, months=6):
        # If there are pledges that have not been initiated in X months
        #   not initiations filed in last X months as 1 person could have been init in a class of X
        return self.pledges(date=TODAY_END - timedelta(30 * months)).filter(
            initiation__isnull=True, depledge__isnull=True
        )

    def pledges_last_x_months(self, months=8):
        from forms.models import Pledge

        return Pledge.objects.filter(
            user__chapter=self,
            created__gte=make_aware(TODAY_END - timedelta(30 * months)),
        )

    def current_members(self):
        return self.actives() | self.pledges()

    @property
    def advisors_external(self):
        # Do not annotate, need the queryset not a list
        all_advisors = self.members.filter(
            current_status__in=[
                "advisor",
            ],
        ).distinct()
        return all_advisors

    @property
    def advisors(self):
        # Do not annotate, need the queryset not a list
        all_advisors = self.members.filter(
            current_status="advisor",
        ) | self.members.filter(
            current_roles__overlap=list(ADVISOR_ROLES),
        )
        all_advisors = all_advisors.annotate(
            role=models.Case(
                models.When(
                    models.Q(current_roles__overlap=list(ADVISOR_ROLES)),
                    Concat(models.Value("Alumni "), "current_roles"),
                ),
                default=models.Value("Faculty Advisor"),
                output_field=models.CharField(),
            )
        )
        return all_advisors

    def active_actives(self):
        # Do not annotate, need the queryset not a list
        """
        Must be only active to change status.
        eg. in prealumn form can not submit change
        for someone already grad (pendalum)
        :return:
        """
        return self.members.filter(
            current_status__in=["active", "activepend", "pendexpul" "activeCC"],
        ).distinct()

    def alumni(self):
        # Do not annotate, need the queryset not a list
        return self.members.filter(
            current_status__in=["alumni", "alumniCC"],
        ).distinct()

    def actives(self):
        # Do not annotate, need the queryset not a list
        return self.members.filter(
            current_status__in=[
                "active",
                "activepend",
                "alumnipend",
                "pendexpul",
                "activeCC",
            ],
        ).distinct()

    def pledges(self, date=TODAY_END):
        # Do not annotate, need the queryset not a list
        return self.members.filter(
            status__status="pnm",
            status__start__lte=date,
            status__end__gte=date,
        ).distinct()

    def pledges_semester(self, given_date):
        """
        This uses forms submitted
        semester_start, semester_end = semester_encompass_start_end_date(
            given_date=given_date
        )
        return self.members.filter(
            pledge_form__created__lte=semester_end,
            pledge_form__created__gte=semester_start,
        )
        """
        # started pledge status in this semester
        semester_start, semester_end = semester_encompass_start_end_date(
            given_date=given_date
        )
        dates = dict(status__start__lte=semester_end, status__start__gte=semester_start)
        return self.members.filter(status__status="pnm", **dates)

    def graduates(self, given_date):
        # Alumni that started in this semester
        semester_start, semester_end = semester_encompass_start_end_date(
            given_date=given_date
        )
        dates = dict(status__start__lte=semester_end, status__start__gte=semester_start)
        return self.members.filter(status__status="alumni", **dates).distinct()

    def depledges(self):
        return self.members.exclude(
            depledge__isnull=True,
        ).distinct()

    def gpas(self):
        return self.current_members().filter(gpas__year__gte=BIENNIUM_START)

    def orgs(self):
        return self.current_members().filter(orgs__end__gte=BIENNIUM_START_DATE)

    def service_hours(self):
        return self.current_members().filter(service_hours__year__gte=BIENNIUM_START)

    def get_current_officers(self):
        return self.members.filter(current_roles__overlap=CHAPTER_ROLES)

    def get_current_officers_council(self):
        officers = self.members.filter(
            current_roles__overlap=list(CHAPTER_OFFICER),
        )
        previous = False
        date = TODAY_END
        if officers.count() < 2:
            # If there are not enough previous officers
            # get officers from last 8 months
            previous_officers = self.members.filter(
                roles__role__in=CHAPTER_OFFICER,
                roles__end__gte=TODAY_END - timedelta(30 * 8),
            )
            officers = previous_officers | officers
            previous = True
            date = TODAY_END - timedelta(30 * 8)
        return annotate_role_status(officers, date=date), previous

    def get_current_officers_council_specific(self, role_specific=None):
        officers, previous = self.get_current_officers_council()
        roles = []
        if role_specific is None:
            role_list = [
                "regent",
                "scribe",
                "vice regent",
                "treasurer",
                "corresponding secretary",
            ]
        else:
            role_list = role_specific
        for role in role_list:
            query = models.Q(current_roles__contains=[role])
            if previous:
                query |= models.Q(old_roles__contains=role)
            user = officers.filter(query).first()
            roles.append(user)
        return roles  # [regent, scribe, vice, treasurer, corsec]

    def council_emails(self):
        officers = self.get_current_officers_council_specific()
        emails = set([officer.email for officer in officers if officer]) | set(
            self.get_generic_chapter_emails()
        )
        return {email for email in emails if email}

    def get_email_specific(self, roles=None):
        # Get the generic and current cor sec emails
        if roles is None:
            roles = [
                "regent",
                "scribe",
                "vice regent",
                "treasurer",
                "corresponding secretary",
            ]
        currents = self.get_current_officers_council_specific(role_specific=roles)
        emails = {getattr(self, f"email_{role.replace(' ', '_')}") for role in roles}
        for current in currents:
            if current:
                emails.add(current.email)
                emails.add(current.email_school)
        return {email for email in emails if email}

    def get_generic_chapter_emails(self):
        return [
            self.email_regent,
            self.email_scribe,
            self.email_vice_regent,
            self.email_treasurer,
            self.email_corresponding_secretary,
            self.email,
        ]

    def get_current_and_future(self):
        # list all officers that currently hold an executive board position
        # current and future
        officers = self.members.filter(
            roles__role__in=CHAPTER_OFFICER,
            roles__end__gte=TODAY_END,
        ).prefetch_related("roles")
        current_and_future_regent = officers.filter(roles__role="regent")
        current_and_future_scribe = officers.filter(roles__role="scribe")
        current_and_future_vice = officers.filter(roles__role="vice regent")
        current_and_future_treasurer = officers.filter(roles__role="treasurer")
        current_and_future_corsec = officers.filter(
            roles__role="corresponding secretary"
        )
        return (
            current_and_future_regent,
            current_and_future_corsec,
            current_and_future_scribe,
            current_and_future_treasurer,
            current_and_future_vice,
        )

    def get_previous_officers(self):
        # list the most recent officer that held position
        previous_officers = self.members.filter(
            roles__role__in=CHAPTER_OFFICER,
            roles__end__gte=TODAY_END
            - timedelta(30 * 8),  # they ended their role in the last 8 months
        ).prefetch_related("roles")
        past_regent = (
            previous_officers.filter(roles__role="regent")
            .order_by("roles__end")
            .first()
        )
        past_scribe = (
            previous_officers.filter(roles__role="scribe")
            .order_by("roles__end")
            .first()
        )
        past_vice = (
            previous_officers.filter(roles__role="vice regent")
            .order_by("roles__end")
            .first()
        )
        past_treasurer = (
            previous_officers.filter(roles__role="treasurer")
            .order_by("roles__end")
            .first()
        )
        past_corsec = (
            previous_officers.filter(roles__role="corresponding secretary")
            .order_by("roles__end")
            .first()
        )

        return past_regent, past_corsec, past_scribe, past_treasurer, past_vice

    def get_about_expired_coucil(self):
        officers_to_update, members_to_notify, emails = [], [], []
        # officer_to_update is a list of all officers that need to be updated on the CMT
        # members_to_notify is a list of members that currently hold and/or held within the last eight months
        # the officer position that needs to be updated
        (
            past_regent,
            past_corsec,
            past_scribe,
            past_treasurer,
            past_vice,
        ) = self.get_previous_officers()
        # gathers past officers by position
        (
            current_and_future_regent,
            current_and_future_corsec,
            current_and_future_scribe,
            current_and_future_treasurer,
            current_and_future_vice,
        ) = self.get_current_and_future()
        # gathers current and future officers by position

        # dictionary that contains all the chapter officer positions as a key with values of type tuple
        current_past = {
            "regent": (
                current_and_future_regent,
                past_regent,
            ),
            "vice regent": (
                current_and_future_vice,
                past_vice,
            ),
            "corresponding secretary": (
                current_and_future_corsec,
                past_corsec,
            ),
            "scribe": (
                current_and_future_scribe,
                past_scribe,
            ),
            "treasurer": (
                current_and_future_treasurer,
                past_treasurer,
            ),
        }

        # position is the key of the dictionary that contains chapter officer positions while
        # info is the value that contains the tuple
        for position, info in current_past.items():
            current_and_future, past = info
            # current_and_future holds all the members that currenty hold a specific officer position
            # past holds the member that most recently held the officer position
            # we want to get officers @ 30, @14 and then every day < 5 Urgent
            if current_and_future:
                future_30_days = current_and_future.filter(
                    roles__end__gte=TODAY_END + timedelta(30),
                )
                # future holds the officer who is set to expire after 30 days
                if not future_30_days:
                    future_5_days = current_and_future.filter(
                        roles__end__gte=TODAY_END + timedelta(5),
                    )
                    current = current_and_future.first()
                    already_notified = SentNotification.objects.filter(
                        notification_class="users.notifications.OfficerUpdateReminder",
                        recipients__icontains=current.email,
                        date_sent__gte=TODAY_END - timedelta(7),
                    )
                    if not future_5_days or not already_notified:
                        # only notify every 7 days or every day within 5
                        # current hold the officer who is set to expire within the
                        print(
                            f"    {position} Not notified or 5 days, {already_notified=}"
                        )
                        members_to_notify.append(current)
                    # There could be other positions to notify,
                    # this position still needs to be updated just not notify the members
                    officers_to_update.append(position)
            else:
                print(f"    {position} No current or future")
                officers_to_update.append(position)
                if past:
                    members_to_notify.append(past)
        if members_to_notify:
            # Start with all chapter emails and generic emails
            emails = [email for email in self.get_generic_chapter_emails() if email]
            emails.extend([user.email for user in members_to_notify if user])
            print("    Emails: ", emails)
            print(f"    {officers_to_update=}")
            print(f"    {members_to_notify=}")
        return emails, officers_to_update

    def next_badge_number(self):
        # Jan 2019 highest badge number was Mu with 1754
        max_badge = self.members.filter(~models.Q(badge_number__gte=5000)).aggregate(
            models.Max("badge_number")
        )
        max_badge = max_badge["badge_number__max"]
        if max_badge is None:
            max_badge = 0
        max_badge += 1
        return max_badge

    @property
    def next_advisor_number(self):
        badge_numbers = list(
            self.members.filter(
                badge_number__gte=7000, badge_number__lte=7999
            ).values_list("badge_number", flat=True)
        )
        if not badge_numbers:
            badge_numbers.append(6999)
        badge_number = max(badge_numbers) + 1
        return badge_number

    @classmethod
    def schools(cls):
        try:
            return [
                (school["pk"], school["school"])
                for school in cls.objects.values("school", "pk").order_by("school")
            ]
        except ProgrammingError:  # pragma: no cover
            # Likely the database hasn't been setup yet?
            warnings.warn("Could not find school relation")
            return []

    @classmethod
    def get_school_chapter(cls, school_name):
        try:
            return cls.objects.get(
                school=school_name,
            )
        except cls.DoesNotExist:
            warnings.warn("Could not find school")
            return None

    def sync_dues(self, request):
        """
        This will sync with quickbooks
        """
        client = get_quickbooks_client()
        chapter_name = self.name
        if "Chapter" in chapter_name:
            chapter_name = chapter_name.replace(" Chapter", "")
        customer = Customer.query(
            select=f"SELECT * FROM Customer WHERE CompanyName LIKE '{chapter_name} chapter%'",
            qb=client,
        )
        if customer:
            customer = customer[0]
        else:
            messages.add_message(
                request,
                messages.ERROR,
                f"Quickbooks Customer matching name: '{chapter_name} Chapter...' not found",
            )
            return
        invoice, linenumber_count = invoice_search("1", customer, client)
        count = self.active_actives().count()
        if not self.candidate_chapter:
            # D1; Service; Semiannual Chapter Dues payable @ $80 each # Minimum per chapter is $1600.
            minimum = Config.get_value("ChapterMinimum")
            line = create_line(
                count, linenumber_count, name="D1", minimum=minimum, client=client
            )
            l1_min = Config.get_value("HealthSafetyMinimum_chapter")
            if self.house:
                l1_min = Config.get_value("HealthSafetyMinimum_house")
        else:
            # D2; Service; Semiannual Candidate Chapter Dues
            line = create_line(count, linenumber_count, name="D2", client=client)
            l1_min = Config.get_value("HealthSafetyMinimum_candidatechapter")
        linenumber_count += 1
        invoice.Line.append(line)
        # L1; Service; Health and Safety Assessment - Semesterly
        line = create_line(
            count, linenumber_count, name="L1", minimum=l1_min, client=client
        )
        linenumber_count += 1
        invoice.Line.append(line)
        if self.health_safety_surcharge != "none":
            line = create_line(
                line.Amount,
                linenumber_count,
                name=self.health_safety_surcharge,
                client=client,
            )
            invoice.Line.append(line)
        memo = f"Actives: {count}; Surcharge: {self.SURCHARGE.get_value(self.health_safety_surcharge)}"
        memo = memo[0:999]
        invoice.CustomerMemo.value = memo
        invoice.DeliveryInfo = None
        invoice_obj = invoice.save(qb=client)
        attachment_path = self.generate_dues_attachment(file_obj=True)
        attachment = Attachable()
        attachable_ref = AttachableRef()
        attachable_ref.EntityRef = invoice.to_ref()
        attachable_ref.IncludeOnSend = True
        attachment.AttachableRef.append(attachable_ref)
        attachment.FileName = attachment_path.name
        attachment._FilePath = str(attachment_path.absolute())
        attachment.ContentType = "text/csv"
        attachment.save(qb=client)
        if attachment_path.exists():
            attachment_path.unlink()  # Delete the file when we are done
        return invoice_obj.DocNumber

    def reminder_dues(self):
        attachment = self.generate_dues_attachment()
        return DuesReminder(self, attachment).send()

    def generate_dues_attachment(self, response=None, file_obj=False):
        from users.tables import UserTable

        time_name = datetime.datetime.now().strftime("%Y%m%d")
        filename = f"{self}_{time_name}_dues.csv"
        if response is not None:
            dues_file = response
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            out = None
        else:
            dues_file = io.StringIO()
            dues_mail = MIMEBase("application", "csv")
            dues_mail.add_header("Content-Disposition", "attachment", filename=filename)
        table = UserTable(data=self.active_actives())
        writer = csv.writer(dues_file)
        writer.writerows(table.as_values())
        if response is None and not file_obj:
            dues_mail.set_payload(dues_file.getvalue())
            out = dues_mail
        elif file_obj:
            filepath = Path(r"exports/" + filename)
            with open(filepath, mode="w", newline="") as f:
                print(dues_file.getvalue(), file=f)
            out = filepath
        return out


class ChapterCurricula(models.Model):
    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="curricula"
    )
    approved = models.BooleanField(default=True)
    major = models.CharField(max_length=100)

    def __str__(self):
        return self.major
