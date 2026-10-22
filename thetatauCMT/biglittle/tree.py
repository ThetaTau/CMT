"""Family tree layout and Plotly figure for one chapter's Bigs and Littles (BLWI-8).

Nothing here queries the database. The view reads pairings with ``.values()`` because
loading a User object costs a query for its address (``User.address_changed``).
"""

from dataclasses import dataclass

import igraph
import plotly.graph_objects as go
from django.utils.html import escape

from core.models import ACTIVE_STATUSES, ALUMNI_STATUSES, SEMESTER

ACTIVE, ALUMNI, OTHER = "Active", "Alumni", "Other"
GROUP_COLORS = {ACTIVE: "#0d6efd", ALUMNI: "#6c757d", OTHER: "#fd7e14"}
NO_BADGE_NUMBER = 999999999
LABEL_LENGTH = 22
# Extra horizontal space between separate families, in the layout's sibling spacing.
FAMILY_GAP = 1.0
GENERATION_HEIGHT = 120
MIN_HEIGHT = 420
PERSON_FIELDS = ("id", "name", "badge_number", "current_status", "chapter", "chapter__name", "initiation__date")


@dataclass(frozen=True)
class Person:
    pk: int
    name: str
    badge_number: int
    status_group: str
    initiated: str = ""
    chapter_note: str = ""

    @property
    def sort_key(self):
        # Roll order keeps each NME class together and puts older members on the left.
        return (self.badge_number, self.name.lower(), self.pk)


@dataclass
class Forest:
    people: dict
    big_of: dict
    children: dict
    roots: list


@dataclass(frozen=True)
class Family:
    root: Person
    size: int


def status_group(status):
    if status in ACTIVE_STATUSES:
        return ACTIVE
    if status in ALUMNI_STATUSES:
        return ALUMNI
    return OTHER


def pair_fields():
    """The ``.values()`` names for both people in a pairing."""
    return [f"{side}__{field}" for side in ("big", "little") for field in PERSON_FIELDS]


def person_from_row(row, side, chapter_pk):
    """The ``side`` ("big" or "little") of a pairing row read with :func:`pair_fields`."""
    values = {field: row[f"{side}__{field}"] for field in PERSON_FIELDS}
    initiated = ""
    if values["initiation__date"]:
        date = values["initiation__date"]
        initiated = f"{'Spring' if SEMESTER[date.month] == 'sp' else 'Fall'} {date.year}"
    return Person(
        pk=values["id"],
        name=values["name"],
        badge_number=values["badge_number"],
        status_group=status_group(values["current_status"]),
        initiated=initiated,
        chapter_note=values["chapter__name"] if values["chapter"] != chapter_pk else "",
    )


def _children_of(big_of, order):
    children = {}
    for pk in order:
        big = big_of.get(pk)
        if big is not None:
            children.setdefault(big, []).append(pk)
    return children


def _descendants(starts, children):
    found, stack = set(), list(starts)
    while stack:
        pk = stack.pop()
        if pk not in found:
            found.add(pk)
            stack.extend(children.get(pk, []))
    return found


def build_forest(pairs):
    """``pairs`` is an iterable of ``(big, little)`` :class:`Person` tuples."""
    people, big_of = {}, {}
    for big, little in pairs:
        people.setdefault(big.pk, big)
        people.setdefault(little.pk, little)
        big_of[little.pk] = big.pk
    order = sorted(people, key=lambda pk: people[pk].sort_key)
    roots = [pk for pk in order if pk not in big_of]
    reached = _descendants(roots, _children_of(big_of, order))
    for pk in order:
        if pk not in reached:
            # Only a loop in bad data leaves someone unreachable; cut it at its oldest member.
            del big_of[pk]
            roots.append(pk)
            reached |= _descendants([pk], _children_of(big_of, order))
    roots.sort(key=lambda pk: people[pk].sort_key)
    return Forest(people=people, big_of=big_of, children=_children_of(big_of, order), roots=roots)


def families(forest):
    """Each family's root and size, largest first."""
    found = [Family(forest.people[root], len(_descendants([root], forest.children))) for root in forest.roots]
    return sorted(found, key=lambda family: (-family.size, family.root.sort_key))


def family_root(forest, pk):
    seen = set()
    while pk in forest.big_of and pk not in seen:
        seen.add(pk)
        pk = forest.big_of[pk]
    return pk


def subforest(forest, root):
    members = _descendants([root], forest.children)
    return Forest(
        people={pk: person for pk, person in forest.people.items() if pk in members},
        big_of={little: big for little, big in forest.big_of.items() if little in members},
        children={big: littles for big, littles in forest.children.items() if big in members},
        roots=[root],
    )


