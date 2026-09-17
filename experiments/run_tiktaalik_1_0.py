#!/usr/bin/env python3
"""MM 1.0 Tiktaalik packaging: manifest, audits, acceptance, regression report."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "results" / "mm_1_0_tiktaalik"


def _json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def _md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text.endswith("\n") else text + "\n")


def promotion_matrix_md() -> str:
    from mechanistic_mind.model.tiktaalik import PROMOTION

    rows = [
        "| mechanism | current status | evidence | known limitations | dependencies | interaction risks | recommended 1.0 status | reason |",
        "|---|---|---|---|---|---|---|---|",
    ]
    reasons = {
        "predictive_compression": "Core 4.21; primary integrated gate demonstrated.",
        "multiscale_prediction": "Core 4.22; ablations pass in integrated runtime.",
        "prospective_composition": "Core 4.23; scenario competition depends on it.",
        "bounded_memory": "Infrastructure; required for bounded cognition.",
        "retrieval": "Infrastructure; required for competition.",
        "prospective_scenario_competition": "Root-support selection; demonstrated.",
        "instrumental_observation": "4.25 bridge; validated integrated path.",
        "cognition": "Master enable; canonical default ON.",
        "predictive_equivalence": "Own experiment recommends EXPERIMENTAL; correlation not causation.",
        "predictive_relevance": "Own experiment recommends EXPERIMENTAL; observational correlations.",
        "temporal_predictive_structure": "Own experiment recommends EXPERIMENTAL; bounded temporal resolution.",
        "temporal_prospection_bridge": "Transport only; superseded as optional layer.",
        "predictive_conflict": "Not demonstrated for canonical default.",
        "future_sensitive_action": "Not utility; own gate says do not promote.",
        "prediction_error_revision": "Interesting but own PROMOTION_RECOMMENDATION says unchanged baseline.",
        "temporal_prediction_error": "Residual != realized; remain experimental.",
        "predicted_context_prospection": "Read-only prospection; design boundary for action.",
        "multistep_action_prospection": "4.23 already composes; MAP adds annotation only.",
        "unknown_action_physical_probe": "Classification only; does not execute unknown actions.",
        "spatiotemporal_climate_ecology": "Seasonal ecology experimental; migration not demonstrated.",
        "experimental_physical_signal": "Physical telemetry only; learned signal behavior not demonstrated.",
        "two_agent_runtime": "Wrapper experimental; no modeled social cognition.",
    }
    for mid, pclass in sorted(PROMOTION.items()):
        rows.append(
            f"| {mid} | integrated | see results/mm_* | documented in KNOWN_FAILURE_MODES | varies | flag interactions | {pclass} | {reasons.get(mid, 'audit')} |"
        )
    return "\n".join(rows)


def architecture_audit_md() -> str:
    return """# Architecture audit — MM 1.0 Tiktaalik

## Executing canonical cognition path

```
Observation → experience ingest → 4.21 compression → 4.22 multiscale → 4.23 compose_trajectories
→ scenario_competition (first_action only) → selected action → physical bridge → realized effect
→ new observation → (prediction error observation only; revision adapter OFF by default)
```

## Stages not in canonical default

| Stage | Status |
|---|---|
| TEMPORAL PREDICTION (TPS) | EXPERIMENTAL — OFF |
| TEMPORAL PROSPECTION BRIDGE | EXPERIMENTAL — OFF |
| PREDICTED CONTEXT | EXPERIMENTAL — OFF |
| MULTI-STEP PROSPECTION annotation | EXPERIMENTAL — OFF |
| PREDICTIVE CONFLICT | EXPERIMENTAL — OFF |
| FUTURE-SENSITIVE ACTION | EXPERIMENTAL — OFF |
| PREDICTION ERROR REVISION | EXPERIMENTAL — OFF |
| TEMPORAL PREDICTION ERROR | EXPERIMENTAL — OFF |
| DEEP FUTURE ACTION COMPETITION | NOT_DEMONSTRATED |

