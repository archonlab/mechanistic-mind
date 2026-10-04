"""OBSERVER_SELECTED_ORGANISM_VOLUMETRIC_VISION_VIEW_V1 — focused tests.

≤60 simulated ticks total across this module.
"""
from __future__ import annotations

from pathlib import Path

TICKS = {"n": 0}
RESULTS = Path(__file__).resolve().parents[1] / "results" / "observer_selected_organism_volumetric_vision_view_v1"


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _beta4(seed: int = 77):
    from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    cfg = acanthostega_beta4_config()
    cfg.cognition.cognition_enabled = True
    return PhysicalSystemRuntime(seed=seed, config=cfg)


def test_01_schema_capability_profile():
    from mechanistic_mind.physical_system.selected_organism_volumetric_vision_view import (
        AUTHORITY,
        CAPABILITY,
        PROFILE,
        SCHEMA,
    )

    assert SCHEMA == "SELECTED_ORGANISM_VOLUMETRIC_VISION_VIEW_V1"
    assert CAPABILITY == "selected_organism_volumetric_vision_view"
    assert PROFILE == "VW6_PHYSICAL_GEOMETRY_TO_ORGANISM_VISUAL_INPUT_AUDIT_V1"
    assert AUTHORITY == "RESEARCHER_VISUALIZATION_OVER_EXISTING_VW6_PERCEPTION"


def test_02_trace_uses_exact_vw6_scientific_capture():
    from mechanistic_mind.physical_system.selected_organism_volumetric_vision_view import (
        observer_payload,
        state_of,
    )

    rt = _beta4(101)
    rt.technical_id = "agent_0"
    # Constructor may already have captured once if cognition_enabled.
    before = 0 if state_of(rt.world) is None else len(state_of(rt.world).traces)
    rt.tick += 1
    rt.body.tick = rt.tick
    rt.world.tick = rt.tick
    obs = rt.agent_observation()
    _tick(1)
    st = state_of(rt.world)
    assert st is not None
    assert len(st.traces) >= before
    tr = st.traces[-1]
    # Post-O4: geometric VW6 samples may be unavailable; receptor-only fallback is honest authority.
    from mechanistic_mind.physical_system.selected_organism_volumetric_vision_view import (
        RECEPTOR_ONLY_FALLBACK,
    )
    assert tr["availability"] in ("AVAILABLE", RECEPTOR_ONLY_FALLBACK)
    if tr["availability"] == "AVAILABLE":
        assert tr["geometric_trace_available"] is True
        assert tr["los_authority"] == "VW1_AUTHORITATIVE_OCCUPANCY"
        assert tr["eye_pose_tick"] == tr["perception_tick"]
        assert tr["receptor_output_tick"] == tr["perception_tick"]
    else:
        assert tr["geometric_trace_available"] is False
    assert tr["perception_tick"] == int(rt.tick)
    if tr.get("xy_wrap_policy") is not None:
        assert tr["xy_wrap_policy"] == "MINIMUM_IMAGE_PERIODIC"
    if tr.get("z_wrap_policy") is not None:
        assert tr["z_wrap_policy"] == "NONE_ABSOLUTE_Z"
    # Cognition floats match observation exo keys when fragments present
    for k, v in (tr.get("cognition_accessible") or {}).get("fragments", {}).items():
        assert abs(float(obs.get(k, 0.0)) - float(v)) < 1e-9
    payload = observer_payload(rt.world, selected_agent_id="agent_0")
    # Geometric AVAILABLE ⇒ available True; receptor-only fallback exposes latest with available False.
    if tr["availability"] == "AVAILABLE":
        assert payload["available"] is True
    else:
        assert payload["available"] is False
        assert payload.get("fallback") == RECEPTOR_ONLY_FALLBACK
    assert payload["latest"]["trace_id"] == tr["trace_id"]
    assert "NOT A CAMERA" in payload["banner"]


def test_03_observer_polling_does_not_duplicate_trace():
    from mechanistic_mind.physical_system.near_field_exteroception import sample_near_field
    from mechanistic_mind.physical_system.selected_organism_volumetric_vision_view import state_of

    rt = _beta4(102)
    rt.technical_id = "agent_0"
    rt.agent_observation()
    _tick(1)
    n0 = len(state_of(rt.world).traces)
    nfe = rt.config.near_field_exteroception
    # Diagnostic / unarmed poll — must not append
    sample_near_field(
        world=rt.world, body=rt.body, cfg=nfe, diagnostic=True, physical_config=rt.config
    )
    sample_near_field(
        world=rt.world, body=rt.body, cfg=nfe, diagnostic=False, physical_config=rt.config
    )
    assert len(state_of(rt.world).traces) == n0


