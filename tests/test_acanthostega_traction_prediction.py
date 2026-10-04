"""Generic consequence-model adaptation to traction. No material learner."""
from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.model.acanthostega import (
    acanthostega_traction_adaptation_config,
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
    PRESET_ACANTHOSTEGA_TRACTION_EXPERIENCE,
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
from mechanistic_mind.physical_system.surface_affinity_traction import traction_multiplier
from mechanistic_mind.physical_system.surface_traction_prediction import (
    ADAPTATION_OBSERVED,
    HISTORY_LIMIT,
    MECHANISM_ID,
    PREDICTION_NOT_AVAILABLE,
    surface_traction_prediction_is_active,
)
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.scientific_v3.traction_prediction_summary import (
    format_traction_prediction_section,
    summarize_traction_prediction,
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
    PRESET_ACANTHOSTEGA_TRACTION_EXPERIENCE,
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
    "TRACTION_PREDICTION_ADAPTATION",
)


def _runtime(seed: int = 17) -> PhysicalSystemRuntime:
    return PhysicalSystemRuntime(seed=seed, config=acanthostega_traction_adaptation_config())


def _park(rt: PhysicalSystemRuntime) -> None:
    rt.body.x = 10.2
    rt.body.y = 10.2
    rt.body.vx = 0.0
    rt.body.vy = 0.0
    rt.body.theta = 0.0
    rt.body.omega = 0.0
    rt.body.mechanical_work_reservoir = 20.0


def _put(rt: PhysicalSystemRuntime, component: str | None) -> None:
    rt.world.surface_material_deposits.clear()
    if component is None:
        return
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


def _capture(rt: PhysicalSystemRuntime) -> dict:
    world = rt.world
    return {
        "T": world.T.copy(),
        "M": world.M.copy(),
        "vx": world.vx.copy(),
        "vy": world.vy.copy(),
        "u": world.u.copy(),
        "u_prev": world.u_prev.copy(),
        "B": rt.body.B.copy(),
        "B_core": rt.body.B_core.copy(),
        "bodyT": float(rt.body.T),
        "c": rt.internal.c.copy(),
        "mech": float(rt.body.mech),
    }


def _restore_phys(rt: PhysicalSystemRuntime, captured: dict) -> None:
    world = rt.world
    world.T[:] = captured["T"]
    world.M[:] = captured["M"]
    world.vx[:] = captured["vx"]
    world.vy[:] = captured["vy"]
    world.u[:] = captured["u"]
    world.u_prev[:] = captured["u_prev"]
    rt.body.B[:] = captured["B"]
    rt.body.B_core[:] = captured["B_core"]
    rt.body.T = captured["bodyT"]
    rt.internal.c[:] = captured["c"]
    rt.body.mech = captured["mech"]
    _park(rt)


def _episode(rt: PhysicalSystemRuntime, component: str | None, phase: str, *, rewind: dict | None) -> dict:
    if rewind is not None:
        _restore_phys(rt, rewind)
    _put(rt, component)
    rt.traction_adaptation_phase = phase
    rt._forced_motor_once = {"locomotion": "MOVE:E"}
    rt.step(1)
    rt._forced_motor_once = {"locomotion": "WAIT"}
    rt.step(1)
    receipt = rt.last_traction_prediction_receipt
    assert receipt is not None
    return receipt


def test_fingerprint_previous_presets_and_generic_flags():
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN_BETA31_FP_SEED17
    assert MECHANISM_ID not in beta31_mechanism_map()
    for name in PREVIOUS:
        mechanisms = preset_canonical(name, seed=17)["mechanisms"]
        assert MECHANISM_ID not in mechanisms
    fresh = preset_canonical("ACANTHOSTEGA_PHASE_A_TRACTION_ADAPTATION", seed=17)
    assert fresh["mechanisms"][MECHANISM_ID] is True
    assert fresh["mechanisms"]["sensorimotor_consequence_model"] is True
    assert fresh["mechanisms"]["surface_traction_experience_bridge"] is True
    experience = acanthostega_traction_experience_config()
    assert experience.cognition.sensorimotor_consequence_model is False
    assert experience.cognition.prediction_error_revision is False
    assert surface_traction_prediction_is_active(experience) is False
    cfg = acanthostega_traction_adaptation_config()
    assert cfg.cognition.sensorimotor_consequence_model is True
    assert cfg.cognition.prediction_error_revision is False
    assert cfg.cognition.temporal_prediction_error is False
    assert cfg.cognition.predictive_equivalence is False
    assert cfg.cognition.predictive_compression is True
    assert cfg.cognition.bounded_memory is True
    assert cfg.cognition.retrieval is True
    assert traction_multiplier(0.75) == 1.2
    assert traction_multiplier(0.25) == 0.8
    tik = tiktaalik_config()
    set_mechanism(tik, MECHANISM_ID, True)
    assert surface_traction_prediction_is_active(tik) is False
    assert tik.cognition.sensorimotor_consequence_model is False
    catalog = {row["id"] for row in PhysicalSystemRuntime(seed=17, config=tik).mechanisms()["mechanisms"]}
    assert MECHANISM_ID not in catalog


def test_missing_snapshot_field_is_off_and_physics_is_unchanged():
    cfg = acanthostega_traction_experience_config()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    snap = rt.snapshot()
    snap["config"].pop("surface_traction_prediction", None)
    restored = PhysicalSystemRuntime.restore(snap)
    assert surface_traction_prediction_is_active(restored.config) is False
    neutral = _runtime()
    high = _runtime()
    _park(neutral)
    _park(high)
    _put(neutral, "component_0")
    _put(high, "component_a")
    for rt in (neutral, high):
        rt.traction_adaptation_phase = "PHYSICS_CHECK"
        rt._forced_motor_once = {"locomotion": "MOVE:E"}
        rt.step(1)
        rt._forced_motor_once = {"locomotion": "WAIT"}
        rt.step(1)
    assert abs(float(neutral.last_traction_experience_receipt["realized_dv"][0]) - 0.105) < 1e-9
    assert abs(float(high.last_traction_experience_receipt["realized_dv"][0]) - 0.126) < 1e-9


def _run_protocol(seed: int) -> tuple[PhysicalSystemRuntime, list[dict]]:
    rt = _runtime(seed)
    _park(rt)
    _put(rt, "component_0")
    captured = _capture(rt)
    rows: list[dict] = []
    for _ in range(6):
        rows.append(dict(_episode(rt, "component_0", "NEUTRAL_BASELINE", rewind=captured)))
    for _ in range(8):
        rows.append(dict(_episode(rt, "component_a", "NON_NEUTRAL_STABLE", rewind=captured)))
    for _ in range(8):
        rows.append(dict(_episode(rt, "component_0", "RETURN_NEUTRAL", rewind=captured)))
    for _ in range(4):
        rows.append(dict(_episode(rt, "component_b", "UNSEEN_MAGNITUDE", rewind=captured)))
    return rt, rows


def test_stable_regime_adapts_on_three_seeds_without_material_features():
    summaries = []
    for seed in (17, 18, 19):
        rt, rows = _run_protocol(seed)
        assert len(rows) == 26
        assert len(rt.traction_prediction_history) == HISTORY_LIMIT
        assert rows[0]["prediction_availability"] == PREDICTION_NOT_AVAILABLE
        neutral = [row for row in rows if row["exposure_phase"] == "NEUTRAL_BASELINE"]
        predicted = [row for row in neutral if row["prediction_availability"] == "OBSERVED"]
        assert predicted
        assert all(abs(float(row["aggregate_error"])) < 1e-4 for row in predicted)
        vx = [float(row["predicted_agent_visible_delta"]["body.vx"]) for row in predicted]
        assert max(vx) - min(vx) < 1e-4
        for row in rows:
            assert row["action_provenance"] == "INTERVENTION"
            assert row["setup_separated_from_agent_action"] is True
            assert row["action_consequence_latency_ticks"] == 1
            assert row["consequence_observation_tick"] == row["action_tick"] + 1
            assert row["prediction_issued_tick"] == row["action_tick"]
            assert set(row["predicted_agent_visible_delta"]) <= {"body.vx", "body.vy"}
            blob = repr(row["predicted_agent_visible_delta"]) + repr(row["context_signature"])
            for token in FORBIDDEN:
                assert token not in blob
            assert "surface_affinity" not in row["predicted_agent_visible_delta"]
        hits = audit_cognition_payload(rt.last_agent_observation)
        assert hits == []
        summary = summarize_traction_prediction(rows)
        summaries.append(summary)
        assert summary["stable_regime_adaptation"] == ADAPTATION_OBSERVED
        assert summary["reversal"] == "OBSERVED"
        assert summary["unseen_magnitude_first_error_exceeds_prior"] == "OBSERVED"
        assert summary["pre_action_context_discrimination"] == "NOT_AVAILABLE"
        assert summary["instrumental_use_established"] == "NOT_ESTABLISHED"
        assert summary["section"] == "SURFACE TRACTION PREDICTION ADAPTATION"
        text = format_traction_prediction_section(summary)
        assert "SURFACE TRACTION PREDICTION ADAPTATION" in text
        assert "action → prediction → physical outcome → error → revision" in text
        assert "STABLE_REGIME_ADAPTATION = ADAPTATION_OBSERVED" in text
        assert "PRE_ACTION_CONTEXT_DISCRIMINATION = NOT_AVAILABLE" in text
        assert "INSTRUMENTAL_USE = NOT_ESTABLISHED" in text
        assert "component_a" not in text
        assert "SLIPPERY" not in text
    assert summaries[0]["stable_regime_adaptation"] == summaries[1]["stable_regime_adaptation"] == summaries[2]["stable_regime_adaptation"]


def test_interleaved_control_keeps_switch_error_and_identical_context():
    rt = _runtime(17)
    _park(rt)
    _put(rt, "component_0")
    captured = _capture(rt)
    sequence = ["component_0", "component_a"] * 6
    signatures = []
    for component in sequence:
        receipt = _episode(rt, component, "INTERLEAVED", rewind=captured)
        signatures.append(receipt["context_signature"])
    assert len(set(signatures[1:])) == 1
    summary = summarize_traction_prediction(rt.traction_prediction_history)
    assert summary["interleaved_regime"] == "SWITCH_ERROR_PERSISTS"
    assert summary["pre_action_context_discrimination"] == "NOT_AVAILABLE"
    assert summary["stable_regime_adaptation"] == PREDICTION_NOT_AVAILABLE


def test_uncontrolled_velocity_is_excluded_and_history_is_bounded():
    rt = _runtime()
    _park(rt)
    _put(rt, "component_a")
    captured = _capture(rt)
    _episode(rt, "component_a", "NON_NEUTRAL_STABLE", rewind=captured)
    _episode(rt, "component_a", "NON_NEUTRAL_STABLE", rewind=captured)
    rt.traction_adaptation_phase = "NON_NEUTRAL_STABLE"
    rt._forced_motor_once = {"locomotion": "MOVE:E"}
    rt.step(1)
    rt._forced_motor_once = {"locomotion": "WAIT"}
    rt.step(1)
    drifted = rt.last_traction_prediction_receipt
    assert drifted["exclusion_reason"] == "VELOCITY_NOT_CONTROLLED"
    assert drifted["entered_adaptation_statistics"] is False
    rt2 = _runtime()
    _park(rt2)
    _put(rt2, "component_0")
    captured2 = _capture(rt2)
    for _ in range(HISTORY_LIMIT + 2):
        _episode(rt2, "component_0", "NEUTRAL_BASELINE", rewind=captured2)
    assert len(rt2.traction_prediction_history) == HISTORY_LIMIT


def test_snapshot_does_not_duplicate_revision():
    rt = _runtime()
    _park(rt)
    _put(rt, "component_a")
    rt.traction_adaptation_phase = "NON_NEUTRAL_STABLE"
    rt._forced_motor_once = {"locomotion": "MOVE:E"}
    rt.step(1)
    assert rt._traction_prediction_pending is not None
    assert rt.last_traction_prediction_receipt is None
    snap = rt.snapshot()
    restored = PhysicalSystemRuntime.restore(deepcopy(snap))
    restored._forced_motor_once = {"locomotion": "WAIT"}
    restored.step(1)
    assert len(restored.traction_prediction_history) == 1
    support = restored.last_traction_prediction_receipt["model_state_reference"]["support_after"]
    again = PhysicalSystemRuntime.restore(restored.snapshot())
    again._forced_motor_once = {"locomotion": "WAIT"}
    again.step(1)
    assert len(again.traction_prediction_history) == 1
    assert again._traction_prediction_pending is None
    record_id = again.last_traction_prediction_receipt["model_state_reference"]["record_id"]
    if record_id is not None:
        live = 0
        for row in again.cognition["sensorimotor_consequence"]["records"].values():
            if row.get("record_id") == record_id:
                live = int(row.get("support") or 0)
        assert live == int(support or 0)


def test_two_agent_and_wait_and_shadow_and_diagnostic():
    cfg = acanthostega_traction_adaptation_config()
    world = TwoAgentRuntime(seed=17, config=cfg, starts=((10, 10), (22, 22)), contact_enabled=False)
    host, other = world.slots
    _park(host)
    other.body.mechanical_work_reservoir = 20.0
    _put(host, "component_a")
    host.traction_adaptation_phase = "NON_NEUTRAL_STABLE"
    host._forced_motor_once = {"locomotion": "MOVE:E"}
    other._forced_motor_once = {"locomotion": "WAIT"}
    world.step(1)
    host._forced_motor_once = {"locomotion": "WAIT"}
    other._forced_motor_once = {"locomotion": "WAIT"}
    world.step(1)
    assert host.last_traction_prediction_receipt["agent_id"] == "agent_0"
    assert host.last_traction_prediction_receipt["action_provenance"] == "INTERVENTION"
    assert other.traction_prediction_history == []
    assert other.last_traction_prediction_receipt is None

    rt = _runtime()
    _park(rt)
    rt._forced_motor_once = {"locomotion": "WAIT"}
    rt.step(1)
    assert rt.last_traction_prediction_receipt is None

    shadow = _runtime(19)
    _park(shadow)
    _put(shadow, "component_a")
    for _ in range(12):
        shadow.step(1)
    assert audit_cognition_payload(shadow.last_agent_observation) == []
    assert len(shadow.traction_prediction_history) <= HISTORY_LIMIT
    actions = shadow.cognition["metrics"]["action_counts"]
    assert actions
    assert not (len(actions) == 1 and "MOVE:E" in actions and sum(actions.values()) == actions["MOVE:E"])

    frame = world_frame(host)
    assert frame["traction_prediction_researcher_only"] is True
    assert frame["traction_prediction_not_agent_accessible"] is True
    assert "surface_affinity" not in frame["traction_prediction_receipts"][-1]
    assert "traction_multiplier" not in frame["traction_prediction_receipts"][-1]