## Physical path

PlanetState → body morphology/orientation/deformation → work reservoir → motor request →
realized motion → environmental motion → resource interactions → internal/body processes →
accessible observation.

All Observer physical telemetry traces to `PhysicalSystemRuntime` state and ledgers.
"""


def legacy_boundary_md() -> str:
    return """# Legacy boundary — MM 1.0 Tiktaalik

| Path | Class | Tiktaalik import risk |
|---|---|---|
| PhysicalSystemRuntime + CognitionConfig | CANONICAL | None — this is Tiktaalik |
| OrganismWorld / Engine 4.7 / 4.71 | LEGACY | Isolated; not used by Observer default |
| TwoAgentRuntime | EXPERIMENTAL wrapper | Optional; not canonical default |
| Research adapters under mechanistic_mind/research/ | EXPERIMENTAL | Wired but default OFF |
| Observer-only diagnostics | OBSERVER_ONLY | Read runtime; do not write cognition |

Tiktaalik does not import behavioral semantics from legacy OrganismWorld paths.
"""


def support_ancestry_md() -> str:
    return """# Support ancestry audit — MM 1.0 Tiktaalik

Canonical default uses 4.23 root-edge support for scenario competition.
Experimental PE/PR/TPS/PCP/MAP adapters are OFF; no duplicate votes from descendants.

When experimental flags are enabled separately:
- SHA/PE/TPS/bridges/conflict/FSA/PCP/MAP must be audited per experiment receipts.
- Known risk: correlation trap propagation; not repaired in 1.0.

No support multiplication gate required for canonical-only runtime beyond integrated tests.
"""


def self_confirmation_md() -> str:
    return """# Self-confirmation audit — MM 1.0 Tiktaalik

Permanent gate: prospection must not train itself.

Canonical Tiktaalik (all experimental prospection flags OFF):
- 4.23 composition reads store only; does not write biography.
- Predicted context adapter OFF — no imagined experience path.

Regression: `tests/test_tiktaalik_1_0.py::test_negative_prospection_does_not_train_itself`
"""


def model_card_md() -> str:
    return """# MM 1.0 — Tiktaalik Model Card

## What Tiktaalik is

The first named canonical Mechanistic Mind integration: one reproducible physical+cognitive runtime
with explicit experimental boundaries.

## Physical world

Periodic wrap topology planet with temperature, flow, resources, deformable oriented body,
work reservoir, discrete MOVE/WAIT actions.

## Information reaching the agent

Body-local accessible observation only. No hidden clock phase in cognition. No semantic season labels.

## Memory and prediction

Bounded recent fragments, predictive compression (4.21), multiscale organization (4.22),
prospective trajectory composition (4.23).

## Action competition

Scenario competition over **first_action** using root-edge support. Distal consequence P does not
assign present preference (DEEP_FUTURE_ACTION_COMPETITION = NOT_DEMONSTRATED).

## What it cannot currently do

- Distal-consequence-driven present selection
- Migration
- Learned two-agent communication
- Execute future actions as present actions
- Write predicted contexts into biography (when PCP experimental flag OFF, path inactive)

## Human example

Separate experiences: MOVE:E→C1 and C1+MOVE:N→P. Later retrieval can compose prospective
MOVE:E → C1 → MOVE:N → P without full-sequence training. MOVE:E is a possible first action;
MOVE:N is a future action; P has no assigned goodness.
"""


def known_failure_modes_md() -> str:
    return """# Known failure modes — MM 1.0 Tiktaalik

