from __future__ import annotations

from copy import deepcopy

from experiments.run_integrated_psyche_v1 import build_engine
from mechanistic_mind.integrated import IntegratedConfig, load_snapshot, save_snapshot
from mechanistic_mind.research import multiscale_prediction as ms
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import prospective_composition as pr


def _state(engine):
    return engine.state.agents["A001"].mechanism_states["PSYCHE-INTEGRATED-V1"]["integrated"]


def test_real_boundaries_and_wait_continuity():
    engine = build_engine(seed=17, config=IntegratedConfig())
    before = deepcopy(engine.state.world.variables)
    result = engine.step({"A001": __import__("mechanistic_mind.agent", fromlist=["Action"]).Action("WAIT")})
    after = engine.state.world.variables
    assert result.observations["A001"].data != after["world"]
    assert after["world"]["tick"] > before["world"]["tick"]
    assert after["bodies"]["A001"] != before["bodies"]["A001"]
    assert "objects" not in result.observations["A001"].data or result.observations["A001"].data.get("objects") != after["world"].get("objects")


def test_coupled_stores_are_bounded_and_provenance_is_runtime_supported():
    engine = build_engine(seed=9, config=IntegratedConfig())
    engine.run(180)
    state = _state(engine)
    assert len(state["compression"]["recent"]) <= pc.RECENT_CAPACITY
    assert len(state["compression"]["structures"]) <= pc.STRUCTURE_CAPACITY
    assert len(state["multiscale"]["local"]) <= ms.MAX_LOCAL
    assert len(state["prospection"]["transitions"]) <= pr.MAX_TRANSITIONS
    assert len(state["trace"]["events"]) <= state["trace"]["capacity"]
    assert state["metrics"]["action_counts"]
    assert all(e["relation"] in {"CAUSAL", "TEMPORAL"} for e in state["trace"]["edges"])
    assert any(e["kind"] == "ACTION_SELECTED" for e in state["trace"]["events"])


def test_ablation_removes_contribution_without_removing_physics():
    cfg = IntegratedConfig(predictive_compression=False, multiscale_prediction=False,
                           prospective_composition=False, instrumental_observation=False,
                           retrieval=False)
    engine = build_engine(seed=3, config=cfg)
    engine.run(12)
    state = _state(engine)
    assert state["compression"]["structures"] == {}
    assert state["multiscale"]["local"] == {}
    assert state["prospection"]["transitions"]  # lower-level transition acquisition remains
    assert engine.state.world.variables["world"]["tick"] == 12


def test_snapshot_resume_preserves_learned_state_and_rng(tmp_path):
    cfg = IntegratedConfig()
    engine = build_engine(seed=12, config=cfg)
    engine.run(30)
    path = save_snapshot(engine, tmp_path / "s.json")
    control = build_engine(seed=12, config=cfg)
    load_snapshot(control, path)
    assert _state(control)["compression"] == _state(engine)["compression"]
    a = engine.step()
    b = control.step()
    assert a.actions == b.actions
    assert engine.state.world == control.state.world


def test_learned_transitions_can_compose_and_change_selection_source():
    engine = build_engine(seed=5, config=IntegratedConfig())
    engine.run(240)
    state = _state(engine)
    sources = [e["payload"].get("source") for e in state["trace"]["events"] if e["kind"] == "ACTION_SELECTED"]
    assert state["prospection"]["transitions"]
    assert any(s in {"PROSPECTIVE_CONTINUATION", "RETAINED_PREDICTION"} for s in sources)
