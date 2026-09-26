
"""E2E: Observer Web session → V3 archive → Analyze Results path → analysis log."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from mechanistic_mind.ui.psy_observer_web.scientific_history import (
    load_evidence_package,
    published_run_dir,
    save_analysis_output,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.scientific_v3.api import RunEvidence
from mechanistic_mind.scientific_v3.analyzer_adapter import format_reconstruction_text
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.scientific_v3.writer import ScientificV3Writer

OUT = Path("results/mm_scientific_v3_phase1_core/web_e2e")
V2_FIXTURE = Path("results/mm_scientific_v3_phase1_core/web_e2e_v2_fixture")

REQUIRED_V3 = (
    "scientific_v3_meta.json",
    "identity_map.json",
    "scientific_spine.jsonl",
    "scientific_observations.jsonl",
    "scientific_decisions.jsonl",
    "scientific_motors.jsonl",
    "scientific_consequences.jsonl",
)


def _fresh(p: Path) -> Path:
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True)
    return p


def test_web_lifecycle_v3_archive_and_analyze_log():
    root = _fresh(OUT)
    cfg = SessionConfig(
        seed=17,
        results_root=str(root),
        buffer_capacity=128,
        speed=1.0,
        ui_hz=4.0,
    )
    sess = ObserverSession(config=cfg)
    sess.apply_experiment({
        "seed": 17,
        "agent_count": 2,
        "cognition_enabled": True,
        "world": {"width": 24, "height": 24, "boundary_mode": "WRAP_PERIODIC"},
    })

    n = 25
    for _ in range(n):
        sess.step()

    health = sess.v3_evidence_health()
    assert health["writer_attached"] is True, health
    assert health["last_error"] is None, health
    live = Path(health["live_dir"])
    assert live.is_dir()
    for name in REQUIRED_V3 + ("scientific_timeline.jsonl",):
        assert (live / name).is_file(), f"missing in live: {name}"

    stop = sess.stop(save=True)
    fin = stop.get("finalize") or sess._last_finalize or {}
    if not fin.get("accepted"):
        fin = sess.finalize_run(reason="USER_STOP_SAVED")
    assert fin.get("accepted"), fin
    rid = str(fin.get("run_id") or sess._active_run_id)
    assert rid.startswith("psyweb-")

    run_dir = published_run_dir(root, rid)
    assert run_dir.is_dir(), run_dir
    for name in REQUIRED_V3 + ("scientific_timeline.jsonl", "scientific_meta.json"):
        assert (run_dir / name).is_file(), f"archived missing {name}"

    pkg = load_evidence_package(
        evidence_dir=run_dir,
        runtime=None,
        cutoff_tick=int(fin.get("final_tick") or n),
        runtime_status="STOPPED",
        run_id=rid,
        identity={"run_id": rid, "agent_count": 2},
    )
    files = pkg.get("evidence_files") or []
    for name in REQUIRED_V3:
        assert name in files, f"{name} not in evidence_files: {files}"

    v3 = pkg.get("scientific_v3_core") or {}
    assert v3.get("evidence_version") == "SCIENTIFIC_V3"
    assert v3.get("status") == "AVAILABLE"
    assert int(v3.get("decision_receipts") or 0) >= n
    assert int(v3.get("complete_odmc_count") or 0) == int(v3.get("ticks_expected") or -1)

    ev = RunEvidence(run_dir)
    summary = ev.reconstruction_summary()
    assert summary["complete_odmc_chains"] == summary["ticks_expected_autonomous"]
    assert summary["decision_receipts"] == summary["ticks_expected_autonomous"]

    text = format_reconstruction_text(v3)
    assert "SCIENTIFIC_V3 CORE RECONSTRUCTION" in text

    report_text = (
        "MECHANISTIC MIND — RUN ANALYSIS\n"
        f"Evidence files: {', '.join(files)}\n"
        + text
        + "\nstructured cognition events: AVAILABLE via SCIENTIFIC_V3 DecisionReceipts\n"
    )
    out = save_analysis_output(
        run_dir,
        report_text=report_text,
        report_json={"scientific_v3_core": v3, "evidence_files": files},
    )
    downloaded = (out / "report.txt").read_text()
    assert "SCIENTIFIC_V3 CORE RECONSTRUCTION" in downloaded
    assert "scientific_spine.jsonl" in downloaded
    assert "structured cognition events: NOT AVAILABLE" not in downloaded


def test_v2_only_fixture_not_fabricated():
    root = _fresh(V2_FIXTURE)
    (root / "scientific_meta.json").write_text(json.dumps({
        "telemetry_mode": "SCIENTIFIC_V2_TIERED",
        "schema": "mm.psy_observer_web.scientific_meta.v2",
    }))
    (root / "scientific_timeline.jsonl").write_text(
        json.dumps({"tick": 1, "agent_id": "agent_0", "action": "WAIT"}) + "\n"
    )
    ver = RunEvidence.detect_evidence_version(root)
    assert ver in ("SCIENTIFIC_V2_TIERED", "SCIENTIFIC_V1_OR_V2")
    assert ver != "SCIENTIFIC_V3"

    pkg = load_evidence_package(
        evidence_dir=root,
        runtime=None,
        cutoff_tick=1,
        runtime_status="STOPPED",
        run_id="psyweb-fake-v2",
        identity={"run_id": "psyweb-fake-v2"},
    )
    assert "scientific_timeline.jsonl" in (pkg.get("evidence_files") or [])
    assert "scientific_spine.jsonl" not in (pkg.get("evidence_files") or [])
    v3 = pkg.get("scientific_v3_core") or {}
    assert v3.get("status") == "NOT_RECORDED"
    assert not v3.get("decision_receipts")


def test_determinism_still_exact_match_after_web_fix():
    def fp(rt):
        rows = []
        for i, s in enumerate(rt.slots):
            b = s.body
            rows.append({
                "i": i,
                "x": round(float(b.x), 10),
                "y": round(float(b.y), 10),
                "vx": round(float(b.vx), 10),
                "vy": round(float(b.vy), 10),
                "action": s.last_selected_action,
            })
        return {"tick": rt.tick, "slots": rows}

    def run(with_v3: bool):
        rt = TwoAgentRuntime(seed=99, config=PhysicalSystemConfig(), signal_enabled=False)
        w = None
        if with_v3:
            d = _fresh(OUT / "det_web")
            w = ScientificV3Writer(d, flush_every=32)
            w.open(run_id="det", generation=0)
        for _ in range(40):
            rt._step_once()
            if w:
                w.append_runtime_tick(rt)
        if w:
            w.close()
        return fp(rt)

    assert run(False) == run(True)
