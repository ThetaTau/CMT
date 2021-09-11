from dj_anonymizer.register_models import (
    register_skip,
    AnonymBase,
    register_anonym,
    register_clean,
)
from dj_anonymizer import anonym_field
from faker import Factory

from forms.models import (
    Audit,
    Badge,
    ChapterReport,
    CollectionReferral,
    Convention,
    Depledge,
    DisciplinaryAttachment,
    DisciplinaryProcess,
    Guard,
    Initiation,
    InitiationProcess,
    OSM,
    Pledge,
    PledgeProcess,
    PledgeProgram,
    PrematureAlumnus,
    ResignationProcess,
    ReturnStudent,
    RiskManagement,
    StatusChange,
)

fake = Factory.create()

register_clean([DisciplinaryAttachment])

register_skip(
    [
        Audit,
        Badge,
        ChapterReport,
        Depledge,
        Guard,
        InitiationProcess,
        OSM,
        PledgeProcess,
        PledgeProgram,
        ReturnStudent,
    ]
)


class StatusChangeAnonym(AnonymBase):
    email_work = anonym_field.string("{seq}@work.com")
    employer = anonym_field.function(fake.company)

    class Meta:
        exclude_fields = [
            "date_end",
            "miles",
            "created",
            "modified",
            "reason",
            "date_start",
            "degree",
        ]


class PrematureAlumnusAnonym(AnonymBase):
    form = anonym_field.function(fake.file_path)
    exec_comments = anonym_field.function(fake.sentence)

    class Meta:
        exclude_fields = [
            "created",
            "data",
            "status",
            "financial",
            "semesters",
            "prealumn_type",
            "good_standing",
            "flow_class",
            "id",
            "approved_exec",
            "artifact_object_id",
            "vote",
            "consideration",
            "lifestyle",
            "finished",
        ]


class ConventionAnonym(AnonymBase):
    signature_del = anonym_field.function(fake.name)
    signature_alt = anonym_field.function(fake.name)
    signature_o1 = anonym_field.function(fake.name)
    signature_o2 = anonym_field.function(fake.name)

    class Meta:
        exclude_fields = [
            "status",
            "approved_o1",
            "meeting_date",
            "created",
            "finished",
            "understand_alt",
            "flow_class",
            "term",
            "year",
            "understand_del",
            "data",
            "id",
            "approved_o2",
            "artifact_object_id",
        ]


class CollectionReferralAnonym(AnonymBase):
    ledger_sheet = anonym_field.function(fake.file_path)

    class Meta:
        exclude_fields = ["balance_due_currency", "balance_due", "modified", "created"]


class RiskManagementAnonym(AnonymBase):
    typed_name = anonym_field.function(fake.name)

    class Meta:
        exclude_fields = [
            "substances",
            "photo_release",
            "arbitration",
            "fines",
            "social",
            "hosting",
            "term",
            "terms_agreement",
            "officer",
            "high_risk",
            "dues",
            "trademark",
            "guns",
            "role",
            "alcohol",
            "member",
            "hazing",
            "property_management",
            "year",
            "date",
            "transportation",
            "electronic_agreement",
            "agreement",
            "abusive",
            "indemnification",
            "monitoring",
        ]


class ResignationProcessAnonym(AnonymBase):
    letter = anonym_field.function(fake.file_path)
    signature = anonym_field.function(fake.name)
    signature_o1 = anonym_field.function(fake.name)
    signature_o2 = anonym_field.function(fake.name)
    exec_comments = anonym_field.function(fake.sentence)

    class Meta:
        exclude_fields = [
            "id",
            "flow_class",
            "approved_o2",
            "returned",
            "resign",
            "obligation",
            "return_evidence",
            "status",
            "artifact_object_id",
            "secrets",
            "financial",
            "data",
            "approved_exec",
            "expel",
            "fee",
            "created",
            "finished",
            "good_standing",
            "approved_o1",
            "fee_paid",
        ]


class InitiationAnonym(AnonymBase):
    date_graduation = anonym_field.function(fake.date_object)
    roll = anonym_field.function(fake.pyint)

    class Meta:
        exclude_fields = ["modified", "created", "gpa", "test_a", "date", "test_b"]


class DisciplinaryAttachmentAnonym(AnonymBase):
    file = anonym_field.function(fake.file_path)

    class Meta:
        pass


class DisciplinaryProcessAnonym(AnonymBase):
    minutes = anonym_field.function(fake.file_path)
    punishment_other = anonym_field.function(fake.sentence)
    charges = anonym_field.function(fake.paragraph)
    why_take = anonym_field.function(fake.sentence)
    ec_notes = anonym_field.function(fake.sentence)
    final_letter = anonym_field.function(fake.file_path)
    ed_notes = anonym_field.function(fake.sentence)
    charging_letter = anonym_field.function(fake.file_path)
    advisor_name = anonym_field.function(fake.name)
    outcome_letter = anonym_field.function(fake.file_path)
    faculty_name = anonym_field.function(fake.name)
    results_letter = anonym_field.function(fake.file_path)

    class Meta:
        exclude_fields = [
            "take",
            "notify_method",
            "id",
            "guilty",
            "advisor",
            "financial",
            "ed_process",
            "trial_date",
            "send_ec_date",
            "resolve",
            "data",
            "modified",
            "finished",
            "attend",
            "status",
            "flow_class",
            "charges_filed",
            "ec_approval",
            "faculty",
            "artifact_object_id",
            "created",
            "punishment",
            "collect_items",
            "notify_date",
            "notify_results",
            "notify_results_date",
            "rescheduled_date",
            "suspension_end",
        ]


class PledgeAnonym(AnonymBase):
    signature = anonym_field.function(fake.name)
    parent_name = anonym_field.function(fake.name)
    explain_crime = anonym_field.function(fake.sentence)
    relative_members = anonym_field.function(fake.name)
    explain_expelled_org = anonym_field.function(fake.sentence)
    other_tech = anonym_field.function(fake.sentence)
    explain_expelled_college = anonym_field.function(fake.sentence)
    birth_place = anonym_field.function(fake.city)
    other_frat = anonym_field.function(fake.sentence)
    other_greeks = anonym_field.function(fake.sentence)
    other_degrees = anonym_field.function(fake.sentence)
    other_college = anonym_field.function(fake.sentence)

    class Meta:
        exclude_fields = [
            "not_honor",
            "attendance",
            "unlawful",
            "created",
            "alumni",
            "modified",
            "life",
            "engineering_grad",
            "payment",
            "honest",
            "harmless",
            "accountable",
            "brotherhood",
            "loyalty",
            "unlawful_org",
            "engineering",
        ]


register_anonym(
    [
        (DisciplinaryProcess, DisciplinaryProcessAnonym),
        (Pledge, PledgeAnonym),
        (Initiation, InitiationAnonym),
        (ResignationProcess, ResignationProcessAnonym),
        (RiskManagement, RiskManagementAnonym),
        (CollectionReferral, CollectionReferralAnonym),
        (Convention, ConventionAnonym),
        (PrematureAlumnus, PrematureAlumnusAnonym),
        (StatusChange, StatusChangeAnonym),
    ]
)
