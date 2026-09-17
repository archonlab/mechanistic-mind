from mechanistic_mind.psyche.state import PsycheState
from mechanistic_mind.research.composed_future_value import (
    acquire_edge, compose_supported_chain, prediction_errors, value_ladder,
)


GOALS = PsycheState.initial_organism_v03().goals


def st(energy):
    return {"energy_signal": energy, "hydration_signal": .72,
            "fatigue_signal": .20, "discomfort_signal": .05}


def test_depth_three_crossing_is_composed_without_sequence_value():
    s0, s1, s2, s3 = st(.45), st(.41), st(.38), st(.63)
    store = {}
    for before, action, after in zip((s0, s1, s2), ("A", "B", "C"), (s1, s2, s3)):
        acquire_edge(store, before, action, after, observations=4)
    result = value_ladder(
        compose_supported_chain(store=store, start=s0, actions=["A", "B", "C"]),
        goals=GOALS,
    )
    values = [d["branches"][0]["ordinary_valuation"]["ordinary_value"] for d in result["depths"]]
    assert values[0] <= 0 and values[1] <= 0 and values[2] > 0
    assert result["value_horizon"] == 3
    assert result["no_cumulative_double_counting"] is True


def test_unknown_link_stops_composition_and_has_no_value():
    s0, s1, s2 = st(.45), st(.41), st(.38)
    store = {}
    acquire_edge(store, s0, "A", s1, observations=4)
    acquire_edge(store, s1, "B", s2, observations=4)
    result = value_ladder(
        compose_supported_chain(store=store, start=s0, actions=["A", "B", "C"]),
        goals=GOALS,
    )
    assert result["depths"][-1]["status"] == "COMPOSED_FUTURE_UNKNOWN"
    assert result["depths"][-1]["branches"] == []


def test_supported_terminal_branches_are_not_averaged():
    s0, s1, good, bad = st(.45), st(.41), st(.63), st(.36)
    store = {}
    acquire_edge(store, s0, "A", s1, observations=4)
    acquire_edge(store, s1, "C", good, observations=4)
    acquire_edge(store, s1, "C", bad, observations=4)
    result = value_ladder(compose_supported_chain(store=store, start=s0, actions=["A", "C"]), goals=GOALS)
    terminal = result["depths"][-1]["branches"]
    assert len(terminal) == 2
    assert sorted(b["ordinary_valuation"]["ordinary_value"] > 0 for b in terminal) == [False, True]


def test_prediction_error_is_componentwise_and_depthwise():
    rows = prediction_errors([st(.4), st(.5)], [st(.39), st(.48)])
    assert [r["depth"] for r in rows] == [1, 2]
    assert rows[1]["l1_error"] > rows[0]["l1_error"]
