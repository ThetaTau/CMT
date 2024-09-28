from dj_anonymizer.register_models import (
    register_skip,
    AnonymBase,
    register_anonym,
    register_clean,
)
from dj_anonymizer import fields
from faker import Factory

from forms.models import (
    Audit,
    AlumniExclusion,
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
    PledgeProgramProcess,
    HSEducation,
    Bylaws,
)

fake = Factory.create()

register_clean(
    [
        (DisciplinaryAttachment, AnonymBase),
    ]
)

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
        PledgeProgramProcess,
        Bylaws,
    ]
)


class StatusChangeAnonym(AnonymBase):
    email_work = fields.string("{seq}@work.com")
    employer = fields.function(fake.company)

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
    form = fields.function(fake.file_path)
    exec_comments = fields.function(fake.sentence)

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
    signature_del = fields.function(fake.name)
    signature_alt = fields.function(fake.name)
    signature_o1 = fields.function(fake.name)
    signature_o2 = fields.function(fake.name)

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
    ledger_sheet = fields.function(fake.file_path)

    class Meta:
        exclude_fields = ["balance_due_currency", "balance_due", "modified", "created"]


class RiskManagementAnonym(AnonymBase):
    typed_name = fields.function(fake.name)

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
    letter = fields.function(fake.file_path)
    signature = fields.function(fake.name)
    signature_o1 = fields.function(fake.name)
    signature_o2 = fields.function(fake.name)
    exec_comments = fields.function(fake.sentence)

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
    date_graduation = fields.function(fake.date_object)
    roll = fields.function(fake.pyint)

    class Meta:
        exclude_fields = ["modified", "created", "gpa", "test_a", "date", "test_b"]


class DisciplinaryAttachmentAnonym(AnonymBase):
    file = fields.function(fake.file_path)

    class Meta:
        pass


class AlumniExclusionAnonym(AnonymBase):
    reason = fields.function(fake.paragraph)
    minutes = fields.function(fake.file_path)
    veto_reason = fields.function(fake.paragraph)

    class Meta:
        exclude_fields = [
            "chapter",
            "regional_director",
            "regional_director_veto",
            "voting_result",
            "date_start",
            "date_end",
            "meeting_date",
            "data",
            "created",
            "flow_class",
            "artifact_object_id",
            "status",
            "modified",
            "id",
            "finished",
        ]


class DisciplinaryProcessAnonym(AnonymBase):
    minutes = fields.function(fake.file_path)
    punishment_other = fields.function(fake.sentence)
    charges = fields.function(fake.paragraph)
    why_take = fields.function(fake.sentence)
    ec_notes = fields.function(fake.sentence)
    final_letter = fields.function(fake.file_path)
    ed_notes = fields.function(fake.sentence)
    charging_letter = fields.function(fake.file_path)
    advisor_name = fields.function(fake.name)
    outcome_letter = fields.function(fake.file_path)
    faculty_name = fields.function(fake.name)
    results_letter = fields.function(fake.file_path)

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
    signature = fields.function(fake.name)
    parent_name = fields.function(fake.name)
    parent_email = fields.string("{seq}@parentemail.com")
    explain_crime = fields.function(fake.sentence)
    relative_members = fields.function(fake.name)
    explain_expelled_org = fields.function(fake.sentence)
    other_tech = fields.function(fake.sentence)
    explain_expelled_college = fields.function(fake.sentence)
    birth_place = fields.function(fake.city)
    other_frat = fields.function(fake.sentence)
    other_greeks = fields.function(fake.sentence)
    other_degrees = fields.function(fake.sentence)
    other_college = fields.function(fake.sentence)

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
            "bill",
        ]


class DepledgeAnonym(AnonymBase):
    reason_other = fields.function(fake.sentence)
    meeting_not = fields.function(fake.sentence)
    informed = fields.function(fake.sentence)
    concerns = fields.function(fake.sentence)
    returned_other = fields.function(fake.sentence)
    extra_notes = fields.function(fake.sentence)

    class Meta:
        exclude_fields = [
            "modified",
            "created",
            "reason",
            "date",
            "meeting_held",
            "meeting_date",
            "meeting_attend",
            "returned_items",
        ]


class HSEducationAnonym(AnonymBase):
    first_name = fields.function(fake.first_name)
    last_name = fields.function(fake.last_name)
    email = fields.string("{seq}@test.com")
    phone_number = fields.function(fake.msisdn)

    class Meta:
        exclude_fields = [
            "chapter",
            "report",
            "program_date",
            "category",
            "title",
            "approval",
            "approval_comments",
            "flow_class",
            "finished",
            "modified",
            "created",
            "data",
            "status",
            "artifact_object_id",
            "id",
        ]


register_anonym(
    [
        (DisciplinaryProcess, DisciplinaryProcessAnonym),
        (AlumniExclusion, AlumniExclusionAnonym),
        (Depledge, DepledgeAnonym),
        (Pledge, PledgeAnonym),
        (Initiation, InitiationAnonym),
        (ResignationProcess, ResignationProcessAnonym),
        (RiskManagement, RiskManagementAnonym),
        (CollectionReferral, CollectionReferralAnonym),
        (Convention, ConventionAnonym),
        (PrematureAlumnus, PrematureAlumnusAnonym),
        (StatusChange, StatusChangeAnonym),
        (HSEducation, HSEducationAnonym),
    ]
)
