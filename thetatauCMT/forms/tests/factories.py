import factory
from ..models import (
    Badge,
    Guard,
    PledgeProgram,
    Initiation,
    Depledge,
    StatusChange,
    ChapterReport,
    RiskManagement,
    Audit,
    Pledge,
    PrematureAlumnus,
    InitiationProcess,
    Convention,
    PledgeProcess,
    OSM,
)
from ..flows import (
    PrematureAlumnusFlow,
    InitiationProcessFlow,
    ConventionFlow,
    PledgeProcessFlow,
    OSMFlow,
)
from chapters.tests.factories import ChapterFactory
from users.tests.factories import UserFactory
from submissions.tests.factories import SubmissionFactory


class BadgeFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("sentence", nb_words=3)
    code = factory.Faker("pystr")
    description = factory.Faker("paragraph", nb_sentences=5)
    cost = factory.Faker("pyfloat", min_value=0, max_value=500)

    class Meta:
        model = Badge


class GuardFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("sentence", nb_words=3)
    code = factory.Faker("pystr")
    letters = factory.Faker(
        "random_element", elements=[item[0] for item in Guard.NUM_LETTERS]
    )
    description = factory.Faker("paragraph", nb_sentences=5)
    cost = factory.Faker("pyfloat", min_value=0, max_value=500)

    class Meta:
        model = Guard


class PledgeProgramFactory(factory.django.DjangoModelFactory):
    chapter = factory.SubFactory(ChapterFactory)
    remote = factory.Faker("boolean")
    date_complete = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    date_initiation = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    weeks = factory.Faker("random_int", max=30)
    weeks_left = factory.Faker("random_int", max=30)
    status = factory.Faker(
        "random_element", elements=[item.value[0] for item in PledgeProgram.STATUS]
    )
    manual = factory.Faker(
        "random_element", elements=[item.value[0] for item in PledgeProgram.MANUALS]
    )

    class Meta:
        model = PledgeProgram


class InitiationFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    date_graduation = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    date = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    roll = factory.Faker("random_int", max=999999999)
    gpa = factory.Faker("pyfloat", min_value=0, max_value=20)
    test_a = factory.Faker("random_int", max=100)
    test_b = factory.Faker("random_int", max=100)
    badge = factory.SubFactory(BadgeFactory)
    guard = factory.SubFactory(GuardFactory)

    class Meta:
        model = Initiation


class DepledgeFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    reason = factory.Faker(
        "random_element", elements=[item.value[0] for item in Depledge.REASONS]
    )
    date = factory.Faker("date_between", start_date="-4y", end_date="+4y")

    class Meta:
        model = Depledge


class StatusChangeFactory(factory.django.DjangoModelFactory):
    created = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    modified = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    user = factory.SubFactory(UserFactory)
    reason = factory.Faker(
        "random_element", elements=[item.value[0] for item in Depledge.REASONS]
    )
    degree = factory.Faker(
        "random_element", elements=[item.value[0] for item in StatusChange.DEGREES]
    )
    date_start = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    date_end = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    employer = factory.Faker("sentence", nb_words=3)
    miles = factory.Faker("random_int", max=5000)
    email_work = factory.Faker("email")

    @factory.post_generation
    def new_school(self, create, extracted, **kwargs):
        return factory.SubFactory(ChapterFactory)

    class Meta:
        model = StatusChange


class ChapterReportFactory(factory.django.DjangoModelFactory):
    created = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    modified = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    year = factory.Faker(
        "random_element", elements=[item[0] for item in ChapterReport.YEARS]
    )
    term = factory.Faker(
        "random_element", elements=[item.value[0] for item in ChapterReport.TERMS]
    )
    user = factory.SubFactory(UserFactory)
    chapter = factory.SubFactory(ChapterFactory)
    report = factory.django.FileField(filename="test.pdf")

    class Meta:
        model = ChapterReport


class RiskManagementFactory(factory.django.DjangoModelFactory):
    year = factory.Faker(
        "random_element", elements=[item[0] for item in RiskManagement.YEARS]
    )
    term = factory.Faker(
        "random_element", elements=[item.value[0] for item in RiskManagement.TERMS]
    )
    user = factory.SubFactory(UserFactory)
    role = factory.Faker("name")
    submission = factory.SubFactory(SubmissionFactory)
    date = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    alcohol = factory.Faker("boolean")
    hosting = factory.Faker("boolean")
    monitoring = factory.Faker("boolean")
    member = factory.Faker("boolean")
    officer = factory.Faker("boolean")
    abusive = factory.Faker("boolean")
    hazing = factory.Faker("boolean")
    substances = factory.Faker("boolean")
    high_risk = factory.Faker("boolean")
    transportation = factory.Faker("boolean")
    property_management = factory.Faker("boolean")
    guns = factory.Faker("boolean")
    trademark = factory.Faker("boolean")
    social = factory.Faker("boolean")
    indemnification = factory.Faker("boolean")
    agreement = factory.Faker("boolean")
    electronic_agreement = factory.Faker("boolean")
    photo_release = factory.Faker("boolean")
    arbitration = factory.Faker("boolean")
    dues = factory.Faker("boolean")
    terms_agreement = factory.Faker("boolean")
    typed_name = factory.Faker("name")

    class Meta:
        model = RiskManagement


