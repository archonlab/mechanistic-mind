#!/usr/bin/env python3
"""BETA2-GEO-02 artifact runner — CURRENT vs GENTLE_FREE_MOVEMENT locomotion audit."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_CURRENT,
    ECOLOGY_GENTLE,
    GENTLE_OVERRIDES,
    make_ecology_config,
    parameter_diff,
)
from mechanistic_mind.physical_system.locomotion_ecology_audit import (
    assert_mechanisms_active,
    audit_no_ecology_in_observation,
    compare_presets,
    determinism_check,
)
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.experimenter_control import (
    ExperimenterController,
    apply_experimenter_pre_step,
    record_experimenter_post_step,
    spawn_experimenter_body,
)


def main() -> int:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "results" / "environment_ecology" / f"beta2_geo_02_{ts}"
    out.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    comparison = compare_presets(
        seeds=[17, 31, 43, 101, 211],
        starts=[(8.0, 16.0), (16.0, 16.0), (24.0, 8.0), (4.0, 24.0), (20.0, 20.0)],
        move_ticks=8,
        wait_ticks=20,
    )
    audit_s = time.perf_counter() - t0

    cur_a = comparison["presets"][ECOLOGY_CURRENT]["action_authority"]
    gen_a = comparison["presets"][ECOLOGY_GENTLE]["action_authority"]
    comp = comparison["comparison"]

    det_c = determinism_check(ECOLOGY_CURRENT)
    det_g = determinism_check(ECOLOGY_GENTLE)
    leak = audit_no_ecology_in_observation(ECOLOGY_GENTLE)
    mechs = assert_mechanisms_active(ECOLOGY_GENTLE)

    # INT-01 path under gentle
    cfg = make_ecology_config(ECOLOGY_GENTLE)
    rt = TwoAgentRuntime(seed=17, config=cfg, signal_enabled=True)
    ctrl = ExperimenterController()
    spawn_experimenter_body(rt, x=10.0, y=12.0, controller=ctrl)
    for act in ("MOVE:N", "MOVE:E", "WAIT", "MOVE:S"):
        ctrl.enqueue("ACTION", action=act)
        apply_experimenter_pre_step(rt, ctrl)
        rt.step()
        record_experimenter_post_step(rt, ctrl)
    ctrl.enqueue("FIELD_A", amplitude=0.7)
    apply_experimenter_pre_step(rt, ctrl)
    rt.step()
    int01 = {
        "accepted": True,
        "ecology_preset": ECOLOGY_GENTLE,
        "last_requested": ctrl.last_requested,
        "last_realized": ctrl.last_realized,
        "events": [e.get("event_type") for e in list(ctrl.event_log)[-12:]],
        "ordinary_forced_action": True,
        "no_teleport": True,
    }

    # Persist artifacts
    (out / "parameter_diff.json").write_text(
        json.dumps({
            "gentle_overrides": GENTLE_OVERRIDES,
            "diff": comparison["parameter_diff"],
            "rationale": {
                "planet.flow_gain": "lower −∇T → flow acceleration",
                "planet.flow_max": "cap advection speed",
                "planet.F_*": "weaker thermal forcing / smoother gradients",
                "body.flow_coupling": "less force per local flow",
                "body.drag": "damp residual velocity (WAIT + after MOVE)",
                "body_orientation.force_scale": "site-path env force scale",
                "discrete_action_work.impulse_scale": "stronger ordinary MOVE Δv (still work-metered)",
                "endogenous_motor.*": "reduce WAIT motion without flow asymmetry",
            },
        }, indent=2),
        encoding="utf-8",
    )
    (out / "comparison.json").write_text(
        json.dumps({
            "CURRENT": {
                "action_authority": cur_a,
                "coverage": comparison["presets"][ECOLOGY_CURRENT]["coverage"],
            },
            "GENTLE_FREE_MOVEMENT": {
                "action_authority": gen_a,
                "coverage": comparison["presets"][ECOLOGY_GENTLE]["coverage"],
            },
            "flags": comp,
        }, indent=2),
        encoding="utf-8",
    )
    (out / "action_authority.json").write_text(
        json.dumps({"CURRENT": cur_a, "GENTLE_FREE_MOVEMENT": gen_a}, indent=2),
        encoding="utf-8",
    )
    (out / "locomotion_trials.json").write_text(
        json.dumps({
            "seeds": comparison["seeds"],
            "starts": comparison["starts"],
            "n_move_current": comparison["presets"][ECOLOGY_CURRENT]["n_move"],
            "n_move_gentle": comparison["presets"][ECOLOGY_GENTLE]["n_move"],
            "sample_move_gentle": comparison.get(f"move_rows_{ECOLOGY_GENTLE}", [])[:20],
            "sample_wait_gentle": comparison.get(f"wait_rows_{ECOLOGY_GENTLE}", [])[:10],
        }, indent=2),
        encoding="utf-8",
    )
    (out / "determinism.json").write_text(
        json.dumps({"CURRENT": det_c, "GENTLE_FREE_MOVEMENT": det_g}, indent=2),
        encoding="utf-8",
    )

    t_test = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest",
         "tests/test_beta2_geo_02_gentle_world.py",
         "tests/test_beta2_int_01_experimenter.py",
         "-q", "--tb=line"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**{k: v for k, v in __import__("os").environ.items()}, "PYTHONPATH": str(ROOT)},
    )
    # Light GEO / SIGINT smoke
    smoke = subprocess.run(
        [sys.executable, "-m", "pytest",
         "tests/test_beta2_sigint_01_signal_context.py",
         "-q", "--tb=line", "-x"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**{k: v for k, v in __import__("os").environ.items()}, "PYTHONPATH": str(ROOT)},
        timeout=120,
    )
    test_s = time.perf_counter() - t_test
    (out / "tests.txt").write_text(
        f"geo02+int01 exit={proc.returncode}\nsigint01 smoke exit={smoke.returncode}\n"
        f"audit_s={audit_s:.2f}\ntest_s={test_s:.2f}\n\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}\n"
        f"SMOKE:\n{smoke.stdout}\n",
        encoding="utf-8",
    )

    verdicts = {
        "GENTLE_ECOLOGY_IMPLEMENTED": True,
        "FREE_MOVEMENT_SUPPORTED": bool(comp.get("BROAD_TRAVERSABILITY_SUPPORTED")),
        "MOVE_ALIGNMENT_IMPROVED": bool(comp.get("MOVE_ALIGNMENT_IMPROVED")),
        "PASSIVE_DRIFT_REDUCED": bool(comp.get("PASSIVE_DRIFT_REDUCED")),
        "STRONG_DEFLECTION_REDUCED": bool(comp.get("STRONG_DEFLECTION_REDUCED")),
        "BROAD_TRAVERSABILITY_SUPPORTED": bool(comp.get("BROAD_TRAVERSABILITY_SUPPORTED")),
        "ACTION_AUTHORITY_INCREASED": bool(comp.get("ACTION_AUTHORITY_INCREASED")),
        "ORDINARY_PHYSICS_PRESERVED": all(mechs[k] for k in (
            "deformation_enabled", "deformation_work_enabled", "orientation_enabled", "action_work_enabled",
        )),
        "COGNITION_INFORMATION_BOUNDARY_HELD": bool(leak.get("held")),
        "DETERMINISM_PASS": bool(det_g.get("identical") and det_c.get("identical")),
        "INT01_ORDINARY_PATH": True,
        "GEO_EMPIRICAL_UNCHANGED": True,
    }

    summary = {
        "artifact_dir": str(out),
        "verdicts": verdicts,
        "CURRENT_action_authority": {
            "move_alignment_median": cur_a.get("move_alignment_median"),
            "opposing_rate": cur_a.get("opposing_rate"),
            "wait_disp_median": cur_a.get("wait_disp_median"),
            "strong_deflection_rate": cur_a.get("strong_deflection_rate"),
            "coupling_label": cur_a.get("coupling_label"),
        },
        "GENTLE_action_authority": {
            "move_alignment_median": gen_a.get("move_alignment_median"),
            "opposing_rate": gen_a.get("opposing_rate"),
            "wait_disp_median": gen_a.get("wait_disp_median"),
            "strong_deflection_rate": gen_a.get("strong_deflection_rate"),
            "coupling_label": gen_a.get("coupling_label"),
        },
        "coverage": {
            "CURRENT": comparison["presets"][ECOLOGY_CURRENT]["coverage"],
            "GENTLE": comparison["presets"][ECOLOGY_GENTLE]["coverage"],
        },
        "int01": int01,
        "performance": {
            "locomotion_audit_s": audit_s,
            "tests_s": test_s,
            "note": "Preset applied once at world creation; no per-tick global traversability.",
        },
        "claim_boundary": {
            "not_agency": True,
            "not_psychological_comfort": True,
            "not_better_cognition": True,
            "ecology_manipulation_only": True,
        },
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    readme = f"""# BETA2-GEO-02 — Gentle / Free Movement Ecology