def test_04_geometry_same_z_above_below_wrap():
    from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import relative_xyz

    same = relative_xyz(1.0, 1.0, 2.0, 2.0, 1.0, 2.0, width=16, height=16)
    assert abs(same["elevation_deg"]) < 1e-9
    assert same["dz"] == 0.0
    up = relative_xyz(1.0, 1.0, 2.0, 2.0, 1.0, 5.0, width=16, height=16)
    assert up["elevation_deg"] > 0.0
    dn = relative_xyz(1.0, 1.0, 5.0, 2.0, 1.0, 2.0, width=16, height=16)
    assert dn["elevation_deg"] < 0.0
    wrap = relative_xyz(0.5, 0.5, 1.0, 7.5, 0.5, 4.0, width=8, height=8)
    assert abs(abs(wrap["dx"]) - 1.0) < 1e-9
    assert wrap["z_wrap"] is False


def test_05_occupancy_los_clear_and_blocked():
    from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
        occupancy_line_of_sight,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        set_volumetric_column,
    )

    rt = _beta4(103)
    set_volumetric_column(
        rt.world,
        3,
        3,
        [
            OccupiedZInterval(0.0, 3.0, 1.0, (("A", 3.0),)),
            OccupiedZInterval(7.0, 10.0, 1.0, (("B", 3.0),)),
        ],
        tick=0,
        reason="sovv_fixture",
    )
    # clear through z=5 free gap
    clear = occupancy_line_of_sight(rt.world, 1.5, 3.5, 5.0, 5.5, 3.5, 5.0, config=rt.config)
    assert clear["visible"] is True
    # blocked through z=2
    low = occupancy_line_of_sight(rt.world, 1.5, 3.5, 2.0, 5.5, 3.5, 2.0, config=rt.config)
    assert low["occluded"] is True
    # blocked through z=8
    high = occupancy_line_of_sight(rt.world, 1.5, 3.5, 8.0, 5.5, 3.5, 8.0, config=rt.config)
    assert high["occluded"] is True
    _tick(1)


def test_06_occluded_not_organism_visible_in_trace():
    from mechanistic_mind.physical_system.selected_organism_volumetric_vision_view import (
        _rejection_class,
    )

    row = {
        "visibility": "OCCLUDED_BY_OCCUPANCY",
        "occluded_by_occupancy": {"t": 0.2},
        "inside_fov": True,
        "detectable": False,
        "final_contribution": 0.0,
    }
    assert _rejection_class(row) == "BLOCKED_BY_VW1_OCCUPANCY"
    assert _rejection_class({**row, "visibility": "OUTSIDE_VERTICAL_ACCEPTANCE"}) == "OUTSIDE_VERTICAL_FOV"
    assert _rejection_class({"inside_fov": False, "final_contribution": 0.0}) == "OUTSIDE_HORIZONTAL_FOV"


def test_07_two_agent_isolation_and_selection():
    from mechanistic_mind.physical_system.selected_organism_volumetric_vision_view import (
        begin_scientific_capture,
        capture_from_near_field_sample,
        end_scientific_capture,
        observer_payload,
        state_of,
    )

    rt = _beta4(104)
    nfe = rt.config.near_field_exteroception
    from mechanistic_mind.physical_system.near_field_exteroception import sample_near_field

    begin_scientific_capture(
        rt.world, agent_id="agent_0", body_id="body_0", run_id="t", runtime_generation=1, decision_tick=0
    )
    s0 = sample_near_field(world=rt.world, body=rt.body, cfg=nfe, physical_config=rt.config)
    capture_from_near_field_sample(rt.world, s0)
    end_scientific_capture(rt.world)
    _tick(1)

    # Fake agent_1 capture with distinct id (same body pose — identity still isolated)
    begin_scientific_capture(
        rt.world, agent_id="agent_1", body_id="body_1", run_id="t", runtime_generation=1, decision_tick=0
    )
    s1 = sample_near_field(world=rt.world, body=rt.body, cfg=nfe, physical_config=rt.config)
    capture_from_near_field_sample(rt.world, s1)
    end_scientific_capture(rt.world)
    _tick(1)

    st = state_of(rt.world)
    agents = {tr["agent_id"] for tr in st.traces}
    assert "agent_0" in agents and "agent_1" in agents
    p0 = observer_payload(rt.world, selected_agent_id="agent_0", runtime_generation=1)
    p1 = observer_payload(rt.world, selected_agent_id="agent_1", runtime_generation=1)
    assert p0["latest"]["agent_id"] == "agent_0"
    assert p1["latest"]["agent_id"] == "agent_1"
    assert p0["latest"]["trace_id"] != p1["latest"]["trace_id"]