class AuditFactory(factory.django.DjangoModelFactory):
    created = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    modified = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    year = factory.Faker(
        "random_element", elements=[item[0] for item in ChapterReport.YEARS]
    )
    term = factory.Faker(
        "random_element", elements=[item.value[0] for item in ChapterReport.TERMS]
    )
    user = factory.SubFactory(UserFactory)
    dues_member = factory.Faker("pyfloat", min_value=0, max_value=5000)
    dues_pledge = factory.Faker("pyfloat", min_value=0, max_value=5000)
    frequency = factory.Faker(
        "random_element", elements=["month", "semester", "quarter", "year"],
    )
    payment_plan = factory.Faker("boolean")
    cash_book = factory.Faker("boolean")
    cash_register = factory.Faker("boolean")
    member_account = factory.Faker("boolean")
    cash_book_reviewed = factory.Faker("boolean")
    cash_register_reviewed = factory.Faker("boolean")
    member_account_reviewed = factory.Faker("boolean")
    balance_checking = factory.Faker("pyfloat", min_value=0, max_value=500000)
    balance_savings = factory.Faker("pyfloat", min_value=0, max_value=5000)
    debit_card = factory.Faker("boolean")
    debit_card_access = factory.Faker("sentence")
    agreement = factory.Faker("boolean")

    class Meta:
        model = Audit


class PledgeFactory(factory.django.DjangoModelFactory):
    created = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    modified = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    user = factory.SubFactory(UserFactory)
    signature = factory.LazyAttribute(
        lambda o: f"{o.user.first_name}{o.user.last_name}"
    )
    parent_name = factory.Faker("name")
    birth_place = factory.Faker("city")
    other_degrees = factory.Faker("sentence")
    relative_members = factory.Faker("sentence")
    other_greeks = factory.Faker("sentence")
    other_tech = factory.Faker("sentence")
    other_frat = factory.Faker("sentence")
    other_college = factory.Faker("sentence")
    explain_expelled_org = factory.Faker("paragraph")
    explain_expelled_college = factory.Faker("paragraph")
    explain_crime = factory.Faker("paragraph")
    loyalty = factory.Faker("boolean")
    not_honor = factory.Faker("boolean")
    accountable = factory.Faker("boolean")
    life = factory.Faker("boolean")
    unlawful = factory.Faker("boolean")
    unlawful_org = factory.Faker("boolean")
    brotherhood = factory.Faker("boolean")
    engineering = factory.Faker("boolean")
    engineering_grad = factory.Faker("boolean")
    payment = factory.Faker("boolean")
    attendance = factory.Faker("boolean")
    harmless = factory.Faker("boolean")
    alumni = factory.Faker("boolean")
    honest = factory.Faker("boolean")

    class Meta:
        model = Pledge


class PrematureAlumnusFactory(factory.django.DjangoModelFactory):
    flow_class = PrematureAlumnusFlow
    user = factory.SubFactory(UserFactory)
    form = factory.django.FileField(filename="test.pdf")
    good_standing = factory.Faker("boolean")
    financial = factory.Faker("boolean")
    semesters = factory.Faker("boolean")
    lifestyle = factory.Faker("boolean")
    consideration = factory.Faker("boolean")
    prealumn_type = factory.Faker(
        "random_element", elements=[item.value[0] for item in PrematureAlumnus.TYPES]
    )
    approved_exec = factory.Faker("boolean")
    exec_comments = factory.Faker("sentence")
    vote = factory.Faker("boolean")

    class Meta:
        model = PrematureAlumnus


class InitiationProcessFactory(factory.django.DjangoModelFactory):
    flow_class = InitiationProcessFlow
    invoice = factory.Faker("random_int", max=999999999)
    chapter = factory.SubFactory(ChapterFactory)

    @factory.post_generation
    def add_initiations(self, create, extracted, **kwargs):
        initiations = InitiationFactory.create_batch(5)
        for initiation in initiations:
            self.initiations.add(initiation)

    class Meta:
        model = InitiationProcess


class ConventionFactory(factory.django.DjangoModelFactory):
    flow_class = ConventionFlow
    meeting_date = factory.Faker("date_between", start_date="-1y", end_date="-1d")
    delegate = factory.SubFactory(UserFactory)
    alternate = factory.SubFactory(UserFactory)
    understand_del = factory.Faker("boolean")
    understand_alt = factory.Faker("boolean")
    chapter = factory.SubFactory(ChapterFactory)
    officer1 = factory.SubFactory(UserFactory)
    officer2 = factory.SubFactory(UserFactory)
    signature_del = factory.LazyAttribute(lambda o: f"{o.name} Signature")
    signature_alt = factory.LazyAttribute(lambda o: f"{o.name} Signature")
    signature_o1 = factory.LazyAttribute(lambda o: f"{o.name} Signature")
    signature_o2 = factory.LazyAttribute(lambda o: f"{o.name} Signature")
    approved_o1 = factory.Faker("boolean")
    approved_o2 = factory.Faker("boolean")

    class Meta:
        model = Convention


class PledgeProcessFactory(factory.django.DjangoModelFactory):
    flow_class = PledgeProcessFlow
    invoice = factory.Faker("random_int", max=999999999)
    chapter = factory.SubFactory(ChapterFactory)

    class Meta:
        model = PledgeProcess

    @factory.post_generation
    def add_pledges(self, create, extracted, **kwargs):
        pledges = PledgeFactory.create_batch(5)
        for pledge in pledges:
            self.pledges.add(pledge)


class OSMFactory(factory.django.DjangoModelFactory):
    flow_class = OSMFlow
    meeting_date = factory.Faker("date_between", start_date="-1y", end_date="-1d")
    nominate = factory.SubFactory(UserFactory)
    selection_process = factory.Faker("paragraph")
    chapter = factory.SubFactory(ChapterFactory)
    officer1 = factory.SubFactory(UserFactory)
    officer2 = factory.SubFactory(UserFactory)
    approved_o1 = factory.Faker("boolean")
    approved_o2 = factory.Faker("boolean")

    class Meta:
        model = OSM
