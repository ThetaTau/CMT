"""Matching the names typed in a Big and Little upload to members of the chapter.

Spelling in a hand-made spreadsheet varies, so a name only counts as found when it matches
exactly one member once case, accents, punctuation, word order and suffixes such as "Jr."
are ignored. Anything else becomes a short list of suggestions for an officer to confirm.
No database access here; the caller loads the roster once with ``.values(*ROSTER_FIELDS)``.
"""

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher, get_close_matches

ROSTER_FIELDS = (
    "id",
    "name",
    "first_name",
    "middle_name",
    "last_name",
    "preferred_name",
    "nickname",
    "maiden_name",
    "badge_number",
    "current_status",
)
SUFFIXES = frozenset({"jr", "sr", "ii", "iii", "iv"})
# Below this similarity a member is not worth suggesting.
SUGGESTION_CUTOFF = 0.6
MAX_SUGGESTIONS = 5
# A word this alike ("jon" and "john" are 0.86) makes a member worth scoring.
WORD_CUTOFF = 0.75
WORD_NEIGHBORS = 8
MAX_CANDIDATES = 100


def normalize_name(value):
    """Lower case, accents and punctuation removed, suffixes dropped, single spaces."""
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char)).lower()
    words = re.sub(r"[^a-z0-9]+", " ", text).split()
    return " ".join(word for word in words if word not in SUFFIXES)


def sorted_words(name):
    return " ".join(sorted(name.split()))


def name_forms(member):
    """Every normalized way the member's name might be written in a spreadsheet."""
    first, middle, last = member["first_name"] or "", member["middle_name"] or "", member["last_name"] or ""
    firsts = {first, member["preferred_name"] or "", member["nickname"] or ""}
    lasts = {last, member["maiden_name"] or ""}
    forms = {normalize_name(member["name"])}
    forms.update(normalize_name(f"{given} {family}") for given in firsts for family in lasts if given and family)
    if first and middle and last:
        forms.add(normalize_name(f"{first} {middle} {last}"))
        forms.add(normalize_name(f"{first} {middle[0]} {last}"))
    forms.discard("")
    return forms


@dataclass
class NameMatch:
    """``member_id`` when exactly one member matches, otherwise suggestions, best first."""

    member_id: int | None = None
    exact_count: int = 0
    suggestions: list = field(default_factory=list)


class Roster:
    """A chapter's members indexed by badge number, by name and by the words in their names.

    Scoring a misspelled name against every member is too slow for a large chapter, so only
    members who share a word, or a word spelled almost the same, with the name are scored.
    Every member can be found by an exact name; only ``can_suggest`` members are suggested.
    """

    def __init__(self, members, can_suggest):
        self.members = {}
        self.can_suggest = can_suggest
        self.badges = defaultdict(list)
        self.exact = defaultdict(set)
        self.forms = {}
        self.word_members = defaultdict(set)
        for member in members:
            member_id = member["id"]
            self.members[member_id] = member
            self.badges[member["badge_number"]].append(member_id)
            self.forms[member_id] = [(form, sorted_words(form)) for form in name_forms(member)]
            suggestable = can_suggest(member)
            for form, words in self.forms[member_id]:
                self.exact[words].add(member_id)
                if suggestable:
                    for word in form.split():
                        self.word_members[word].add(member_id)
        # Grouped by first letter: a typo rarely hits the first letter of every word.
        self.vocabulary = defaultdict(list)
        for word in self.word_members:
            self.vocabulary[word[0]].append(word)

    def with_badge(self, number):
        return self.badges.get(number, [])

    def _words(self, name):
        """The name's words, plus any known words inside a name typed as one run-together word."""
        words = set(name.split())
        if len(words) == 1:
            (token,) = words
            words.update(
                part
                for cut in range(2, len(token) - 1)
                for part in (token[:cut], token[cut:])
                if part in self.word_members
            )
        return words

    def _candidates(self, name):
        """Members whose name words are closest to the words of ``name``; exact words count most."""
        totals = defaultdict(float)
        for word in self._words(name):
            if len(word) < 2:
                continue
            closest = {}
            for close in get_close_matches(word, self.vocabulary.get(word[0], ()), WORD_NEIGHBORS, WORD_CUTOFF):
                closeness = SequenceMatcher(None, word, close).ratio()
                for member_id in self.word_members[close]:
                    closest[member_id] = max(closest.get(member_id, 0.0), closeness)
            for member_id, closeness in closest.items():
                totals[member_id] += closeness
        ranked = sorted(totals, key=lambda member_id: (-totals[member_id], member_id))
        return ranked[:MAX_CANDIDATES]

    def _score(self, name, member_id):
        """How alike ``name`` is to the closest form of the member's name, ignoring word order."""
        direct, ordered = SequenceMatcher(None, b=name), SequenceMatcher(None, b=sorted_words(name))
        best = 0.0
        for form, words in self.forms[member_id]:
            direct.set_seq1(form)
            ordered.set_seq1(words)
            best = max(best, direct.ratio(), ordered.ratio())
        return best

    def match(self, text):
        name = normalize_name(text)
        if not name:
            return NameMatch()
        exact = self.exact.get(sorted_words(name), set())
        if len(exact) == 1:
            return NameMatch(member_id=next(iter(exact)), exact_count=1)
        scores = dict.fromkeys(exact, 1.0)
        for member_id in self._candidates(name):
            if member_id not in scores:
                score = self._score(name, member_id)
                if score >= SUGGESTION_CUTOFF:
                    scores[member_id] = score
        ranked = sorted(
            (member_id for member_id in scores if self.can_suggest(self.members[member_id])),
            key=lambda member_id: (-scores[member_id], self.members[member_id]["name"], member_id),
        )
        suggestions = [{"pk": pk, "score": round(scores[pk], 2)} for pk in ranked[:MAX_SUGGESTIONS]]
        return NameMatch(exact_count=len(exact), suggestions=suggestions)
