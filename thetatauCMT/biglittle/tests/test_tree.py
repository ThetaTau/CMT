import datetime
import json

from thetatauCMT.biglittle import tree


def _person(pk, badge=None, name=None, group=tree.ACTIVE, **kwargs):
    return tree.Person(pk=pk, name=name or f"Member {pk}", badge_number=badge or pk, status_group=group, **kwargs)


def _forest(pairs, people=None):
    people = people or {}

    def get(pk):
        return people.get(pk) or _person(pk)

    return tree.build_forest([(get(big), get(little)) for big, little in pairs])


def _url(pk):
    return f"/biglittle/member/{pk}/"


# Family A: 1 -> (2, 3), 2 -> 4.  Family B: 5 -> 6.
FAMILIES = [(1, 2), (1, 3), (2, 4), (5, 6)]


def test_build_forest_finds_roots_and_orders_littles_by_roll():
    forest = _forest([(1, 3), (1, 2), (2, 4), (5, 6)])

    assert forest.roots == [1, 5]
    assert forest.children[1] == [2, 3]
    assert forest.big_of == {2: 1, 3: 1, 4: 2, 6: 5}


def test_a_loop_in_bad_data_is_cut_at_its_oldest_member():
    forest = _forest([(1, 2), (2, 3), (3, 1)])

    assert forest.roots == [1]
    assert forest.big_of == {2: 1, 3: 2}


def test_families_are_largest_first_and_subforest_keeps_one():
    forest = _forest(FAMILIES)

    assert [(family.root.pk, family.size) for family in tree.families(forest)] == [(1, 4), (5, 2)]
    assert tree.family_root(forest, 4) == 1
    small = tree.subforest(forest, 5)
    assert (set(small.people), small.roots, small.big_of) == ({5, 6}, [5], {6: 5})


def test_layout_puts_generations_in_rows_and_centers_each_big():
    forest = _forest(FAMILIES)

    positions = tree.layout_forest(forest)

    assert {pk: generation for pk, (_, generation) in positions.items()} == {1: 0, 2: 1, 3: 1, 4: 2, 5: 0, 6: 1}
    assert positions[1][0] == (positions[2][0] + positions[3][0]) / 2
    assert positions[2][0] < positions[3][0]
    assert min(x for x, _ in positions.values()) == 0


def test_layout_never_overlaps_and_separates_families():
    forest = _forest(FAMILIES + [(5, 7), (7, 8), (7, 9), (9, 10)])

    positions = tree.layout_forest(forest)

    rows = {}
    for x, generation in positions.values():
        rows.setdefault(generation, []).append(x)
    for xs in rows.values():
        assert len(xs) == len(set(xs))
    family_a = [positions[pk][0] for pk in (1, 2, 3, 4)]
    family_b = [positions[pk][0] for pk in (5, 6, 7, 8, 9, 10)]
    assert min(family_b) - max(family_a) >= 1 + tree.FAMILY_GAP


def test_layout_is_the_same_every_run():
    assert tree.layout_forest(_forest(FAMILIES)) == tree.layout_forest(_forest(list(reversed(FAMILIES))))


def test_a_long_chain_twins_and_a_single_pair():
    chain = _forest([(pk, pk + 1) for pk in range(1, 30)])
    assert max(generation for _, generation in tree.layout_forest(chain).values()) == 29

    twins = tree.layout_forest(_forest([(1, 2), (1, 3)]))
    assert twins[2][1] == twins[3][1] == 1

    assert tree.layout_forest(_forest([(1, 2)])) == {1: (0.0, 0.0), 2: (0.0, 1.0)}
    assert tree.layout_forest(tree.build_forest([])) == {}


def test_the_figure_follows_the_plotly_tree_example():
    people = {3: _person(3, group=tree.ALUMNI)}
    forest = _forest(FAMILIES, people)
    positions = tree.layout_forest(forest)

    figure = tree.build_figure(forest, positions, _url, highlight=4)

    edges, *nodes, highlight = figure.data
    assert edges.mode == "lines"
    assert len(edges.x) == 3 * len(forest.big_of)
    assert edges.x[2::3] == (None,) * len(forest.big_of)
    assert [trace.name for trace in nodes] == [tree.ACTIVE, tree.ALUMNI]
    assert nodes[1].customdata == ("/biglittle/member/3/",)
    assert highlight.name == "Selected member"
    assert (highlight.x[0], highlight.y[0]) == positions[4]
    assert figure.layout.meta == {"focusX": positions[4][0]}
    assert figure.layout.yaxis.fixedrange is True
    assert tree.build_figure(forest, positions, _url).layout.meta == {}
    json.loads(figure.to_json())


def test_names_are_escaped_in_labels_and_hover_text():
    sneaky = _person(2, name="<script>alert(1)</script>")
    forest = tree.build_forest([(_person(1), sneaky)])

    figure = tree.build_figure(forest, tree.layout_forest(forest), _url)

    labels = " ".join(figure.data[1].text) + " ".join(figure.data[1].hovertext)
    assert "<script>" not in labels
    assert "&lt;script&gt;" in labels


def test_hover_text_lists_roll_term_big_and_littles():
    little = _person(2, badge=314, name="Lee Little", initiated="Fall 2024", chapter_note="beta")
    forest = tree.build_forest([(_person(1, name="Bo Big"), little)])

    assert tree.hover_text(forest, little) == (
        "<b>Lee Little</b><br>beta<br>Roll #314<br>Initiated Fall 2024<br>Big: Bo Big<br>Littles: 0"
    )
    assert "Big: None recorded<br>Littles: 1" in tree.hover_text(forest, forest.people[1])


def test_long_names_are_shortened_for_the_label():
    assert tree.short_label(_person(1, name="A" * 30)) == "A" * 21 + "\u2026"


def test_outline_nests_littles_under_their_big():
    forest = _forest(FAMILIES)

    outline = tree.outline(forest)

    assert [node["person"].pk for node in outline] == [1, 5]
    assert [child["person"].pk for child in outline[0]["children"]] == [2, 3]
    assert outline[0]["children"][0]["children"][0]["person"].pk == 4


def test_person_from_row_reads_the_initiation_term_and_other_chapter():
    row = {f"big__{field}": None for field in tree.PERSON_FIELDS}
    row.update(
        {
            "big__id": 7,
            "big__name": "Ann",
            "big__badge_number": 12,
            "big__current_status": "alumni",
            "big__chapter": 2,
            "big__chapter__name": "beta",
            "big__initiation__date": datetime.date(2021, 3, 6),
        }
    )

    person = tree.person_from_row(row, "big", chapter_pk=1)
    assert (person.pk, person.status_group, person.initiated, person.chapter_note) == (
        7,
        tree.ALUMNI,
        "Spring 2021",
        "beta",
    )

    row.update({"big__chapter": 1, "big__initiation__date": None})
    person = tree.person_from_row(row, "big", chapter_pk=1)
    assert (person.initiated, person.chapter_note) == ("", "")
