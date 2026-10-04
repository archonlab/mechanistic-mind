"""Ordinary body experience of surface traction. No new sensor and no learner."""
from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.model.acanthostega import (
    acanthostega_surface_traction_config,
    acanthostega_traction_experience_config,
)
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA,
    PRESET_ACANTHOSTEGA_BILATERAL_GRASP,
    PRESET_ACANTHOSTEGA_BRING_TOGETHER,
    PRESET_ACANTHOSTEGA_COMPOSITION_MERGE,
    PRESET_ACANTHOSTEGA_GENTLE,
    PRESET_ACANTHOSTEGA_MATERIAL_PROPERTIES,
    PRESET_ACANTHOSTEGA_MATERIAL_VISION,
    PRESET_ACANTHOSTEGA_MATERIALS,
    PRESET_ACANTHOSTEGA_SINGLE_GRASP,
    PRESET_ACANTHOSTEGA_SURFACE_DEPOSITION,
    PRESET_ACANTHOSTEGA_SURFACE_TRACTION,
    PRESET_BETA31,
    beta31_mechanism_map,
    canonical_fingerprint,
    preset_canonical,
)
from mechanistic_mind.physical_system.explicit_surface_deposition import (
    SurfaceMaterialDeposit,
    deposit_id_for_cell,
)
from mechanistic_mind.physical_system.mechanism_registry import set_mechanism
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.resource_objects import MaterialComponent
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.surface_affinity_traction import (
    SURFACE_AFFINITY_TRACTION,
    traction_multiplier,
)
from mechanistic_mind.physical_system.surface_traction_experience import (
    SURFACE_TRACTION_EXPERIENCE_BRIDGE,
    surface_traction_experience_is_active,
)
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.scientific_v3.traction_experience_summary import (
    LEARNING_ESTABLISHED,
    summarize_traction_experience,
)
from mechanistic_mind.ui.psy_observer_web.serialize import world_frame

FROZEN_BETA31_FP_SEED17 = "1621ef2c154864d1"
PREVIOUS = (
    PRESET_BETA31,
    PRESET_ACANTHOSTEGA,
    PRESET_ACANTHOSTEGA_GENTLE,
    PRESET_ACANTHOSTEGA_MATERIALS,
    PRESET_ACANTHOSTEGA_MATERIAL_VISION,
    PRESET_ACANTHOSTEGA_SINGLE_GRASP,
    PRESET_ACANTHOSTEGA_BILATERAL_GRASP,
    PRESET_ACANTHOSTEGA_BRING_TOGETHER,
    PRESET_ACANTHOSTEGA_COMPOSITION_MERGE,
    PRESET_ACANTHOSTEGA_MATERIAL_PROPERTIES,
    PRESET_ACANTHOSTEGA_SURFACE_DEPOSITION,
    PRESET_ACANTHOSTEGA_SURFACE_TRACTION,
)
FORBIDDEN = (
    "deposit_id",
    "component_id",
    "component_a",
    "component_b",
    "surface_affinity",
    "traction_multiplier",
    "SURFACE_AFFINITY_TRACTION_V1",
    "LOW_TRACTION",
    "HIGH_TRACTION",
    "SLIPPERY",
    "STICKY",
    "TRACTION_EXPERIENCE",
)


def _runtime(*, cognition: bool = True) -> PhysicalSystemRuntime:
    cfg = acanthostega_traction_experience_config()
    cfg.cognition.cognition_enabled = cognition
    return PhysicalSystemRuntime(seed=17, config=cfg)


def _park(rt: PhysicalSystemRuntime, x: float = 10.2, y: float = 10.2) -> None:
    rt.body.x = float(x)
    rt.body.y = float(y)
    rt.body.vx = 0.0
    rt.body.vy = 0.0
    rt.body.mechanical_work_reservoir = 20.0


def _put(rt: PhysicalSystemRuntime, component: str) -> None:
    deposit = SurfaceMaterialDeposit(
        deposit_id=deposit_id_for_cell(10, 10),
        cell_x=10,
        cell_y=10,
        mass=1.0,
        quantity=1.0,
        composition=(MaterialComponent(component, 1.0),),
        provenance={"lineage_refs": [{"event_id": "setup-deposit", "tick": -1}]},
        created_tick=-1,
        last_updated_tick=-1,
    )
    rt.world.surface_material_deposits[deposit.deposit_id] = deposit


def _move(rt: PhysicalSystemRuntime, command: str = "MOVE:E") -> None:
    rt._forced_motor_once = {"locomotion": command}
    rt.step(1)


def _close(rt: PhysicalSystemRuntime) -> None:
    rt._forced_motor_once = {"locomotion": "WAIT"}
    rt.step(1)