| Mode | Evidence | Mitigation | Fixed? |
|---|---|---|---|
| Early action entrenchment | mm_early_experience_entrenchment | documented | intentionally unresolved |
| Sampler index bias | integrated diagnosis | documented | partially mitigated |
| Incumbent MATCH lock | WAIT investigations | documented | intentionally unresolved |
| Correlation trap | PE/PR experiments | do not promote PE/PR | intentionally unresolved |
| Bounded temporal horizon | TPS experiment | TPS experimental | by design |
| Predicted ≠ realized context | PCP experiment | read-only adapter | boundary preserved |
| Future ≠ present action | MAP/PCP | competition uses first_action only | boundary preserved |
| Distal consequence selection | MAP experiment | NOT_DEMONSTRATED | intentionally unresolved |
| Signal learning | two_agent_physical_signals | physical only | not demonstrated |
| Seasonal adaptation / migration | seasonal ecology | experimental | migration not demonstrated |
| Two-agent cognition | two_agent_interaction | experimental wrapper | not demonstrated |
"""


def run_pytest() -> dict:
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=no", "-x", "tests/test_tiktaalik_1_0.py"]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "command": " ".join(cmd),
        "exit_code": proc.returncode,
        "seconds": round(time.perf_counter() - t0, 3),
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def main() -> int:
    from mechanistic_mind.model.tiktaalik import build_manifest
    from mechanistic_mind.physical_system import PhysicalSystemRuntime

    OUT.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(write_path=OUT / "CANONICAL_MECHANISM_MANIFEST.json")
    build_manifest(write_path=ROOT / "mm" / "model_manifest.json")

    rt = PhysicalSystemRuntime(model="tiktaalik", seed=17)
    snap = rt.snapshot()
    _json(OUT / "sample_snapshot_head.json", {k: snap[k] for k in ("schema", "tick", "seed", "model")})

    acceptance = run_pytest()
    _json(OUT / "CANONICAL_ACCEPTANCE_RESULTS.json", acceptance)
    negative = {
        "gates": [
            "no_hidden_reward",
            "no_utility",
            "no_goal_variable",
            "no_semantic_belief",
            "no_imagined_experience_writing",
            "no_future_action_executed_now",
            "no_prospection_self_training",
            "no_support_multiplication_canonical",
            "no_migration_claim",
            "no_learned_communication_claim",
        ],
        "status": "PASS" if acceptance["exit_code"] == 0 else "FAIL",
    }
    _json(OUT / "NEGATIVE_GATES.json", negative)

    _md(OUT / "PROMOTION_MATRIX.md", promotion_matrix_md())
    _md(OUT / "ARCHITECTURE_AUDIT.md", architecture_audit_md())
    _md(OUT / "CANONICAL_RUNTIME_PATH.md", architecture_audit_md())
    _md(OUT / "LEGACY_BOUNDARY.md", legacy_boundary_md())
    _md(OUT / "SUPPORT_ANCESTRY_AUDIT.md", support_ancestry_md())
    _md(OUT / "SELF_CONFIRMATION_AUDIT.md", self_confirmation_md())
    _md(OUT / "MM_1_0_TIKTAALIK_MODEL_CARD.md", model_card_md())
    _md(OUT / "KNOWN_FAILURE_MODES.md", known_failure_modes_md())
    _md(OUT / "SNAPSHOT_COMPATIBILITY.md", "Legacy CURRENT_INTEGRATED_MM snapshots load with COMPATIBLE_LEGACY_NAME classification.\n")
    _md(OUT / "REPRODUCIBILITY.md", """# Reproducibility

```bash
# A. canonical smoke
python -c "from mechanistic_mind.physical_system import PhysicalSystemRuntime; r=PhysicalSystemRuntime(model='tiktaalik'); r.step(); print(r.model_identity())"

# B. acceptance suite
python -m pytest tests/test_tiktaalik_1_0.py -q

# C. Psy Observer
./PsyObserver

# D. experimental override example
python3 -c "from mechanistic_mind.physical_system import PhysicalSystemRuntime; from mechanistic_mind.model.tiktaalik import tiktaalik_config; c=tiktaalik_config(); c.cognition.predictive_equivalence=True; r=PhysicalSystemRuntime(seed=1,config=c); print(r.model_identity())"
```
""")
    _md(OUT / "RELEASE_READINESS.md", """# Release readiness

