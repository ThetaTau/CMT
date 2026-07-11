"""Tests for the vCard renderer."""

from thetatauCMT.contact_sync.officers import OfficerContact
from thetatauCMT.contact_sync.vcard import build_vcard, build_vcard_collection


def _sample_contact(**overrides) -> OfficerContact:
    kwargs = {
        "chapter_abbr": "X",
        "chapter_name": "Chi",
        "role": "regent",
        "role_abbr": "R",
        "first_name": "Franklin",
        "last_name": "Ventura",
        "preferred_name": "",
        "middle_name": "",
        "suffix": "",
        "email": "frank@example.com",
        "email_school": "",
        "phone": "+15551234567",
        "user_pk": 42,
    }
    kwargs.update(overrides)
    return OfficerContact(**kwargs)


def test_build_vcard_emits_expected_fields():
    contact = _sample_contact()
    text = build_vcard(contact)
    assert text.startswith("BEGIN:VCARD\r\n")
    assert text.endswith("END:VCARD\r\n")
    assert "VERSION:3.0" in text
    # Display name follows the natoff spec: "X-R Franklin Ventura".
    assert "FN:X-R Franklin Ventura" in text
    assert "N:Ventura;Franklin;;;" in text
    assert "ORG:Theta Tau;Chi Chapter" in text
    assert "TITLE:Regent" in text
    assert "EMAIL;TYPE=INTERNET,PREF:frank@example.com" in text
    assert "TEL;TYPE=CELL,VOICE:+15551234567" in text
    assert "CATEGORIES:Theta Tau,Chi Chapter,Regent" in text
    assert text.count("BEGIN:VCARD") == 1


def test_build_vcard_prefers_preferred_name_for_given_name():
    contact = _sample_contact(first_name="Kevin", preferred_name="Henry", middle_name="L")
    text = build_vcard(contact)
    assert "FN:X-R Henry Ventura" in text
    # When preferred is set, that becomes given and the legal first slides into additional.
    assert "N:Ventura;Henry;Kevin;;" in text


def test_build_vcard_escapes_special_characters():
    contact = _sample_contact(first_name="J;Doe", last_name="O'Neil, Jr\\", email="a;b@example.com")
    text = build_vcard(contact)
    # Backslash before ; , and \  is required.
    assert "J\\;Doe" in text
    assert "O'Neil\\, Jr\\\\" in text
    assert "a\\;b@example.com" in text


def test_build_vcard_includes_extra_roles_in_title():
    contact = _sample_contact(extra_roles=["scribe"])
    text = build_vcard(contact)
    assert "TITLE:Regent / Scribe" in text


def test_build_vcard_omits_phone_when_missing():
    contact = _sample_contact(phone="")
    text = build_vcard(contact)
    assert "TEL" not in text


def test_build_vcard_deduplicates_and_orders_emails():
    contact = _sample_contact(email="a@example.com", email_school="A@Example.com")
    text = build_vcard(contact)
    # Case-insensitive dedup keeps only the first.
    assert text.count("EMAIL;TYPE=INTERNET") == 1


def test_build_vcard_collection_concatenates():
    a = _sample_contact()
    b = _sample_contact(chapter_abbr="Y", role="scribe", role_abbr="S", first_name="Alice", last_name="Smith")
    text = build_vcard_collection([a, b])
    assert text.count("BEGIN:VCARD") == 2
    assert "FN:X-R Franklin Ventura" in text
    assert "FN:Y-S Alice Smith" in text


def test_build_vcard_falls_back_when_no_chapter_abbr():
    contact = _sample_contact(chapter_abbr="", role_abbr="R", first_name="F", last_name="V")
    text = build_vcard(contact)
    # Display name should be "-R F V" (dash retained because role_abbr is present) —
    # but we strip a leading dash in OfficerContact.display_name so the prefix
    # collapses to just "R" (or "TT" if both are empty).
    assert "FN:R F V" in text or "FN:TT F V" in text