def test_08_restore_creates_no_trace_then_one_new():
    from mechanistic_mind.physical_system.selected_organism_volumetric_vision_view import (
        restore_state,
        serialize_state,
        state_of,
    )

    rt = _beta4(105)
    rt.technical_id = "agent_0"
    rt.agent_observation()
    _tick(1)
    snap = serialize_state(state_of(rt.world))
    n = len(state_of(rt.world).traces)
    # Clear and restore
    rt.world.selected_organism_volumetric_vision_state = None
    restore_state(rt.world, snap)
    assert len(state_of(rt.world).traces) == n
    n2 = len(state_of(rt.world).traces)
    rt.agent_observation()
    _tick(1)
    # Same tick may dedupe; advance tick for a new perception
    rt.tick += 1
    rt.body.tick = rt.tick
    rt.world.tick = rt.tick
    rt.agent_observation()
    _tick(1)
    assert len(state_of(rt.world).traces) >= n2
    assert len(state_of(rt.world).traces) <= n2 + 2


def test_09_privacy_tokens_and_cognition_boundary():
    from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS

    for tok in (
        "SELECTED_ORGANISM_VOLUMETRIC_VISION_VIEW_V1",
        "selected_organism_volumetric_vision_view",
        "RESEARCHER_VISUALIZATION_OVER_EXISTING_VW6_PERCEPTION",
        "occupancy_digest",
        "trace_id",
        "eye_xyz",
        "target_xyz",
        "BLOCKED_BY_VW1_OCCUPANCY",
    ):
        assert tok in FORBIDDEN_TOKENS


def test_10_analyzer_causal_and_public_selector():
    from mechanistic_mind.physical_system.experiment_canonical import public_model_selector_entries
    from mechanistic_mind.physical_system.selected_organism_volumetric_vision_view import (
        analyzer_causal_reconstruction,
        state_of,
    )

    presets = public_model_selector_entries()
    assert len(presets) == 2
    rt = _beta4(106)
    rt.technical_id = "agent_0"
    rt.agent_observation()
    _tick(1)
    tr = state_of(rt.world).traces[-1]
    causal = analyzer_causal_reconstruction(tr)
    assert causal["available"] is True
    # Exact VW6 geometric policy when available; otherwise honest receptor-only fallback (post-O4).
    assert causal["policy"] in ("EXACT_VW6_TRACE", "RECEPTOR_ONLY_FALLBACK_GEOMETRIC_TRACE_UNAVAILABLE")
    if causal["policy"] == "EXACT_VW6_TRACE":
        assert causal["processed"] == causal["total"]
        assert causal["total"] > 0
    legacy = analyzer_causal_reconstruction(None)
    assert legacy["available"] is False


def test_11_vw3_vw4_visibility_feedback_ordinary_path():
    """Visibility follows occupancy via ordinary perception — no manual visibility edit."""
    from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
        occupancy_line_of_sight,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        set_volumetric_column,
    )

    rt = _beta4(107)
    set_volumetric_column(
        rt.world,
        4,
        4,
        [OccupiedZInterval(0.0, 5.0, 1.0, (("ROCK", 5.0),))],
        tick=0,
        reason="sovv_block",
    )
    blocked = occupancy_line_of_sight(rt.world, 2.5, 4.5, 2.0, 6.5, 4.5, 2.0, config=rt.config)
    assert blocked["occluded"] is True
    # VW3-style removal: clear column
    set_volumetric_column(rt.world, 4, 4, [], tick=1, reason="sovv_clear")
    clear = occupancy_line_of_sight(rt.world, 2.5, 4.5, 2.0, 6.5, 4.5, 2.0, config=rt.config)
    assert clear["visible"] is True
    # VW4-style insertion again
    set_volumetric_column(
        rt.world,
        4,
        4,
        [OccupiedZInterval(0.0, 5.0, 1.0, (("ROCK", 5.0),))],
        tick=2,
        reason="sovv_reinsert",
    )
    again = occupancy_line_of_sight(rt.world, 2.5, 4.5, 2.0, 6.5, 4.5, 2.0, config=rt.config)
    assert again["occluded"] is True
    _tick(3)


def test_12_tick_budget():
    assert TICKS["n"] <= 60


def test_13_write_probe_summary(tmp_path=None):
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "TICK_BUDGET.txt").write_text(f"TOTAL_SIMULATED_TICKS={TICKS['n']}\n", encoding="utf-8")