def test_fingerprint_and_previous_presets_exclude_the_bridge():
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN_BETA31_FP_SEED17
    assert SURFACE_TRACTION_EXPERIENCE_BRIDGE not in beta31_mechanism_map()
    assert SURFACE_AFFINITY_TRACTION not in beta31_mechanism_map()
    for name in PREVIOUS:
        mechanisms = preset_canonical(name, seed=17)["mechanisms"]
        assert SURFACE_TRACTION_EXPERIENCE_BRIDGE not in mechanisms
    fresh = preset_canonical("ACANTHOSTEGA_PHASE_A_TRACTION_EXPERIENCE", seed=17)
    assert fresh["mechanisms"][SURFACE_AFFINITY_TRACTION] is True
    assert fresh["mechanisms"][SURFACE_TRACTION_EXPERIENCE_BRIDGE] is True
    assert fresh["mechanisms"]["explicit_surface_deposition"] is True
    traction = preset_canonical(PRESET_ACANTHOSTEGA_SURFACE_TRACTION, seed=17)
    assert traction["mechanisms"][SURFACE_AFFINITY_TRACTION] is True
    assert SURFACE_TRACTION_EXPERIENCE_BRIDGE not in traction["mechanisms"]
    tik = tiktaalik_config()
    set_mechanism(tik, SURFACE_TRACTION_EXPERIENCE_BRIDGE, True)
    assert surface_traction_experience_is_active(tik) is False
    catalog = {row["id"] for row in PhysicalSystemRuntime(seed=17, config=tik).mechanisms()["mechanisms"]}
    assert SURFACE_TRACTION_EXPERIENCE_BRIDGE not in catalog


def test_formula_unchanged_and_missing_config_is_off():
    assert traction_multiplier(0.75) == 1.2
    assert traction_multiplier(0.25) == 0.8
    cfg = acanthostega_surface_traction_config()
    assert surface_traction_experience_is_active(cfg) is False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    snap = rt.snapshot()
    snap["config"].pop("surface_traction_experience", None)
    restored = PhysicalSystemRuntime.restore(snap)
    assert surface_traction_experience_is_active(restored.config) is False


def test_matched_controls_reach_cognition_without_material_identity():
    seen = {}
    for label, component in (("empty", None), ("neutral", "component_0"), ("high", "component_a")):
        rt = _runtime(cognition=True)
        _park(rt)
        if component:
            _put(rt, component)
        _move(rt)
        _close(rt)
        obs = rt.cognition["compression"]["raw_log"][1]["realized"]
        receipt = rt.last_traction_experience_receipt
        assert receipt["action_tick"] == 0
        assert receipt["consequence_observation_tick"] == 1
        assert receipt["action_consequence_latency_ticks"] == 1
        assert receipt["causal_order"] == "ACTION_THEN_NEXT_OBSERVATION"
        assert receipt["selected_motor_command"] == "MOVE:E"
        assert receipt["action_provenance"] == "INTERVENTION"
        assert receipt["setup_separated_from_agent_action"] is True
        assert receipt["cognition_delivered"] is True
        assert "body.vx" in receipt["agent_visible_fields"]
        assert receipt["memory_status"] == "OBSERVED"
        assert receipt["memory_reference"]["action"] == "MOVE:E"
        assert receipt["memory_reference"]["raw_id"] == 1
        assert receipt["prediction_error_status"] == "NOT_AVAILABLE"
        assert receipt["researcher_only"] is True
        assert receipt["agent_accessible"] is False
        hits = audit_cognition_payload(rt.last_agent_observation)
        assert hits == []
        blob = repr(rt.cognition["compression"]["raw_log"][1]["realized"])
        for token in FORBIDDEN:
            assert token not in blob
        seen[label] = (
            float(obs["body.vx"]),
            float(receipt["realized_dv"][0]),
            float(receipt["agent_visible_fields"]["body.vx"]),
        )
    assert seen["empty"][0] == seen["neutral"][0]
    assert seen["high"][0] != seen["neutral"][0]
    assert seen["high"][1] > seen["neutral"][1]
    assert seen["high"][2] > seen["neutral"][2]
    assert seen["empty"][2] == seen["neutral"][2]


def test_cognition_off_does_not_invent_memory():
    rt = _runtime(cognition=False)
    _park(rt)
    _put(rt, "component_a")
    _move(rt)
    _close(rt)
    receipt = rt.last_traction_experience_receipt
    assert receipt["cognition_delivered"] is False
    assert receipt["agent_visible_fields"] == {}
    assert receipt["memory_status"] == "NOT_AVAILABLE"
    assert receipt["prediction_error_status"] == "NOT_AVAILABLE"
    assert receipt["action_provenance"] == "INTERVENTION"
    assert abs(float(receipt["realized_dv"][0]) - 0.126) < 1e-9


