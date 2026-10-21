from thetatauCMT.biglittle import names
from thetatauCMT.biglittle.names import NameMatch, Roster, name_forms, normalize_name


def _row(pk, name, first="", last="", status="active", badge=None, **extra):
    row = {
        "id": pk,
        "name": name,
        "first_name": first,
        "middle_name": "",
        "last_name": last,
        "preferred_name": None,
        "nickname": "",
        "maiden_name": "",
        "badge_number": badge,
        "current_status": status,
    }
    row.update(extra)
    return row


def _roster(*rows):
    return Roster(rows, can_suggest=lambda member: member["current_status"] != "pnm")


def test_normalize_ignores_case_accents_punctuation_and_suffixes():
    assert normalize_name("  José  O'Brien-Smith, Jr. ") == "jose o brien smith"
    assert normalize_name("JOHN SMITH III") == "john smith"
    assert normalize_name(None) == ""


def test_forms_cover_preferred_names_nicknames_maiden_names_and_middle_names():
    member = _row(
        1,
        "Bob Jones",
        first="Robert",
        last="Jones",
        middle_name="James",
        preferred_name="Bob",
        nickname="Bobby",
        maiden_name="Smith",
    )

    assert name_forms(member) >= {
        "bob jones",
        "robert jones",
        "bobby jones",
        "robert smith",
        "bob smith",
        "robert james jones",
        "robert j jones",
    }


def test_blank_name_parts_add_no_forms():
    assert name_forms(_row(1, "", first="", last="")) == set()


def test_a_name_that_matches_one_member_finds_them_in_any_word_order():
    roster = _roster(
        _row(1, "Robert Jones", "Robert", "Jones", middle_name="James"), _row(2, "Mary Lee", "Mary", "Lee")
    )

    assert roster.match("ROBERT JONES").member_id == 1
    assert roster.match("Jones, Robert").member_id == 1
    assert roster.match("Robert J. Jones").member_id == 1
    assert roster.match("mary lee").member_id == 2


def test_a_name_shared_by_two_members_suggests_both():
    roster = _roster(_row(1, "John Smith", "John", "Smith"), _row(2, "John Smith", "John", "Smith"))

    match = roster.match("John Smith")

    assert match.member_id is None
    assert match.exact_count == 2
    assert match.suggestions == [{"pk": 1, "score": 1.0}, {"pk": 2, "score": 1.0}]


def test_a_misspelled_name_suggests_the_closest_members_best_first():
    roster = _roster(
        _row(1, "John Smith", "John", "Smith"),
        _row(2, "Joan Smythe", "Joan", "Smythe"),
        _row(3, "Mary Lee", "Mary", "Lee"),
    )

    match = roster.match("Jon Smith")

    assert match.member_id is None
    assert match.exact_count == 0
    assert [suggestion["pk"] for suggestion in match.suggestions] == [1, 2]
    assert match.suggestions[0]["score"] == 0.95


def test_an_unknown_name_has_no_suggestions():
    match = _roster(_row(1, "John Smith", "John", "Smith")).match("Zed Quux")

    assert match == NameMatch()


def test_a_name_typed_as_one_word_is_still_suggested():
    roster = _roster(_row(1, "Mary Lee", "Mary", "Lee"), _row(2, "John Smith", "John", "Smith"))

    assert roster.match("MaryLee").suggestions == [{"pk": 1, "score": 0.93}]


def test_only_the_closest_members_are_scored_and_exact_words_count_most(monkeypatch):
    monkeypatch.setattr(names, "MAX_CANDIDATES", 1)
    roster = _roster(_row(1, "James Bowen", "James", "Bowen"), _row(2, "Jamie Bowen", "Jamie", "Bowen"))

    # "eowen" shares no first letter with "bowen", so only "jamie" picks who is scored.
    assert [suggestion["pk"] for suggestion in roster.match("Jamie Eowen").suggestions] == [2]


def test_members_who_cannot_be_picked_are_found_but_never_suggested():
    roster = _roster(_row(1, "Pat Pnm", "Pat", "Pnm", status="pnm"))

    assert roster.match("Pat Pnm").member_id == 1
    assert roster.match("Pat Pmn").suggestions == []


def test_an_empty_name_matches_nobody():
    assert _roster(_row(1, "", "", "")).match("  ") == NameMatch()


def test_badge_numbers_are_indexed():
    roster = _roster(
        _row(1, "A B", "A", "B", badge=7), _row(2, "C D", "C", "D", badge=7), _row(3, "E F", "E", "F", badge=8)
    )

    assert roster.with_badge(7) == [1, 2]
    assert roster.with_badge(8) == [3]
    assert roster.with_badge(9) == []
