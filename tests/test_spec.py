import dataclasses
import random

import pytest

import config
from core.errors import UserInputError
from core.spec import (
    RunSpec,
    build_spec,
    parse_edges,
    parse_int_list,
    parse_line,
    random_edges,
)


def build(algo, data=None, size=None, target=None, start=None, seed=1):
    return build_spec(algo, data, size, target, start, random.Random(seed))


# ---- parsing ---------------------------------------------------------------
def test_parse_int_list_accepts_common_separators():
    assert parse_int_list("5, 2 9;1") == [5, 2, 9, 1]


@pytest.mark.parametrize("bad", ["", "  ", "a,b", "1,,x", "-3", "1.5", "1e3", "١٢"])
def test_parse_int_list_rejects_junk(bad):
    with pytest.raises(UserInputError):
        parse_int_list(bad)


def test_parse_int_list_rejects_oversized_text():
    with pytest.raises(UserInputError):
        parse_int_list("1," * config.MAX_DATA_CHARS)


def test_parse_edges_normalises_and_dedupes():
    assert parse_edges("2-1, 1-2, 3-1") == [(1, 2), (1, 3)]


@pytest.mark.parametrize("bad", ["", "1-1", "1", "1-2-3", "a-b", "1:2"])
def test_parse_edges_rejects_junk(bad):
    with pytest.raises(UserInputError):
        parse_edges(bad)


# ---- building --------------------------------------------------------------
def test_random_is_deterministic_for_a_seed():
    assert build("bubble", seed=5)[0] == build("bubble", "random", seed=5)[0]


def test_random_sort_input_is_valid_and_not_presorted():
    for seed in range(50):
        spec, _ = build("bubble", None, 8, seed=seed)
        assert len(spec.values) == 8
        assert list(spec.values) != sorted(spec.values)
        assert all(config.MIN_VALUE <= v <= config.MAX_VALUE for v in spec.values)


def test_list_input_is_kept_as_given():
    spec, notes = build("merge", "5,2,9,1")
    assert spec.values == (5, 2, 9, 1) and notes == []


def test_size_with_explicit_list_is_rejected():
    with pytest.raises(UserInputError):
        build("bubble", "5,2,9", size=3)


def test_target_and_start_only_where_they_belong():
    with pytest.raises(UserInputError):
        build("bubble", "5,2", target=5)
    with pytest.raises(UserInputError):
        build("linear", "5,2", start=1)


@pytest.mark.parametrize("data", ["1", "5," + ",".join(["9"] * 21), "5,100", "0,5"])
def test_limits_enforced(data):
    with pytest.raises(UserInputError):
        build("bubble", data)


def test_binary_search_sorts_input_and_says_so():
    spec, notes = build("binary", "9,3,7", target=7)
    assert spec.values == (3, 7, 9) and any("sorted" in n.lower() for n in notes)


def test_search_picks_target_when_missing():
    spec, notes = build("linear", "9,3,7")
    assert spec.target is not None and notes


def test_tree_duplicates_are_skipped_with_note():
    spec, notes = build("inorder", "5,3,5,8")
    assert spec.values == (5, 3, 8) and notes


def test_tree_needs_two_distinct_values():
    with pytest.raises(UserInputError):
        build("inorder", "4,4,4")


def test_graph_defaults_start_to_smallest_node():
    spec, _ = build("bfs", "3-4,4-5")
    assert spec.start == 3


def test_graph_start_must_exist():
    with pytest.raises(UserInputError):
        build("bfs", "1-2", start=7)


def test_random_graph_is_connected_and_within_limits():
    for seed in range(100):
        rng = random.Random(seed)
        nodes = rng.randint(config.MIN_GRAPH_NODES, config.MAX_GRAPH_NODES)
        edges = random_edges(rng, nodes)
        assert len(edges) <= config.MAX_GRAPH_EDGES
        reached, frontier = {1}, [1]
        while frontier:
            cur = frontier.pop()
            for a, b in edges:
                for x, y in ((a, b), (b, a)):
                    if x == cur and y not in reached:
                        reached.add(y)
                        frontier.append(y)
        assert reached == set(range(1, nodes + 1))


def test_graph_node_limit():
    with pytest.raises(UserInputError):
        build("bfs", "1-11")


# ---- the run line stored in Discord ------------------------------------------
@pytest.mark.parametrize(
    "algo", ["bubble", "quick", "radix", "linear", "binary", "bfs", "dfs", "preorder", "postorder"]
)
def test_run_line_round_trip(algo):
    for seed in range(10):
        spec, _ = build(algo, seed=seed)
        assert parse_line(f"**Title**\n`{spec.to_line()}`\nnote") == spec


@pytest.mark.parametrize(
    "text",
    [
        "",
        "no run info here",
        "`v=1 | algo=bubble | data=5,2 | target=- | start=-`".replace("v=1", "v=2"),
        "`v=1 | algo=nope | data=5,2 | target=- | start=-`",
        "`v=1 | algo=bubble | data=5,x | target=- | start=-`",
        "`v=1 | algo=bubble | data=5,200 | target=- | start=-`",
        "`v=1 | algo=bubble | data=5,2 | target=7 | start=-`",
        "`v=1 | algo=../etc | data=5,2 | target=- | start=-`",
        "`v=1 | algo=bubble | data=5,2`",
        "`v=1 | bubble`",
    ],
)
def test_parse_line_rejects_bad_text(text):
    with pytest.raises(UserInputError):
        parse_line(text)


def test_validate_catches_unsorted_binary_spec():
    with pytest.raises(UserInputError):
        parse_line("`v=1 | algo=binary | data=9,3 | target=3 | start=-`")


def test_runspec_is_hashable_and_immutable():
    spec = RunSpec(algo="bubble", values=(1, 2))
    assert hash(spec) == hash(RunSpec(algo="bubble", values=(1, 2)))
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.algo = "x"  # type: ignore[misc]