def test_repeated_exposure_is_deterministic_and_bounded():
    rt = _runtime(cognition=True)
    _park(rt)
    _put(rt, "component_a")
    velocities = []
    for _ in range(3):
        _park(rt)
        _move(rt)
        _close(rt)
        receipt = rt.last_traction_experience_receipt
        velocities.append((
            float(receipt["realized_dv"][0]),
            float(receipt["agent_visible_fields"]["body.vx"]),
        ))
    assert velocities[0][0] == velocities[1][0] == velocities[2][0]
    assert max(row[1] for row in velocities) - min(row[1] for row in velocities) < 1e-4
    assert len(rt.traction_experience_history) == 3
    summary = summarize_traction_experience(rt.traction_experience_history)
    assert summary["section"] == "SURFACE TRACTION EXPERIENCE"
    assert summary["exposure_episodes"] == 3
    assert summary["same_nominal_action"] is True
    assert summary["distribution"]["non_neutral"] == 3
    assert summary["intervention_action_count"] == 3
    assert summary["endogenous_action_count"] == 0
    assert set(summary["action_consequence_latency_ticks"]) == {1}
    assert summary["prediction_error_decrease_across_repetition"] == "NOT_AVAILABLE"
    assert summary["LEARNING_ESTABLISHED"] == LEARNING_ESTABLISHED
    assert summary["mixed_with_resource_change"] is False
    assert "body.vx" in summary["agent_visible_fields"]
    assert "deposit_id" in summary["researcher_only_causal_fields"]
    assert "traction_multiplier" in summary["researcher_only_causal_fields"]


def test_wait_does_not_open_an_experience():
    rt = _runtime(cognition=True)
    _park(rt)
    _put(rt, "component_a")
    _close(rt)
    assert rt.last_traction_experience_receipt is None
    assert rt.traction_experience_history == []


def test_snapshot_does_not_duplicate_the_episode():
    rt = _runtime(cognition=True)
    _park(rt)
    _put(rt, "component_a")
    _move(rt)
    assert rt._traction_experience_pending is not None
    assert rt.last_traction_experience_receipt is None
    snap = rt.snapshot()
    restored = PhysicalSystemRuntime.restore(deepcopy(snap))
    restored._forced_motor_once = {"locomotion": "WAIT"}
    restored.step(1)
    assert len(restored.traction_experience_history) == 1
    action_tick = restored.last_traction_experience_receipt["action_tick"]
    again = PhysicalSystemRuntime.restore(restored.snapshot())
    again._forced_motor_once = {"locomotion": "WAIT"}
    again.step(1)
    assert len(again.traction_experience_history) == 1
    assert again.last_traction_experience_receipt["action_tick"] == action_tick
    assert again._traction_experience_pending is None


def test_two_agent_attribution_stays_separate():
    cfg = acanthostega_traction_experience_config()
    world = TwoAgentRuntime(seed=17, config=cfg, starts=((10, 10), (22, 22)), contact_enabled=False)
    host, other = world.slots
    host.body.x, host.body.y = 10.2, 10.2
    host.body.vx = host.body.vy = 0.0
    host.body.mechanical_work_reservoir = 20.0
    other.body.mechanical_work_reservoir = 20.0
    other.config.cognition.cognition_enabled = False
    _put(host, "component_a")
    host._forced_motor_once = {"locomotion": "MOVE:E"}
    other._forced_motor_once = {"locomotion": "WAIT"}
    world.step(1)
    host._forced_motor_once = {"locomotion": "WAIT"}
    other._forced_motor_once = {"locomotion": "WAIT"}
    world.step(1)
    assert host.last_traction_experience_receipt["agent_id"] == "agent_0"
    assert host.last_traction_experience_receipt["action_provenance"] == "INTERVENTION"
    assert other.traction_experience_history == []
    assert other.last_traction_experience_receipt is None


def test_observer_diagnostic_is_researcher_only():
    rt = _runtime(cognition=True)
    _park(rt)
    _put(rt, "component_b")
    _move(rt)
    _close(rt)
    frame = world_frame(rt)
    rows = frame["traction_experience_receipts"]
    assert frame["traction_experience_researcher_only"] is True
    assert frame["traction_experience_not_agent_accessible"] is True
    assert rows[-1]["prediction_error_status"] == "NOT_AVAILABLE"
    assert rows[-1]["action_provenance"] == "INTERVENTION"
    assert "surface_affinity" not in rows[-1]
    assert "traction_multiplier" not in rows[-1]
    summary = summarize_traction_experience([
        {"type": "RESOURCE_CHANGE", "evidence": {"event": "RESOURCE_CHANGE"}},
        rt.last_traction_experience_receipt,
    ])
    assert summary["exposure_episodes"] == 1
    assert summary["distribution"]["non_neutral"] == 1
    assert summary["INSTRUMENTAL_USE"] == "NOT_ESTABLISHED"
