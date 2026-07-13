"""URL-resolution smoke tests (Phase 0.5.5).

Calls django.urls.reverse() for every named URL in config/urls.py and each
app's urls.py. Catches url() removal, allauth route renames, and
report-builder URL drift without touching the database.

These tests are intentionally database-free — reverse() is pure URL-config
traversal — so they run fast and can serve as a pre-flight check.
"""

import pytest
from django.urls import reverse


def _id(name, kwargs):
    """Generate a readable parametrize ID from a url name + kwargs dict."""
    if kwargs:
        return f"{name}[{','.join(str(k) for k in kwargs)}]"
    return name


# ---------------------------------------------------------------------------
# Master URL table: (url_name, kwargs_dict)
#
# Include every URL that has name= in config/urls.py or an app's urls.py.
# For parameterised routes supply minimal dummy values that satisfy the
# converter type (int→1, slug→"test", str→"testuser", etc.).
# ---------------------------------------------------------------------------

_URL_CASES = [
    # ── config/urls.py — top-level named URLs ─────────────────────────────
    ("zipcode-autocomplete", {}),
    ("home", {}),
    ("about", {}),
    ("help", {}),
    ("electronic_terms", {}),
    ("password_reset", {}),
    ("password_reset_done", {}),
    ("password_reset_complete", {}),
    # uidb64 / token are plain <str> converters — any non-empty values work
    ("password_reset_confirm", {"uidb64": "abc123", "token": "1ab-cd1234"}),
    ("login", {}),
    ("logout", {}),
    ("privacy", {}),
    ("eula", {}),
    ("rmp", {}),
    ("report_redirect", {}),
    ("conventionform", {}),
    ("osmform", {}),
    ("alumniexclusion", {}),
    ("gear", {}),
    ("update_lookup", {}),
    # ── allauth_2fa (path("", include("allauth_2fa.urls"))) ────────────────
    ("two-factor-setup", {}),
    ("two-factor-remove", {}),
    ("two-factor-authenticate", {}),
    ("two-factor-backup-tokens", {}),
    # ── allauth (path("accounts/", include("allauth.urls"))) ──────────────
    # NOTE: account_password_change / account_password_reset no longer exist
    # in allauth 65.x — intentionally omitted; their absence is verified by
    # the auth smoke tests in test_auth_flows.py.
    ("account_login", {}),
    ("account_logout", {}),
    ("account_signup", {}),
    ("account_email", {}),
    ("account_email_verification_sent", {}),
    # ── report_builder (path("report_builder/", include("thetatauCMT.configs.urls"))) ─
    # Two patterns share the name report_download_file; test both kwargs shapes.
    ("report_download_file", {"pk": 1}),
    ("report_download_file", {"pk": 1, "filetype": "csv"}),
    ("report_check_status", {"pk": 1, "task_id": "abc"}),
    ("ajax_add_star", {"pk": 1}),
    ("report_builder_create_copy", {"pk": 1}),
    ("export_to_report", {}),
    ("related_fields", {}),
    ("fields", {}),
    ("generate_report", {"report_id": 1}),
    ("report_update_view", {"pk": 1}),
    ("report_builder", {}),
    # ── users ──────────────────────────────────────────────────────────────
    ("users:list", {}),
    ("users:gpas", {}),
    ("users:service", {}),
    ("users:orgs", {}),
    ("users:redirect", {}),
    ("users:detail", {}),
    ("users:info", {"username": "testuser"}),
    ("users:search", {}),
    ("users:lookup_search", {}),
    ("users:lookup_select", {}),
    ("users:update", {}),
    ("users:update_review", {"pk": 1}),
    ("users:user_verify", {}),
    ("users:autocomplete", {}),
    ("users:alterchapter", {}),
    ("users:sync_email_provider", {"report_id": 1}),
    # ── chapters ───────────────────────────────────────────────────────────
    ("chapters:list", {}),
    ("chapters:redirect", {}),
    ("chapters:detail", {"slug": "test"}),
    # ── regions ────────────────────────────────────────────────────────────
    ("regions:list", {}),
    ("regions:redirect", {}),
    ("regions:detail", {"slug": "test"}),
    ("regions:dashboard", {"slug": "test"}),
    ("regions:officers", {"slug": "test"}),
    ("regions:advisors", {"slug": "test"}),
    ("regions:tasks", {"slug": "test"}),
    # ── events ─────────────────────────────────────────────────────────────
    ("events:list", {}),
    ("events:list_all", {}),
    ("events:add", {}),
    ("events:copy", {"pk": 1}),
    ("events:redirect", {}),
    ("events:update", {"year": 2023, "month": 1, "day": 1, "event_slug": "test"}),
    ("events:detail", {"year": 2023, "month": 1, "day": 1, "slug": "test"}),
    # ── jobs ───────────────────────────────────────────────────────────────
    ("jobs:list", {}),
    ("jobs:search", {}),
    ("jobs:search_filter", {"pk": 1}),
    ("jobs:keyword-autocomplete", {}),
    ("jobs:keyword-autocomplete-ro", {}),
    ("jobs:major-autocomplete", {}),
    ("jobs:add", {}),
    ("jobs:add_search", {}),
    ("jobs:copy", {"pk": 1}),
    ("jobs:redirect", {}),
    ("jobs:update", {"pk": 1}),
    ("jobs:update_search", {"pk": 1}),
    ("jobs:detail", {"pk": 1, "slug": "test"}),
    # ── notes ──────────────────────────────────────────────────────────────
    ("notes:add", {"slug": "test"}),
    ("notes:add_user", {"username": "testuser"}),
    ("notes:detail", {"pk": 1}),
    # ── objectives ─────────────────────────────────────────────────────────
    ("objectives:list", {}),
    ("objectives:create", {}),
    ("objectives:detail", {"pk": 1}),
    # ── trainings ──────────────────────────────────────────────────────────
    ("trainings:list", {}),
    # ── finances ───────────────────────────────────────────────────────────
    ("finances:list", {}),
    ("finances:chapters", {}),
    # ── scores ─────────────────────────────────────────────────────────────
    ("scores:list", {}),
    ("scores:chapterlist", {}),
    ("scores:redirect", {}),
    ("scores:detail", {"slug": "test"}),
    # ── submissions ────────────────────────────────────────────────────────
    ("submissions:list", {}),
    ("submissions:add", {}),
    ("submissions:add-direct", {"slug": "test"}),
    ("submissions:redirect", {}),
    ("submissions:update", {"pk": 1}),
    ("submissions:detail", {"year": 2023, "month": 1, "day": 1, "slug": "test"}),
    ("submissions:gear", {}),
    ("submissions:gearlist", {}),
    ("submissions:gear_detail", {"pk": 1}),
    # ── surveys ────────────────────────────────────────────────────────────
    ("surveys:depledge", {"username": "testuser"}),
    ("surveys:survey-detail", {"slug": "test"}),
    ("surveys:survey-detail-step", {"slug": "test", "step": 1}),
    ("surveys:survey-detail-member", {"slug": "test", "user_pk": "1"}),
    ("surveys:survey-detail-step-member", {"slug": "test", "step": 1, "user_pk": "1"}),
    # ── forms ──────────────────────────────────────────────────────────────
    ("forms:landing", {}),
    ("forms:bylaws", {}),
    ("forms:bylaws_list", {}),
    ("forms:audit", {}),
    ("forms:audit_complete", {"pk": 1}),
    ("forms:education_list", {}),
    ("forms:convention_list", {}),
    ("forms:osm_list", {}),
    ("forms:audit_list", {}),
    ("forms:ajax_load_majors", {}),
    ("forms:pledgeform", {}),
    ("forms:pledgeform-alt", {}),
    ("forms:pledge_program_list", {}),
    ("forms:pledge_program_detail", {"pk": 1}),
    ("forms:alumniexclusion_detail", {"pk": 1}),
    ("forms:alumniexclusion_list", {}),
    ("forms:initiation", {}),
    ("forms:init_selection", {}),
    # Two patterns share the name init_csv; test the shorter form
    ("forms:init_csv", {"process_pk": 1, "csv_type": "badge"}),
    ("forms:shingle_post", {"process_pk": 1}),
    ("forms:init_sync", {"process_pk": 1, "invoice_number": 1}),
    ("forms:pledge_csv", {"process_pk": 1, "csv_type": "badge"}),
    ("forms:pledge_sync", {"process_pk": 1, "invoice_number": 1}),
    ("forms:status", {}),
    ("forms:status_selection", {}),
    ("forms:officer", {}),
    ("forms:natoff", {}),
    ("forms:bill_of_rights_pdf", {"pk": 1}),
    ("forms:bill_of_rights", {"pk": 1}),
    ("forms:roll_book_page", {"pk": 1}),
    ("forms:roll_book_download_all", {}),
    ("forms:set_init_date", {}),
    ("forms:rmp", {}),
    ("forms:rmp_complete", {"pk": 1}),
    ("forms:rmp_list", {}),
    ("forms:discipline", {}),
    ("forms:pledge_program", {}),
    ("forms:discipline_pdftest", {"pk": 1}),
    ("forms:discipline_download", {"process_pk": 1}),
    ("forms:collection", {}),
    ("forms:resignation", {}),
    ("forms:resign_list", {}),
    ("forms:ritual_proficiency", {}),
    ("forms:ritual_proficiency_user_table", {}),
    # ── tasks ──────────────────────────────────────────────────────────────
    ("tasks:list", {}),
    ("tasks:complete", {"pk": 1}),
    ("tasks:detail", {"pk": 1}),
    # ── ballots ────────────────────────────────────────────────────────────
    ("ballots:list", {}),
    ("ballots:create", {}),
    ("ballots:copy", {"pk": 1}),
    ("ballots:redirect", {}),
    ("ballots:update", {"pk": 1}),
    ("ballots:detail", {"slug": "test"}),
    ("ballots:votelist", {}),
    ("ballots:vote", {"slug": "test"}),
]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_name,kwargs",
    _URL_CASES,
    ids=[_id(n, k) for n, k in _URL_CASES],
)
def test_url_resolves(url_name, kwargs):
    """reverse() must return a non-empty path for every named URL.

    A NoReverseMatch exception here means a URL was removed, renamed, or its
    required kwargs changed — exactly the regressions this test is designed to
    catch during the Django 3.2 → 4.2 upgrade.
    """
    url = reverse(url_name, kwargs=kwargs or None)
    assert isinstance(url, str) and url.startswith("/"), f"Expected an absolute path string, got {url!r}"
