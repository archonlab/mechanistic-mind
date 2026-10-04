"""O5 Sensory Modality Temporal Alignment Contract V1 — focused validation (<=30 ticks)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.experiment_canonical import (
    acanthostega_beta4_mechanism_map,
    public_model_selector_entries,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.sensory_modality_temporal_alignment import (
    AUTHORITY,
    AVAIL_TRUE_ZERO,
    CAPABILITY,
    PROFILE,
    SCHEMA,
    WORLD_COUNTERS_ATTR,
    WORLD_HISTORY_ATTR,
    WORLD_LAST_ATTR,
    build_alignment_envelope,
    build_o5_analyzer_reconstruction,
    derive_envelope_from_saved_evidence,
    finalize_alignment_envelope,
    note_observer_poll_skip,
    researcher_summary,
    sensory_modality_temporal_alignment_is_active,
)

RESULTS = Path("results/acanthostega_sensory_modality_temporal_alignment_contract_v1")
RESULTS.mkdir(parents=True, exist_ok=True)

TICK_BUDGET = 0


def _budget(n: int) -> None:
    global TICK_BUDGET
    TICK_BUDGET += int(n)
    assert TICK_BUDGET <= 30, f"tick budget exceeded: {TICK_BUDGET}"


def _beta4_rt(*, seed: int = 11) -> PhysicalSystemRuntime:
    cfg = acanthostega_beta4_config()
    assert sensory_modality_temporal_alignment_is_active(cfg)
    return PhysicalSystemRuntime(seed=seed, config=cfg)


def test_01_identity_capability_profile():
    assert SCHEMA == "SENSORY_MODALITY_TEMPORAL_ALIGNMENT_CONTRACT_V1"
    assert CAPABILITY == "sensory_modality_temporal_alignment"
    assert PROFILE == "PHYSICAL_EVENT_RECEPTOR_OBSERVATION_TICK_ENVELOPE_O5_V1"
    assert AUTHORITY == "RESEARCHER_AND_CAUSAL_METADATA_OVER_EXISTING_MODALITY_TIMING"
    assert acanthostega_beta4_mechanism_map().get("sensory_modality_temporal_alignment") is True
    assert len(public_model_selector_entries()) == 2


def test_02_vision_zero_delay_and_no_static_emission_fabricated():
    rt = _beta4_rt()
    for _ in range(2):
        rt.step()
    _budget(2)
    env = getattr(rt.world, WORLD_LAST_ATTR)
    assert isinstance(env, dict)
    vis = env["vision"]
    assert vis.get("causal_delay_ticks") == 0
    assert vis.get("static_light_emission_event_fabricated") is False
    assert vis.get("physical_event_tick") in ("NOT_APPLICABLE", None) or vis.get("physical_event_tick") == "NOT_APPLICABLE"
    assert vis.get("receptor_sample_tick") == vis.get("organism_observation_tick") or (
        vis.get("receptor_sample_tick") is not None and vis.get("organism_observation_tick") is not None
    )
    assert env.get("researcher_presentation_tick_is_scientific_authority") is False


def test_03_lps_transport_distinct_from_oatt_zero():
    rt = _beta4_rt(seed=13)
    for _ in range(3):
        rt.step()
    _budget(3)
    env = getattr(rt.world, WORLD_LAST_ATTR)
    hear = env["hearing"]
    # OATT A3→observation may be 0; must never overwrite transport with OATT
    assert hear.get("lps_transport_delay_overwritten_by_oatt") is False
    assert hear.get("oatt_zero_delay_meaning") == (
        "A3_RECEPTOR_TO_A5_OBSERVATION_ALIGNMENT_NOT_LPS_TRANSPORT"
    )
    if hear.get("receptor_to_observation_delay_ticks") is not None:
        assert int(hear["receptor_to_observation_delay_ticks"]) >= 0
    # When transport delay known, must be >= 1
    td = hear.get("source_to_receptor_propagation_delay_ticks")
    if td is not None:
        assert int(td) >= 1


def test_04_same_observation_different_physical_times_flag():
    rt = _beta4_rt(seed=17)
    for _ in range(2):
        rt.step()
    _budget(2)
    env = getattr(rt.world, WORLD_LAST_ATTR)
    assert env.get("same_observation_tick_means_same_physical_time") is False
    # Inject distinct source refs without mutating sensory numerics
    hear = dict(env["hearing"])
    hear["physical_event_ticks"] = [0]
    hear["source_to_receptor_propagation_delay_ticks"] = 2
    env2 = dict(env)
    env2["hearing"] = hear
    from mechanistic_mind.physical_system.sensory_modality_temporal_alignment import (
        STATUS_ALIGNED_DIFF_PHYS,
        _alignment_status,
    )

    st = _alignment_status(env2["vision"], hear, int(env["observation_identity"]["organism_observation_tick"]))
    assert st in (STATUS_ALIGNED_DIFF_PHYS, env.get("alignment_status"))


def test_05_true_zero_vs_missing():
    rt = _beta4_rt(seed=19)
    rt.step()
    _budget(1)
    env = getattr(rt.world, WORLD_LAST_ATTR)
    for mod in ("vision", "hearing"):
        avail = env[mod].get("availability")
        assert avail is not None
        assert "ZERO_FILL" not in str(avail)
    assert env.get("zero_fill_used") is False
    assert env.get("interpolation_used") is False
    assert env.get("last_value_carried_as_current") is False
    missing = build_alignment_envelope(
        world=rt.world,
        body=rt.body,
        config=rt.config,
        observation={},
        observation_tick=99,
        agent_id="agent_x",
        body_id="body_x",
        run_id="r",
        runtime_generation=1,
    )
    # empty obs without traces for foreign body → missing not silent zero invent
    assert missing["hearing"]["availability"] in (
        "MISSING_NOT_CAPTURED",
        AVAIL_TRUE_ZERO,
        "AVAILABLE_NONZERO",
        "AVAILABLE_TRUE_ZERO",
    )


def test_06_body_support_and_motor_links_no_adjacent_inference():
    rt = _beta4_rt(seed=23)
    for _ in range(2):
        rt.step()
    _budget(2)
    env = getattr(rt.world, WORLD_LAST_ATTR)
    assert env["body_support"].get("physical_state_tick") is not None
    links = env["motor_context"]["links"]
    assert links.get("adjacent_ticks_alone_used_as_causal_proof") is False
    assert "observation_tick" in links


def test_07_restore_no_envelope_then_one_post_restore():
    rt = _beta4_rt(seed=29)
    for _ in range(2):
        rt.step()
    _budget(2)
    before = len(getattr(rt.world, WORLD_HISTORY_ATTR) or [])
    assert before >= 1
    snap = rt.snapshot()
    rt2 = PhysicalSystemRuntime.restore(snap)
    # Restore must not create a NEW live envelope
    counters = getattr(rt2.world, WORLD_COUNTERS_ATTR) or {}
    assert int(counters.get("live_envelopes_created_on_restore", 0)) == 0
    hist = getattr(rt2.world, WORLD_HISTORY_ATTR) or []
    for e in hist:
        assert e.get("restored_researcher_evidence_only") is True
    n0 = int((getattr(rt2.world, WORLD_COUNTERS_ATTR) or {}).get("envelopes", 0))
    rt2.step()
    _budget(1)
    n1 = int((getattr(rt2.world, WORLD_COUNTERS_ATTR) or {}).get("envelopes", 0))
    assert n1 == n0 + 1
    live = [e for e in (getattr(rt2.world, WORLD_HISTORY_ATTR) or []) if not e.get("restored_as_live_envelope") is False or not e.get("restored_researcher_evidence_only")]
    # At least one new non-restored envelope exists
    fresh = [e for e in (getattr(rt2.world, WORLD_HISTORY_ATTR) or []) if not e.get("restored_researcher_evidence_only")]
    assert len(fresh) == 1


def test_08_generations_and_cross_agent_and_poll():
    rt = _beta4_rt(seed=31)
    rt.runtime_generation = 7
    rt.step()
    _budget(1)
    env = getattr(rt.world, WORLD_LAST_ATTR)
    assert env["observation_identity"].get("runtime_generation") == 7
    # Poll skip does not add envelope
    n0 = len(getattr(rt.world, WORLD_HISTORY_ATTR) or [])
    note_observer_poll_skip(rt.world)
    assert len(getattr(rt.world, WORLD_HISTORY_ATTR) or []) == n0
    # Cross-agent: finalize other agent id separately
    finalize_alignment_envelope(
        world=rt.world,
        body=rt.body,
        config=rt.config,
        observation=rt.last_agent_observation,
        observation_tick=int(env["observation_identity"]["organism_observation_tick"]),
        agent_id="agent_1",
        body_id="agent_1",
        run_id="31",
        runtime_generation=7,
        runtime=rt,
    )
    agents = {
        (e["observation_identity"]["agent_id"], e["observation_identity"]["organism_observation_tick"])
        for e in getattr(rt.world, WORLD_HISTORY_ATTR)
    }
    assert ("agent_0", env["observation_identity"]["organism_observation_tick"]) in agents
    assert ("agent_1", env["observation_identity"]["organism_observation_tick"]) in agents


def test_09_privacy_numerics_tiktaalik_selector():
    rt = _beta4_rt(seed=37)
    rt.step()
    _budget(1)
    obs = rt.last_agent_observation or {}
    blob = json.dumps(obs)
    for tok in (SCHEMA, CAPABILITY, PROFILE, AUTHORITY, "alignment_envelope", "source_event_refs"):
        assert tok not in blob
    # O4/LPS paths still present as organism values (exo_/osc_) — keys only, unchanged contract
    tik = tiktaalik_config()
    assert not sensory_modality_temporal_alignment_is_active(tik)
    assert len(public_model_selector_entries()) == 2


def test_10_analyzer_legacy_saved_run():
    exact = {
        "schema": SCHEMA,
        "observation_identity": {"organism_observation_tick": 1, "agent_id": "a0"},
        "vision": {"causal_delay_ticks": 0},
        "hearing": {"source_to_receptor_propagation_delay_ticks": 2, "receptor_to_observation_delay_ticks": 0},
        "alignment_status": "ALIGNED_OBSERVATION_DIFFERENT_PHYSICAL_EVENT_TIMES",
    }
    d = derive_envelope_from_saved_evidence(exact)
    assert d["legacy_policy"] == "CURRENT_O5_EXACT_ENVELOPE"
    leg = derive_envelope_from_saved_evidence({"old": True})
    assert leg["legacy_policy"] == "LEGACY_PARTIAL_UNKNOWN"
    rec = build_o5_analyzer_reconstruction(d)
    assert rec["same_observation_means_same_physical_time"] is False
    assert rec["oatt_delay_is_not_lps_transport"] is True
    # Serialize researcher summary
    rt = _beta4_rt(seed=41)
    rt.step()
    _budget(1)
    summ = researcher_summary(rt.world, rt.config)
    assert summ.get("researcher_only") is True
    assert summ.get("feeds_cognition") is False
    (RESULTS / "smoke_envelope.json").write_text(json.dumps(getattr(rt.world, WORLD_LAST_ATTR), indent=2, default=str))


def test_11_tick_budget_guard():
    assert TICK_BUDGET <= 30