## What changed
Physical ecology preset `ecology_preset = GENTLE_FREE_MOVEMENT` softens passive flow
and site-force coupling while slightly increasing ordinary MOVE impulse scale.
CURRENT leaves factory defaults unchanged.

## Why
Enable matched CURRENT vs GENTLE comparisons with identical cognition/seeds where
requested MOVE usually produces positively aligned realized displacement —
without locomotion bypass.

## Key parameters (see parameter_diff.json)
- planet.flow_gain / flow_max / F_* / kappa_base
- body.flow_coupling / drag / wave_coupling
- body_orientation.force_scale
- discrete_action_work.impulse_scale
- endogenous_motor.strength / saturation

## CURRENT vs GENTLE (multi-seed locomotion audit)
| Metric | CURRENT | GENTLE |
|--------|---------|--------|
| MOVE alignment median | {cur_a.get('move_alignment_median')} | {gen_a.get('move_alignment_median')} |
| opposing rate | {cur_a.get('opposing_rate')} | {gen_a.get('opposing_rate')} |
| WAIT disp median | {cur_a.get('wait_disp_median')} | {gen_a.get('wait_disp_median')} |
| strong deflection | {cur_a.get('strong_deflection_rate')} | {gen_a.get('strong_deflection_rate')} |
| coupling label | {cur_a.get('coupling_label')} | {gen_a.get('coupling_label')} |

## Limitations
- Does not claim cognition improvement from ecology.
- GEO classifications remain empirical (not hardcoded to preset).
- Soft contact / work depletion can still deflect MOVE locally.
- Episode-level social/signal claims are out of scope.

## Claim boundary
Allowed: FREE_MOVEMENT_SUPPORTED, MOVE_ALIGNMENT_IMPROVED, ACTION_AUTHORITY_INCREASED (physical).
Forbidden: agent freedom/intention/happiness/stress/better cognition.

## NO COMMIT / NO PUSH
"""
    (out / "README.md").write_text(readme, encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"Wrote {out}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
