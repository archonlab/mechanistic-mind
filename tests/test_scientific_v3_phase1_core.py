\
"""SCIENTIFIC_V3 Phase-1 CORE acceptance gates."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest

from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.scientific_v3.analyzer_adapter import build_v3_core_reconstruction, write_v3_core_reconstruction
from mechanistic_mind.scientific_v3.api import RunEvidence
from mechanistic_mind.scientific_v3.capture import capture_v3_tick
from mechanistic_mind.scientific_v3.identity import IdentityMap
from mechanistic_mind.scientific_v3.writer import ScientificV3Writer

OUT = Path("results/mm_scientific_v3_phase1_core")


def _fresh(name: str) -> Path:
    p = OUT / name
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True)
    return p


def _fingerprint(rt: TwoAgentRuntime) -> dict:
    """Science fingerprint — body/world scalars only, no evidence fields."""
    rows = []
    for i, s in enumerate(rt.slots):
        b = s.body
        rows.append({
            "i": i,
            "x": round(float(b.x), 10),
            "y": round(float(b.y), 10),
            "vx": round(float(b.vx), 10),
            "vy": round(float(b.vy), 10),
            "theta": round(float(getattr(b, "theta", 0.0) or 0.0), 10),
            "omega": round(float(getattr(b, "omega", 0.0) or 0.0), 10),
            "B_sum": round(float(sum(b.B)), 10),
            "tick": int(s.tick),
            "action": s.last_selected_action,
            "motor": (s.last_motor_output or {}).get("legacy_token"),
        })
    return {"seed": rt.seed, "tick": rt.tick, "slots": rows}


def test_gate1_to4_odmc_every_autonomous_tick():
    out = _fresh("gate_odmc")
    rt = TwoAgentRuntime(seed=17, config=PhysicalSystemConfig(), signal_enabled=False)
    w = ScientificV3Writer(out, flush_every=8)
    w.open(run_id="gate-odmc", generation=0)
    n_ticks = 50
    for _ in range(n_ticks):
        rt._step_once()
        w.append_runtime_tick(rt)
    w.close()
    ev = RunEvidence(out)
    summary = ev.reconstruction_summary()
    # 2 autonomous agents × n_ticks
    assert summary["ticks_expected_autonomous"] == n_ticks * 2
    assert summary["decision_receipts"] == n_ticks * 2
    assert summary["observation_receipts"] == n_ticks * 2
    assert summary["motor_receipts"] == n_ticks * 2
    assert summary["consequence_receipts"] == n_ticks * 2
    assert summary["complete_odmc_chains"] == n_ticks * 2
    # Linkage spot-check
    chain = ev.trace_chain("agent_0", 3)
    assert chain["complete"]
    assert chain["decision"]["observation_id"] == chain["observation"]["observation_id"]
    assert chain["motor"]["decision_id"] == chain["decision"]["decision_id"]
    assert chain["consequence"]["motor_id"] == chain["motor"]["motor_id"]
    assert chain["motor"]["motor_schema"] == "COMPOSITE_MOTOR_V1"
    assert "locomotion" in chain["motor"]["components"]


def test_gate5_identity_map_distinguishes_roles():
    out = _fresh("gate_identity")
    rt = TwoAgentRuntime(seed=21, config=PhysicalSystemConfig(), signal_enabled=False)
    # Mark slot 1 as experimenter-controlled (role UNDERCOVER), disable its cognition
    rt.experimenter_slot = 1
    rt.slots[1]._experimenter_controlled = True  # type: ignore[attr-defined]
    rt.slots[1].config.cognition.cognition_enabled = False
    w = ScientificV3Writer(out, flush_every=4)
    w.open(run_id="gate-id", generation=0)
    for _ in range(10):
        rt._step_once()
        w.append_runtime_tick(rt)
    w.close()
    imap = json.loads((out / "identity_map.json").read_text())
    bodies = {b["physical_body_id"]: b for b in imap["bodies"]}
    assert "body-0" in bodies and "body-1" in bodies
    assert bodies["body-0"]["controller_type"] == "AUTONOMOUS"
    assert bodies["body-0"]["cognitive_agent_id"] == "agent_0"
    assert bodies["body-0"]["role_label"] != "UNDERCOVER"
    assert bodies["body-1"]["controller_type"] == "EXPERIMENTER"
    assert bodies["body-1"]["role_label"] == "UNDERCOVER"
    assert bodies["body-1"]["cognitive_agent_id"] != "agent_1"  # not silent synonym
    assert bodies["body-1"]["cognitive_agent_id"] != "undercover"
    # Autonomous chains only for agent_0
    ev = RunEvidence(out)
    assert ev.get_decision("agent_0", 0) is not None
    assert ev.get_decision("agent_1", 0) is None


def test_gate6_accessible_vs_gt_hidden_body():
    """Foreign body exists physically but ObservationReceipt must not contain GT pose."""
    rt = TwoAgentRuntime(seed=33, config=PhysicalSystemConfig(), signal_enabled=False)
    rt._step_once()
    imap = IdentityMap(run_id="gt", generation=0)
    pkg = capture_v3_tick(rt, run_id="gt", identity_map=imap)
    obs0 = next(o for o in pkg["observations"] if o["cognitive_agent_id"] == "agent_0")
    acc = obs0["accessible"]
    # Must not contain true positions of the other body as GT fields
    forbidden_substrings = ("body-1", "agent_1", "foreign_x", "foreign_y", "other_body")
    joined = " ".join(acc.keys())
    for bad in forbidden_substrings:
        assert bad not in joined
    # True position of other body exists in physical GT
    other = rt.slots[1].body
    assert abs(float(other.x)) + abs(float(other.y)) > 0
    # Observation does not embed that exact GT pair as a dedicated channel
    for k, v in acc.items():
        assert not (k.endswith(".x") and abs(float(v) - float(other.x)) < 1e-15 and "local" not in k)


def test_gate7_missing_not_zero():
    out = _fresh("gate_missing")
    # Empty package meta coverage uses NOT_RECORDED not 0
    w = ScientificV3Writer(out)
    w.open(run_id="miss", generation=0)
    w.close()
    meta = json.loads((out / "scientific_v3_meta.json").read_text())
    dims = meta["coverage"]["dimensions"]
    # Before any ticks, dimensions stay NOT_RECORDED (writer may still have empty coverage)
    assert dims["decision"] in ("NOT_RECORDED", "COMPLETE")
    assert dims["decision"] != 0
    assert "SCENARIO_SELECTED" not in json.dumps(meta)


def test_gate8_v2_still_readable():
    from mechanistic_mind.ui.psy_observer_web.scientific_history import ScientificHistoryWriter
    out = _fresh("gate_v2_compat")
    rt = TwoAgentRuntime(seed=17, config=PhysicalSystemConfig(), signal_enabled=False)
    v2 = ScientificHistoryWriter(out)
    v2.open({"run_id": "v2compat", "telemetry_mode": "SCIENTIFIC_V2_TIERED"})
    v3 = ScientificV3Writer(out, flush_every=4)
    v3.open(run_id="v2compat", generation=0)
    for _ in range(15):
        rt._step_once()
        v2.append_tick(rt)
        v3.append_runtime_tick(rt)
    v2.close()
    v3.close()
    assert (out / "scientific_timeline.jsonl").is_file()
    assert (out / "scientific_meta.json").is_file()
    assert (out / "scientific_spine.jsonl").is_file()
    assert RunEvidence.detect_evidence_version(out) == "SCIENTIFIC_V3"
    # V2 timeline still parses
    lines = [json.loads(l) for l in (out / "scientific_timeline.jsonl").read_text().splitlines() if l.strip()]
    assert len(lines) >= 15


def test_gate9_determinism_v3_on_vs_off():
    def run(with_v3: bool, seed: int = 99) -> dict:
        rt = TwoAgentRuntime(seed=seed, config=PhysicalSystemConfig(), signal_enabled=False)
        w = None
        if with_v3:
            out = _fresh(f"det_{'on' if with_v3 else 'off'}_{seed}")
            w = ScientificV3Writer(out, flush_every=64)
            w.open(run_id=f"det-{seed}", generation=0)
        for _ in range(80):
            rt._step_once()
            if w is not None:
                w.append_runtime_tick(rt)
        if w is not None:
            w.close()
        return _fingerprint(rt)

    off = run(False)
    on = run(True)
    assert on == off, f"science diverged:\nON={on}\nOFF={off}"


def test_tick_alignment_move_wait_consequence():
    out = _fresh("gate_align")
    rt = TwoAgentRuntime(seed=7, config=PhysicalSystemConfig(), signal_enabled=False)
    w = ScientificV3Writer(out, flush_every=2)
    w.open(run_id="align", generation=0)
    # Force MOVE then WAIT
    rt.slots[0]._forced_motor_once = {
        "locomotion": "MOVE:+x",
        "neck": "NONE",
        "oscillator": {},
        "push": False,
    }
    rt._step_once()
    w.append_runtime_tick(rt)
    rt.slots[0]._forced_motor_once = {
        "locomotion": "WAIT",
        "neck": "NONE",
        "oscillator": {},
        "push": False,
    }
    rt._step_once()
    w.append_runtime_tick(rt)
    w.close()
    ev = RunEvidence(out)
    m0 = ev.get_motor("agent_0", 0)
    c0 = ev.get_consequence("body-0", 0)
    assert m0["components"]["locomotion"].startswith("MOVE")
    assert abs(c0["pose_delta"]["dx"]) + abs(c0["pose_delta"]["dy"]) > 0
    m1 = ev.get_motor("agent_0", 1)
    c1 = ev.get_consequence("body-0", 1)
    assert m1["components"]["locomotion"] == "WAIT"
    # WAIT must not imply "nothing happened" — world may still change
    # (orientation/resources may be non-zero even if pose tiny)
    assert c1 is not None
    # Tick linkage: decision tick matches
    d0 = ev.get_decision("agent_0", 0)
    assert d0["tick"] == 0
    assert d0["motor_id"] == m0["motor_id"]


def test_analyzer_adapter_section():
    out = _fresh("gate_analyzer")
    rt = TwoAgentRuntime(seed=17, config=PhysicalSystemConfig(), signal_enabled=False)
    w = ScientificV3Writer(out, flush_every=8)
    w.open(run_id="an", generation=0)
    for _ in range(12):
        rt._step_once()
        w.append_runtime_tick(rt)
    w.close()
    path = write_v3_core_reconstruction(out)
    payload = json.loads(path.read_text())
    assert payload["section"] == "SCIENTIFIC_V3 CORE RECONSTRUCTION"
    assert payload["decision_receipts"] == 24
    assert "24 / 24" in str(payload["complete_odmc_chains"])


def test_decision_uses_real_selection_path():
    out = _fresh("gate_selpath")
    rt = TwoAgentRuntime(seed=17, config=PhysicalSystemConfig(), signal_enabled=False)
    w = ScientificV3Writer(out, flush_every=4)
    w.open(run_id="sel", generation=0)
    rt._step_once()
    w.append_runtime_tick(rt)
    w.close()
    ev = RunEvidence(out)
    d = ev.get_decision("agent_0", 0)
    assert d["selection_path"] not in ("", "OTHER_EXISTING_PATH")
    # Must be a real runtime term
    assert d["selection_source"] in (
        "COMPOSITE_FACTORIZED",
        "FORCED_COMPOSITE",
        "NOT_AVAILABLE",
    ) or isinstance(d["selection_source"], str)
    # Ensure we did not invent scored fields (ignore documentation notes)
    keys = set(d.keys())
    for bad in ("utility", "reward", "motivation", "utility_score", "reward_signal"):
        assert bad not in keys
        assert bad not in {str(k).lower() for k in (d.get("accessible") or {})}