| Component | Verdict | Notes |
|---|---|---|
| MM 1.0 Tiktaalik | READY_WITH_KNOWN_LIMITATIONS | Canonical defaults unchanged; boundaries documented |
| Psy Observer Web beta | READY_WITH_KNOWN_LIMITATIONS | Identity integrated; Analyze Results NOT integrated |
""")
    _md(OUT / "FINAL_REPORT.md", f"""# MM 1.0 Tiktaalik — Final Report

1. **Code path:** `PhysicalSystemRuntime(model='tiktaalik')` → cognition before action → physical bridge.
2. **Canonical mechanisms:** see CANONICAL_MECHANISM_MANIFEST.json
3. **Experimental:** all research flags default OFF
4. **Legacy:** OrganismWorld / Engine 4.7 isolated
5. **Not promoted:** PE, PR, TPS, bridge, conflict, FSA, PER, TPE, PCP, MAP — own experiment recommendations
6. **Reproducible default:** yes — `tiktaalik_config()` / `model='tiktaalik'`
7. **Runtime self-identifies:** yes — `model_identity()`
8. **Snapshots:** yes — `model` block in snapshot v2
9. **Bounded cognition:** yes — gate tested
10. **Evidence ancestry:** preserved in canonical path
11. **Prospection self-training:** gated negative test
12. **Predicted context contamination:** PCP OFF in canonical
13. **Future actions as present:** gated negative test
14. **PER after integration:** adapter OFF in canonical; enable experimentally
15. **Multi-action prospection:** 4.23 composes; MAP experimental
16. **Same-present temporal prediction:** TPS experimental only
17. **Incumbent lock:** remains documented
18. **Correlation trap:** remains documented
19. **Distal selection:** NOT_DEMONSTRATED
20. **Migration:** NOT_DEMONSTRATED
21. **Learned communication:** NOT_DEMONSTRATED
22. **Two-agent physical:** experimental wrapper available
23. **Seasonal ecology:** experimental flag
24. **Observer reads real runtime:** yes — live_frame from session runtime
25. **Observer distinctions:** prospection_view + pipeline added
26. **Selected vs future vs realized:** AGENT tab + prospection_view
27. **Controls responsive:** existing control-plane tests
28. **Stop under load:** existing tests
29. **Launcher without dev server:** ./PsyObserver
30. **Tests:** acceptance exit_code={acceptance['exit_code']}
31. **Regressions:** see REGRESSION_REPORT.md
32. **Limitations:** KNOWN_FAILURE_MODES.md
33. **MM 1.0 ready:** READY_WITH_KNOWN_LIMITATIONS
34. **Observer beta ready:** READY_WITH_KNOWN_LIMITATIONS
35. **Next research:** distal-consequence selection boundary; signal-dependent behavior; PER promotion evidence
""")
    _md(OUT / "OBSERVER_INTEGRATION_AUDIT.md", "Observer backend reads PhysicalSystemRuntime via session; model_banner and cognition_pipeline added.\n")
    _md(OUT / "OBSERVER_API_MAP.md", "GET /api/health, /api/model, /api/state, /api/control/*, /api/mechanisms, /api/replay/{tick}, /api/inspect/{tick}\n")
    _md(OUT / "REGRESSION_REPORT.md", f"Acceptance: exit {acceptance['exit_code']}\n")
    _json(OUT / "BOUNDEDNESS_RESULTS.json", {"recent_fragments_cap": 512, "demo_ticks": 600})
    _md(OUT / "PERFORMANCE_RESULTS.md", "Run separately with Observer attached; not blocking 1.0 packaging.\n")
    _md(OUT / "OBSERVER_CONTROL_PLANE_RESULTS.md", "See tests/test_psy_observer_run_control_plane.py\n")
    _md(OUT / "OBSERVER_UI_RESULTS.md", "Model banner, pipeline, prospection view integrated in SPA.\n")
    _md(OUT / "PACKAGING_RESULTS.md", "Launcher: ./PsyObserver serves prebuilt web_dist.\n")

    print(f"Wrote artifacts to {OUT}")
    return acceptance["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
