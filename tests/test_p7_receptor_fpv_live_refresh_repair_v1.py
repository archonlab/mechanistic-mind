"""P7_RECEPTOR_FPV_LIVE_REFRESH_REPAIR_V1 — FPV latest_exact_trace must advance under ObserverSession."""
from __future__ import annotations

import time

from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
from mechanistic_mind.physical_system import organism_receptor_grounded_3d_fpv as fpv
from mechanistic_mind.physical_system.near_field_exteroception import (
    _SNF_CACHE,
    sample_near_field,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.selected_organism_volumetric_vision_view import (
    begin_scientific_capture,
    end_scientific_capture,
)
from mechanistic_mind.ui.psy_observer_web import observer_canonical_response_encoding as p4b
from mechanistic_mind.ui.psy_observer_web import observer_serialization_fragment_cache as p4
from mechanistic_mind.ui.psy_observer_web.serialize import live_frame
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession

TICKS = {"n": 0}
BUDGET = 40


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _reset_budget() -> None:
    TICKS["n"] = 0


def _session_beta4(seed: int = 20261011) -> ObserverSession:
    _reset_budget()
    sess = ObserverSession()
    sess.apply_experiment(
        {
            "public_preset": "ACANTHOSTEGA_BETA4",
            "seed": seed,
            "agent_count": 2,
            "cognition_enabled": True,
        }
    )
    _tick(1)
    return sess


def test_01_consecutive_session_steps_advance_latest_trace():
    sess = _session_beta4(20261012)
    obs_ticks = []
    for _ in range(5):
        fr = sess.step(n=1)
        _tick(1)
        block = (fr.get("world") or {}).get("organism_receptor_grounded_3d_fpv") or {}
        latest = block.get("latest") or {}
        assert block.get("available") is True
        obs_ticks.append(int(latest["observation_tick"]))
        assert int(latest["receptor_tick"]) == int(latest["observation_tick"])
    assert obs_ticks == sorted(obs_ticks)
    assert obs_ticks[-1] > obs_ticks[0]
    assert len(set(obs_ticks)) >= 3


def test_02_same_state_poll_does_not_create_or_advance_trace():
    sess = _session_beta4(20261013)
    sess.step(n=3)
    _tick(3)
    st = fpv.state_of(sess.runtime.world)
    before_cap = int(st.capture_count)
    before = fpv.latest_exact_trace(sess.runtime.world, "agent_0")
    assert before is not None
    p1 = fpv.observer_payload(sess.runtime.world, selected_agent_id="agent_0")
    p2 = fpv.observer_payload(sess.runtime.world, selected_agent_id="agent_0")
    assert (p1.get("latest") or {}).get("trace_id") == (p2.get("latest") or {}).get("trace_id")
    assert (p1.get("latest") or {}).get("observation_tick") == before["observation_tick"]
    assert fpv.state_of(sess.runtime.world).capture_count == before_cap


def test_03_latest_survives_fifo_eviction():
    sess = _session_beta4(20261014)
    st = fpv.ensure_state(sess.runtime.world)
    st.capacity = 2
    for _ in range(5):
        sess.step(n=1)
        _tick(1)
    st = fpv.state_of(sess.runtime.world)
    assert st is not None
    assert st.evicted_count >= 1
    tr = fpv.latest_exact_trace(sess.runtime.world, "agent_0")
    assert tr is not None
    assert int(tr["observation_tick"]) == int(sess.runtime.tick) or int(tr["observation_tick"]) == int(
        sess.runtime.tick
    ) - 0
    # Latest must equal the most recent published observation for agent_0
    assert tr["observation_tick"] == max(
        int(h["observation_tick"])
        for h in st.history
        if str(h.get("agent_id")) == "agent_0"
    )


def test_04_agent_traces_isolated():
    sess = _session_beta4(20261015)
    sess.step(n=3)
    _tick(3)
    p0 = fpv.observer_payload(sess.runtime.world, selected_agent_id="agent_0")
    p1 = fpv.observer_payload(sess.runtime.world, selected_agent_id="agent_1")
    assert p0["available"] and p1["available"]
    assert p0["latest"]["agent_id"] == "agent_0"
    assert p1["latest"]["agent_id"] == "agent_1"
    assert p0["latest"]["trace_id"] != p1["latest"]["trace_id"]


def test_05_runtime_generations_do_not_mix():
    sess = _session_beta4(20261016)
    sess.step(n=2)
    _tick(2)
    st = fpv.state_of(sess.runtime.world)
    st.latest_by_agent["agent_0"]["runtime_generation"] = 1
    p = fpv.observer_payload(
        sess.runtime.world, selected_agent_id="agent_0", runtime_generation=99
    )
    assert p["available"] is False
    assert p["missing_reason"] == fpv.REASON_RUNTIME_GENERATION_MISMATCH


def test_06_true_zero_advances_as_valid_frame():
    sess = _session_beta4(20261017)
    sess.step(n=2)
    _tick(2)
    st = fpv.state_of(sess.runtime.world)
    # Force a true-zero exact trace as a new observation identity
    prev = st.latest_by_agent["agent_0"]
    zero = dict(prev)
    zero["observation_tick"] = int(prev["observation_tick"]) + 1
    zero["receptor_tick"] = zero["observation_tick"]
    zero["accepted_count"] = 0
    zero["accepted_contributions"] = []
    zero["true_zero_exact_trace"] = True
    zero["physical_signal_reached_receptor"] = False
    zero["trace_id"] = "true_zero_" + str(zero["observation_tick"])
    st.latest_by_agent["agent_0"] = zero
    p = fpv.observer_payload(sess.runtime.world, selected_agent_id="agent_0")
    assert p["available"] is True
    assert p["latest"]["true_zero_exact_trace"] is True
    assert p["missing_reason"] is None


def test_07_missing_trace_remains_unavailable():
    p = fpv.observer_payload(object(), selected_agent_id="agent_0")
    assert p["available"] is False
    assert p["missing_reason"] == fpv.REASON_NO_O4_TRACE_YET
    assert p["render_as_darkness_forbidden"] is True


def test_08_restore_does_not_create_or_replay_as_new():
    sess = _session_beta4(20261018)
    sess.step(n=2)
    _tick(2)
    st = fpv.state_of(sess.runtime.world)
    ser = fpv.serialize_state(st)
    before = st.capture_count
    rt2 = PhysicalSystemRuntime(seed=99, config=acanthostega_beta4_config())
    fpv.restore_state(rt2.world, ser)
    st2 = fpv.state_of(rt2.world)
    assert st2.capture_count == before
    assert fpv.latest_exact_trace(rt2.world, "agent_0") is not None


def test_09_snf_cache_hit_still_publishes_when_armed():
    """First stale seam: cache hit previously skipped FPV capture."""
    cfg = acanthostega_beta4_config()
    cfg.cognition.cognition_enabled = True
    rt = PhysicalSystemRuntime(seed=20261019, config=cfg)
    rt.technical_id = "agent_0"
    rt.tick = 1
    rt.body.tick = 1
    rt.world.tick = 1
    nfe = cfg.near_field_exteroception
    _SNF_CACHE.clear()
    begin_scientific_capture(
        rt.world,
        agent_id="agent_0",
        body_id="agent_0",
        decision_tick=1,
        run_id="t",
    )
    try:
        sample_near_field(
            world=rt.world, body=rt.body, cfg=nfe, physical_config=cfg, diagnostic=False
        )
        mid = fpv.latest_exact_trace(rt.world, "agent_0")
        assert mid is not None
        # Second call: cache hit must still keep/publish latest
        sample_near_field(
            world=rt.world, body=rt.body, cfg=nfe, physical_config=cfg, diagnostic=False
        )
        after = fpv.latest_exact_trace(rt.world, "agent_0")
        assert after is not None
        assert after["trace_id"] == mid["trace_id"]
        assert int(after["observation_tick"]) == int(mid["observation_tick"])
    finally:
        end_scientific_capture(rt.world)
    _tick(1)


def test_10_p4_world_frame_is_dynamic_family():
    assert p4.FAMILY_WORLD_FRAME in p4.DYNAMIC_FAMILIES
    assert p4.FAMILY_WORLD_FRAME not in p4.STABLE_FAMILIES


def test_11_p4b_same_tick_hit_and_new_tick_miss():
    sess = _session_beta4(20261020)
    sess.step(n=2)
    _tick(2)
    fr = live_frame(
        sess.runtime,
        status="PAUSED",
        mode="LIVE",
        target_tick=None,
        previous_body=None,
        detail="compact",
    )
    auth = p4b.authority_key_from_frame(
        fr,
        run_id="p7",
        runtime_generation=int(getattr(sess, "_runtime_generation", 0) or 0),
    )
    p4b.clear(reason="TEST")
    b1 = p4b.encode_and_cache(fr, auth)
    b2 = p4b.encode_and_cache(fr, auth)
    assert b1 == b2
    assert p4b.stats()["counters"]["hits"] >= 1
    # New scientific tick must miss
    sess.step(n=1)
    _tick(1)
    fr2 = live_frame(
        sess.runtime,
        status="PAUSED",
        mode="LIVE",
        target_tick=None,
        previous_body=None,
        detail="compact",
    )
    auth2 = p4b.authority_key_from_frame(
        fr2,
        run_id="p7",
        runtime_generation=int(getattr(sess, "_runtime_generation", 0) or 0),
    )
    assert auth2["scientific_tick"] != auth["scientific_tick"]
    before_miss = int(p4b.stats()["counters"]["misses"])
    p4b.encode_and_cache(fr2, auth2)
    assert int(p4b.stats()["counters"]["misses"]) >= before_miss + 1
    block = (fr2.get("world") or {}).get("organism_receptor_grounded_3d_fpv") or {}
    assert int((block.get("latest") or {}).get("observation_tick")) >= 1


def test_12_response_contains_fresh_trace_identity():
    sess = _session_beta4(20261021)
    fr0 = sess.step(n=1)
    _tick(1)
    fr1 = sess.step(n=1)
    _tick(1)
    t0 = (((fr0.get("world") or {}).get("organism_receptor_grounded_3d_fpv") or {}).get("latest") or {}).get(
        "trace_id"
    )
    t1 = (((fr1.get("world") or {}).get("organism_receptor_grounded_3d_fpv") or {}).get("latest") or {}).get(
        "trace_id"
    )
    assert t0 and t1 and t0 != t1


def test_13_polling_without_context_does_not_capture():
    sess = _session_beta4(20261022)
    sess.step(n=1)
    _tick(1)
    end_scientific_capture(sess.runtime.world)
    before = fpv.state_of(sess.runtime.world).capture_count
    full = getattr(sess.runtime.world, "_o4_last_reception_trace", None)
    assert fpv.capture_from_o4_trace(sess.runtime.world, full, diagnostic=False) is None
    assert fpv.state_of(sess.runtime.world).capture_count == before


def test_14_o5_timing_metadata_from_exact_trace():
    sess = _session_beta4(20261023)
    fr = sess.step(n=2)
    _tick(2)
    latest = (
        ((fr.get("world") or {}).get("organism_receptor_grounded_3d_fpv") or {}).get("latest") or {}
    )
    hdr = fr.get("header") or {}
    assert latest.get("observation_tick") is not None
    assert latest.get("receptor_tick") is not None
    # Visual delay may be zero; metadata must still track the observation, not be stuck at 0
    # after the sim has advanced past apply.
    assert int(hdr.get("tick") or 0) >= 2
    assert int(latest["observation_tick"]) >= 1


def test_15_perf_same_tick_response_cache_intact():
    sess = _session_beta4(20261024)
    sess.step(n=2)
    _tick(2)
    fr = live_frame(
        sess.runtime,
        status="PAUSED",
        mode="LIVE",
        target_tick=None,
        previous_body=None,
        detail="compact",
    )
    auth = p4b.authority_key_from_frame(
        fr,
        run_id="p7perf",
        runtime_generation=int(getattr(sess, "_runtime_generation", 0) or 0),
    )
    p4b.clear(reason="TEST")
    p4b.encode_and_cache(fr, auth)
    samples = []
    for _ in range(20):
        t0 = time.perf_counter()
        p4b.encode_and_cache(fr, auth)
        samples.append((time.perf_counter() - t0) * 1000.0)
    samples.sort()
    p95 = samples[int(0.95 * (len(samples) - 1))]
    assert p95 < 50.0  # same-tick hit must stay cheap