def layout_forest(forest):
    """``{pk: (x, generation)}`` from igraph's Reingold-Tilford layout; generation 0 is the top."""
    order = sorted(forest.people, key=lambda pk: forest.people[pk].sort_key)
    if not order:
        return {}
    index = {pk: number for number, pk in enumerate(order)}
    graph = igraph.Graph(
        n=len(order),
        edges=[(index[big], index[little]) for little, big in forest.big_of.items()],
        directed=True,
    )
    # igraph orders siblings by vertex number, which is roll order here.
    coords = graph.layout_reingold_tilford(mode="out", root=[index[root] for root in forest.roots]).coords
    top = min(y for _, y in coords)
    positions = {pk: (coords[index[pk]][0], coords[index[pk]][1] - top) for pk in order}
    return _spread_families(forest, positions)


def _spread_families(forest, positions):
    """Start at x=0 and leave a clear gap between families, which igraph packs like siblings."""
    spans = []
    for root in forest.roots:
        members = _descendants([root], forest.children)
        xs = [positions[pk][0] for pk in members]
        spans.append((min(xs), max(xs), members))
    spread, right_edge = {}, None
    for left, right, members in sorted(spans, key=lambda span: span[0]):
        shift = -left if right_edge is None else right_edge + 1 + FAMILY_GAP - left
        for pk in members:
            x, y = positions[pk]
            spread[pk] = (x + shift, y)
        right_edge = right + shift
    return spread


def short_label(person):
    if len(person.name) <= LABEL_LENGTH:
        return person.name
    return person.name[: LABEL_LENGTH - 1].rstrip() + "\u2026"


def hover_text(forest, person):
    lines = [f"<b>{escape(person.name)}</b>"]
    if person.chapter_note:
        lines.append(escape(person.chapter_note))
    if person.badge_number and person.badge_number < NO_BADGE_NUMBER:
        lines.append(f"Roll #{person.badge_number}")
    if person.initiated:
        lines.append(f"Initiated {person.initiated}")
    big = forest.big_of.get(person.pk)
    lines.append(f"Big: {escape(forest.people[big].name) if big is not None else 'None recorded'}")
    lines.append(f"Littles: {len(forest.children.get(person.pk, []))}")
    return "<br>".join(lines)


def build_figure(forest, positions, profile_url, highlight=None):
    """The tree drawn the way https://plotly.com/python/tree-plots/ does it.

    ``profile_url`` maps a member's pk to the link opened when their marker is clicked.
    """
    figure = go.Figure()
    edge_x, edge_y = [], []
    for little, big in sorted(forest.big_of.items()):
        edge_x += [positions[big][0], positions[little][0], None]
        edge_y += [positions[big][1], positions[little][1], None]
    figure.add_trace(
        go.Scatter(
            x=edge_x,
            y=edge_y,
            mode="lines",
            name="Big to Little",
            line={"color": "rgba(128, 128, 128, 0.7)", "width": 1.5},
            hoverinfo="none",
            showlegend=False,
        )
    )
    ordered = sorted(forest.people.values(), key=lambda person: person.sort_key)
    for group in (ACTIVE, ALUMNI, OTHER):
        people = [person for person in ordered if person.status_group == group]
        if not people:
            continue
        figure.add_trace(
            go.Scatter(
                x=[positions[person.pk][0] for person in people],
                y=[positions[person.pk][1] for person in people],
                mode="markers+text",
                name=group,
                marker={
                    "size": 16,
                    "color": GROUP_COLORS[group],
                    "line": {"width": 1, "color": "rgba(40, 40, 40, 0.8)"},
                },
                text=[escape(short_label(person)) for person in people],
                textposition="bottom center",
                hovertext=[hover_text(forest, person) for person in people],
                hoverinfo="text",
                customdata=[profile_url(person.pk) for person in people],
            )
        )
    if highlight in forest.people:
        x, y = positions[highlight]
        figure.add_trace(
            go.Scatter(
                x=[x],
                y=[y],
                mode="markers",
                name="Selected member",
                marker={"size": 30, "symbol": "circle-open", "color": "#ffc107", "line": {"width": 3}},
                hoverinfo="skip",
            )
        )
    xs = [x for x, _ in positions.values()] or [0]
    generations = int(max((y for _, y in positions.values()), default=0)) + 1
    meta = {}
    if highlight in forest.people:
        # The page opens zoomed in around this member.
        meta["focusX"] = positions[highlight][0]
    figure.update_layout(
        showlegend=True,
        legend={"orientation": "h", "x": 0, "y": 1.0, "yanchor": "bottom"},
        # Fixed ranges leave room for the labels under the bottom row and at both ends.
        xaxis={"visible": False, "range": [min(xs) - 1, max(xs) + 1]},
        # Zooming and dragging only move sideways; every generation always fits.
        yaxis={"visible": False, "range": [generations - 0.4, -0.6], "fixedrange": True},
        hovermode="closest",
        dragmode="pan",
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
        height=max(MIN_HEIGHT, GENERATION_HEIGHT * generations + 120),
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)",
        meta=meta,
    )
    return figure


def outline(forest):
    """Nested ``{"person", "children"}`` dicts, oldest family first, for the text version."""

    def node(pk):
        return {
            "person": forest.people[pk],
            "children": [node(child) for child in forest.children.get(pk, [])],
        }

    return [node(root) for root in forest.roots]
