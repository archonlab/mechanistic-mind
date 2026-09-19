"""Beta 2: LIVE world interventions × reset semantics × provenance (L1–L24).

Does not retune physics/cognition. Observer session + Analyzer only.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mechanistic_mind.physical_system import TwoAgentRuntime
from mechanistic_mind.physical_system.ecology_presets import make_ecology_config
from mechanistic_mind.ui.psy_observer_web.live_intervention import (
    WORLD_STRUCTURAL_KEYS,
    classify_control,
    regimes_from_interventions,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession
from mechanistic_mind.research.climate_authority import effective_world_fingerprint


ROOT = Path(__file__).resolve().parents[1]
APP_TSX = ROOT / "web" / "psy-observer" / "src" / "App.tsx"


@pytest.fixture()
def sess():
    s = ObserverSession()
    s.apply_experiment({
        "seed": 17,
        "ecology_preset": "BASELINE_CLIMATE_DEFAULT",
        "agent_count": 2,
        "cognition_enabled": True,
        "world": {"width": 24, "height": 24, "boundary_mode": "WRAP_PERIODIC"},
    })
    return s


def _agent_ids(runtime):
    if getattr(runtime, "slots", None):
        return [f"agent_{i}" for i in range(len(runtime.slots))]
    return ["agent_0"]


def _body_xy(runtime):
    if getattr(runtime, "slots", None):
        b = runtime.slots[0].body
    else:
        b = runtime.body
    return (float(b.x), float(b.y), float(getattr(b, "vx", 0.0) or 0.0))


def _cognition_blob(runtime):
    if getattr(runtime, "slots", None):
        return runtime.slots[0].cognition
    return runtime.cognition


def test_L1_set_world_exposes_destructive_reset(sess):
    text = APP_TSX.read_text(encoding="utf-8")
    assert ("APPLY &amp; RESET WORLD" in text) or ("APPLY & RESET WORLD" in text)
    gen0 = sess._runtime_generation
    out = sess.apply_experiment({
        "seed": 17,
        "ecology_preset": "BASELINE_CLIMATE_DEFAULT",
        "agent_count": 2,
        "world": {"width": 24, "height": 24, "boundary_mode": "WRAP_PERIODIC"},
    })
    assert out["control_receipt"]["operation"] == "APPLY_AND_RESET_WORLD"
    assert out["control_receipt"].get("requires_reset") is True
    assert sess._runtime_generation == gen0 + 1


def test_L2_L5_L20_live_ecology_preserves_agents(sess):
    sess.step(n=5)
    tick0 = int(sess.runtime.tick)
    gen0 = sess._runtime_generation
    ids0 = _agent_ids(sess.runtime)
    cog0 = id(_cognition_blob(sess.runtime))
    xy0 = _body_xy(sess.runtime)
    out = sess.apply_live_intervention({
        "ecology_preset": "CURRENT_LEGACY",
        "category": "ecology",
        "source": "test",
    })
    assert out["control_receipt"]["accepted"] is True
    assert out["control_receipt"]["operation"] == "LIVE_INTERVENTION"
    assert out["control_receipt"].get("requires_reset") is False
    assert int(sess.runtime.tick) == tick0
    assert sess._runtime_generation == gen0
    assert _agent_ids(sess.runtime) == ids0
    assert id(_cognition_blob(sess.runtime)) == cog0
    assert _body_xy(sess.runtime)[:2] == xy0[:2]
    assert getattr(sess.runtime.config, "ecology_preset", None) in {
        "CURRENT_LEGACY", "CURRENT",
    }


def test_L6_mechanism_toggle_remains_live(sess):
    sess.step(n=3)
    tick0 = int(sess.runtime.tick)
    gen0 = sess._runtime_generation
    cog0 = id(_cognition_blob(sess.runtime))
    out = sess.set_mechanism("spatiotemporal_climate_ecology", False)
    assert out["control_receipt"]["accepted"] is True
    assert out["control_receipt"]["request"].get("live") is True
    assert int(sess.runtime.tick) == tick0
    assert sess._runtime_generation == gen0
    assert id(_cognition_blob(sess.runtime)) == cog0
    assert len(sess._world_interventions) >= 1


def test_L7_world_structural_not_falsely_live():
    assert classify_control("seed") == "WORLD_STRUCTURAL"
    assert classify_control("width") == "WORLD_STRUCTURAL"
    assert classify_control("ecology_preset") == "LIVE"
    assert classify_control("mechanism.spatiotemporal_climate_ecology") == "LIVE"
    for k in ("seed", "width", "height", "agent_count"):
        assert k in WORLD_STRUCTURAL_KEYS


def test_L7_live_api_rejects_structural(sess):
    sess.step(n=2)
    out = sess.apply_live_intervention({"seed": 999, "ecology_preset": "CURRENT_LEGACY"})
    assert out["control_receipt"]["accepted"] is False
    assert "WORLD-STRUCTURAL" in str(out["control_receipt"].get("reason") or "")


def test_L8_L12_provenance_fields_and_order(sess):
    sess.step(n=4)
    t1 = int(sess.runtime.tick)
    sess.apply_live_intervention({"ecology_preset": "CURRENT_LEGACY", "category": "ecology"})
    assert len(sess._world_interventions) >= 1
    ev0 = sess._world_interventions[0]
    assert ev0["type"] == "WORLD_INTERVENTION"
    assert int(ev0["simulation_tick"]) == t1
    assert "ecology_preset" in ev0["changes"]
    assert ev0["changes"]["ecology_preset"]["old"] != ev0["changes"]["ecology_preset"]["new"]
    assert ev0["effective_world_fingerprint_before"]
    assert ev0["effective_world_fingerprint_after"]
    assert ev0["effective_world_fingerprint_before"] != ev0["effective_world_fingerprint_after"]
    assert ev0["history_reset"] is False
    assert ev0["cognition_reset"] is False
    assert ev0["body_reset"] is False

    sess.step(n=2)
    t2 = int(sess.runtime.tick)
    sess.set_mechanism("spatiotemporal_climate_ecology", True)
    sess.step(n=1)
    sess.set_mechanism("spatiotemporal_climate_ecology", False)
    assert len(sess._world_interventions) >= 2
    ticks = [int(e["simulation_tick"]) for e in sess._world_interventions]
    assert ticks == sorted(ticks)
    assert ticks[0] == t1
    assert ticks[-1] >= t2


def test_L13_L16_analyzer_regimes(sess):
    sess.step(n=3)
    sess.apply_live_intervention({"ecology_preset": "CURRENT_LEGACY"})
    sess.step(n=2)
    sess.set_mechanism("spatiotemporal_climate_ecology", True)
    items = list(sess._world_interventions)
    report = regimes_from_interventions(
        items,
        start_tick=0,
        end_tick=int(sess.runtime.tick),
        initial_fingerprint=sess._world_intervention_fp0,
    )
    assert report["configuration_history"] == "MULTI_REGIME"
    assert report["n_interventions"] >= 1
    assert report["n_regimes"] == report["n_interventions"] + 1
    assert "must not be treated" in (report.get("note") or "")


def test_L14_static_when_no_interventions(sess):
    sess.step(n=5)
    report = regimes_from_interventions(
        [],
        start_tick=0,
        end_tick=int(sess.runtime.tick),
        initial_fingerprint=sess._world_intervention_fp0,
    )
    assert report["configuration_history"] == "STATIC"
    assert report["n_interventions"] == 0
    assert report["n_regimes"] == 1


def test_L17_L18_reset_clears_intervention_provenance(sess):
    sess.step(n=3)
    sess.apply_live_intervention({"ecology_preset": "CURRENT_LEGACY"})
    assert len(sess._world_interventions) >= 1
    gen0 = sess._runtime_generation
    old_ids = [e["event_id"] for e in sess._world_interventions]
    sess.apply_experiment({
        "seed": 17,
        "ecology_preset": "BASELINE_CLIMATE_DEFAULT",
        "agent_count": 2,
        "world": {"width": 24, "height": 24, "boundary_mode": "WRAP_PERIODIC"},
    })
    assert sess._runtime_generation == gen0 + 1
    assert sess._world_interventions == []
    assert all(eid not in {e.get("event_id") for e in sess._world_interventions} for eid in old_ids)


def test_L19_ui_only_intended_world_reset_control():
    text = APP_TSX.read_text(encoding="utf-8")
    assert ("APPLY &amp; RESET WORLD" in text) or ("APPLY & RESET WORLD" in text)
    assert "experimentScreen === 'set_world'" in text
    assert "APPLY LIVE" in text


def test_L21_effective_world_fingerprint_stable_api():
    cfg = make_ecology_config("BASELINE_CLIMATE_DEFAULT")
    rt = TwoAgentRuntime(seed=17, config=cfg, signal_enabled=False)
    fp1 = effective_world_fingerprint(runtime=rt)
    fp2 = effective_world_fingerprint(runtime=rt)
    assert fp1 == fp2
    assert isinstance(fp1, str) and len(fp1) >= 8


def test_frontend_configuration_history_module():
    p = ROOT / "web" / "psy-observer" / "src" / "analysis" / "configurationHistory.ts"
    assert p.is_file()
    src = p.read_text(encoding="utf-8")
    assert "MULTI_REGIME" in src
    assert "STATIC" in src
    assert "WORLD_INTERVENTION" in src
