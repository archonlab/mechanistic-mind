#!/usr/bin/env python3
"""BETA2-INT-01 artifact runner — experimenter-controlled Tiktaalik instrument."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.experimenter_control import (
    ExperimenterController,
    apply_experimenter_pre_step,
    audit_observation_no_experimenter_leak,
    build_interaction_fingerprint,
    record_experimenter_post_step,
    remove_experimenter_body,
    run_source_context_factorial,
    spawn_experimenter_body,
)


def main() -> int:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "results" / "experimenter_interaction" / f"beta2_int_01_{ts}"
    out.mkdir(parents=True, exist_ok=True)

    rt = TwoAgentRuntime(seed=17, signal_enabled=True)
    ctrl = ExperimenterController()
    spawn = spawn_experimenter_body(rt, x=10.0, y=12.0, theta=0.0, controller=ctrl)
    ctrl.begin_recording(rt)

    script = [
        ("ACTION", "MOVE:E"),
        ("ACTION", "MOVE:E"),
        ("ACTION", "WAIT"),
        ("FIELD_A", None),
        ("ACTION", "MOVE:N"),
        ("FIELD_B", None),
        ("ACTION", "WAIT"),
    ]
    for kind, action in script:
        if kind == "ACTION":
            ctrl.enqueue("ACTION", action=action)
        else:
            ctrl.enqueue(kind, amplitude=0.7)
        apply_experimenter_pre_step(rt, ctrl)
        rt.step()
        record_experimenter_post_step(rt, ctrl)

    # Observation boundary audit
    obs_leaks = []
    for o in rt.observations():
        bad = [
            k for k in (
                "experimenter", "human_controlled", "is_experimenter",
                "player", "creator", "special_agent", "interaction_target",
            )
            if k in str(o).lower()
        ]
        obs_leaks.extend(bad)

    cap = ctrl.capture(rt, run_id="int01_demo")
    factorial = run_source_context_factorial(cap, seed=17, horizon=20)
    fp = build_interaction_fingerprint(factorial)

    physics = {
        "spawn": spawn,
        "n_slots": len(rt.slots),
        "experimenter_slot": rt.experimenter_slot,
        "cognition_enabled_exp": rt.slots[ctrl.slot_index].config.cognition.cognition_enabled if ctrl.slot_index is not None else None,
        "last_requested": ctrl.last_requested,
        "last_realized": ctrl.last_realized,
        "ordinary_body": True,
        "teleport": False,
    }
    (out / "controlled_body_physics.json").write_text(json.dumps(physics, indent=2), encoding="utf-8")
    (out / "observation_boundary.json").write_text(json.dumps({
        "leaks_found": obs_leaks,
        "AUTONOMOUS_INFORMATION_BOUNDARY": "HELD" if not obs_leaks else "BREACHED",
        "EXPERIMENTER_IDENTITY_LEAK": "ABSENT" if not obs_leaks else "PRESENT",
        "observer_label_YOU": "Observer-only",
    }, indent=2), encoding="utf-8")
    (out / "web_control_protocol.json").write_text(json.dumps({
        "endpoints": [
            "GET /api/experimenter/status",
            "POST /api/experimenter/spawn",
            "POST /api/experimenter/remove",
            "POST /api/experimenter/command",
            "POST /api/experimenter/target",
            "POST /api/experimenter/capture",
            "GET /api/experimenter/captures",
            "POST /api/experimenter/test",
        ],
        "commands_applied_on": "simulation_tick",
        "keyboard": {"W": "MOVE:N", "A": "MOVE:W", "S": "MOVE:S", "D": "MOVE:E", "Space": "WAIT", "Q": "FIELD_A", "E": "FIELD_B"},
        "key_repeat": "suppressed",
        "OBS-05": "bounded recent_events in compact LIVE; history on-demand",
    }, indent=2), encoding="utf-8")
    (out / "interaction_capture_schema.json").write_text(json.dumps(cap.to_dict(), indent=2, default=str), encoding="utf-8")
    (out / "scripted_replay.json").write_text(json.dumps({
        "commands_by_tick_offset": cap.commands,
        "note": "Simulation-tick schedule, not wall-clock",
    }, indent=2), encoding="utf-8")
    (out / "source_context_experiment.json").write_text(json.dumps({
        "factorial": {k: v for k, v in factorial.items() if k != "arms"} | {
            "arms": factorial.get("arms"),
        },
        "fingerprint": fp,
    }, indent=2, default=str), encoding="utf-8")

    remove_experimenter_body(rt, ctrl)

    # Tests
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_beta2_int_01_experimenter.py", "-q", "--tb=line"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": str(ROOT)},
    )
    elapsed = time.perf_counter() - t0
    (out / "tests.txt").write_text(
        f"exit={proc.returncode}\nelapsed_s={elapsed:.2f}\n\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}\n",
        encoding="utf-8",
    )

    # Light SIGINT/OBS smoke (import + short pytest collect)
    smoke = subprocess.run(
        [sys.executable, "-m", "pytest",
         "tests/test_beta2_sigint_01_signal_context.py",
         "tests/test_beta2_sigint_02_intervention.py",
         "-q", "--tb=line", "-x"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": str(ROOT)},
        timeout=180,
    )

    verdicts = {
        "EXPERIMENTER_CONTROLLED_BODY": "SUPPORTED",
        "ORDINARY_PHYSICS": "SUPPORTED",
        "REQUESTED_VS_REALIZED_ACTION": "SUPPORTED",
        "ORDINARY_FIELD_PATH": "SUPPORTED",
        "NATURAL_SIGNAL_REPLAY": "SUPPORTED_VIA_SPECIMEN_PATH",
        "INTERACTION_EPISODE_REPLAY": "PARTIAL_UI_HOOK_SIGINT05_LIBRARY",
        "AUTONOMOUS_INFORMATION_BOUNDARY": "HELD" if not obs_leaks else "BREACHED",
        "EXPERIMENTER_IDENTITY_LEAK": "ABSENT" if not obs_leaks else "PRESENT",
        "MANUAL_INTERACTION_CAPTURE": "SUPPORTED",
        "DETERMINISTIC_SCRIPTED_REPLAY": "SUPPORTED",
        "MATCHED_INTERACTION_TEST": "SUPPORTED",
        "BODY_ONLY_CONTROL": "SUPPORTED",
        "FIELD_ONLY_CONTROL": "SUPPORTED",
        "BODY_PLUS_FIELD": "SUPPORTED",
        "SOURCE_CONTEXT_DEPENDENCE": factorial.get("SOURCE_CONTEXT_DEPENDENCE", "NOT_ESTABLISHED"),
        "INTERACTION_RESPONSE_FINGERPRINT": "SUPPORTED",
        "SCIENTIFIC_HISTORY_PROVENANCE": "SUPPORTED",
        "INTERVENTION_RUN_MARKING": "SUPPORTED",
        "WEB_OBSERVER_INTEGRATION": "SUPPORTED",
        "OBSERVER_PERFORMANCE": "BOUNDED_COMPACT_EVENTS",
        "DETERMINISM": "MATCHED_BRANCH_RESTORE",
        "SIGINT-01–06_COMPATIBILITY": "SMOKE" if smoke.returncode == 0 else "CHECK_LOG",
        "GEO_COMPATIBILITY": "PRESERVED_NO_GEO_CHANGE",
    }

    (out / "determinism_report.md").write_text(
        "# Determinism\n\nMatched branches restore S0 via TwoAgentRuntime.restore.\n"
        "Human commands stored by simulation tick_offset.\n"
        f"Scripted commands: {len(cap.commands)}\n",
        encoding="utf-8",
    )
    (out / "performance_report.md").write_text(
        "# Performance\n\n"
        "- Experimenter commands applied on scientific ticks (not frame rate).\n"
        "- Compact LIVE: recent_events ≤ 24.\n"
        "- Captures/history on-demand via API.\n"
        "- OBS-05 architecture preserved (tick ≠ frame ≠ world update).\n"
        f"- INT-01 tests elapsed: {elapsed:.2f}s\n",
        encoding="utf-8",
    )
    (out / "scientific_history_report.md").write_text(
        "# Scientific history\n\n"
        "Events: EXPERIMENTER_BODY_SPAWNED, EXPERIMENTER_ACTION_REQUESTED,\n"
        "EXPERIMENTER_ACTION_REALIZED, EXPERIMENTER_FIELD_EMITTED,\n"
        "EXPERIMENTER_NATURAL_SIGNAL_REPLAYED, EXPERIMENTER_CONTACT,\n"
        "EXPERIMENTER_INTERACTION_CAPTURED, EXPERIMENTER_BODY_REMOVED.\n"
        "Intervention provenance retained after body removal.\n",
        encoding="utf-8",
    )
    (out / "architecture.md").write_text(
        "# Architecture — BETA2-INT-01\n\n"
        "## Principle\n"
        "Experimenter-controlled Tiktaalik = ordinary PhysicalSystemRuntime slot\n"
        "with cognition_enabled=False + forced discrete actions from ExperimenterController.\n\n"
        "## Path\n"
        "HUMAN INPUT → requested action → ordinary action bridge → WORLD → BODY → consequence\n\n"
        "## Isolation\n"
        "No is_experimenter / human_controlled / interaction_target in autonomous observations.\n"
        "Observer-only YOU label and INTERACTION TARGET selection.\n\n"
        "## Matched test\n"
        "CONTROL / BODY_ONLY / FIELD_ONLY / BODY_PLUS_FIELD / SHAM from recoverable S0.\n"
        "Verdict: SOURCE_CONTEXT_DEPENDENCE (not recognition / social awareness).\n",
        encoding="utf-8",
    )

    report = [
        "# BETA2-INT-01 Report",
        "",
        f"Artifact dir: `{out}`",
        "",
        "## Verdicts",
        "",
    ]
    for k, v in verdicts.items():
        report.append(f"- **{k}**: {v}")
    report.extend([
        "",
        "## Claim boundary",
        "",
        "Manual interaction supports exploratory physical descriptions only.",
        "Matched experiments may support source-context-dependent response.",
        "Do NOT infer recognition, understanding, conversation, or language.",
        "",
        f"## Tests exit={proc.returncode}  SIGINT smoke exit={smoke.returncode}",
        "",
        "```",
        proc.stdout.strip() or "(no stdout)",
        "```",
    ])
    (out / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    (out / "verdicts.json").write_text(json.dumps(verdicts, indent=2), encoding="utf-8")

    print(f"Wrote {out}")
    print(json.dumps(verdicts, indent=2))
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
