# ACANTHOSTEGA_BETA4_SCIENTIFIC_BEHAVIORAL_VALIDATION_ARCHITECTURE

**Status:** Architecture / preregistration only.  
**Public model:** `ACANTHOSTEGA_BETA4` (frozen).  
**Release-candidate fingerprint:** `e658e1ef405d95388a2a7322196fb93678ec803c73e07ff59ec199b4658075ac`  
**P7 verdict context:** `P7_PASS_WITH_NON_BLOCKING_DEBT`; engineering release blockers = 0; physical habitability ESTABLISHED; scientific behavioral validation NOT_YET_COMPLETE.  
**This seam:** `TOTAL_SIMULATED_TICKS = 0`. No production-code changes. No live-run mutation. No Observer redesign. No UX consolidation. No recalibration.

Companion artifacts live under `results/beta4_scientific_behavioral_validation_architecture/`.

---

## 0. Interpretive law

Absence of an outcome is **not** automatic cognitive failure. Every missing or null finding must be classified along:

physical capability → action availability → action selection → actuation → geometric reach → contact → transmitted work → material failure → detached-object creation → subsequent manipulation → learning/developmental change → chance exploration → Analyzer/capture failure.

---

## 1. Pre-validation requirements (Phase 1)

P7 `REQUIRED_BEFORE_SCIENTIFIC_VALIDATION_COUNT = 2` from `results/beta4_release_equivalence_and_performance_gate_v1/DEBT_REGISTER.md`:

1. Scientific behavioral validation architecture and execution (next seam).
2. Policy-level confirmation of intended habitat behaviors (MOVE/WAIT, grasp/carry, terrain work) under frozen physics.

Full classification: `PRE_VALIDATION_REQUIREMENTS.md`.

**Verdict on the count:** After this package, the count is **stale as an execution gate**. Item 1’s architecture half is satisfied here; its execution half *is* S1–S6. Item 2 is a **validation objective** (H2/H5–H8), not a prerequisite to start pilot/primary. `RELEASE_CANDIDATE_MUST_CHANGE = false`.

---

## 2. Scientific claim boundary (Phase 2)

See `CLAIM_BOUNDARY.md`.

**May establish (operational):** embodied stability; meaningful locomotion (MOVE→displacement); physical vision/hearing at organism boundaries; motor→body causality; world contact when geometry/work allow; reachable material-interaction stages; experience-linked distribution change; PSC intervention effects vs matched OFF; ablation differences.

**Requires extra evidence:** autonomous terrain manipulation; learned effector-Z skill; purposeful excavation; communication; object-use chains; adaptive multimodal integration.

**Forbidden:** consciousness; intention without ops evidence; understanding; desire/motivation; fitness; biological realism; human-like senses; language; “planning” merely because PSC is enabled; Observer pixels/playback as agent evidence.

**Autonomous excavation is not a required pass criterion for Beta4 scientific closure.**

---

## 3. Validation domains (Phase 3)

### V1 — Physical stability and embodiment
Finite state; support/free-space transitions; landing; locomotion kinematics; rest; contacts; numerical stability; conservation; IDs; spatial consistency.

### V2 — Physical sensory causality
**Vision:** O3 source→surface→O4 receptor; nonzero/zero/missing; occlusion; O5 timing; FPV only as researcher view unless exact O4 numerics analyzed.  
**Hearing:** physical emission→LPS→A3/A5; transport delay; silence≠missing; O5 timing.  
Observer pixels / audio playback are **not** agent evidence.

### V3 — Motor utilization
MOVE/WAIT; LEFT/RIGHT Z availability and selection; nonzero actuation; displacement; contact; PUSH/GRASP/RELEASE; OSC controls; action entropy/motifs; state/action dependence.

### V4 — Terrain interaction causal ladder
Classify every attempt: control unavailable → not selected → selected not actuated → actuated no displacement → displaced no reach → contact insufficient work → material failure → detached object → later grasp/carry/combine/deposit.  
**No excavation claim from terrain deltas alone.**

### V5 — Development and PSC
Canonical Beta4 cognition (static inspection of `acanthostega_beta4_config()` + `CognitionConfig`):

| Field | Shipped value |
|-------|----------------|
| `prospective_selection` | `SCENARIO_COMPETITION` |
| `persistent_prospective_control` | `False` |
| `psc_off_ticks` | absent → MANUAL (`None`) |
| `psc_motor_resolution` | `LOCO_FACTORIZED` |
| `sensorimotor_consequence_model` | `True` |
| `sensorimotor_consequence_withhold_from_psc` | `True` |
| `historical_sensorimotor_selection_bridge` | `False` |

- **Early-life duration (preregistered):** ticks `[0, PSC_ENABLE_TICK)`.
- **`PSC_ENABLE_TICK = 1000`:** engineering value justified by mechanism-registry experimental starting point (~1000), FIRST_HABITABLE 400-tick underpower for locomotion/history, and prior developmental Phase-A precedents — not “sounds nice” alone.
- **Auto-enable authority:** `cognition.psc_off_ticks` + `Runtime._maybe_auto_enable_psc` — **experiment protocol / Observer control**, not immutable model anatomy. Registry “~1000” is guidance, not hard-coded anatomy.
- **Manual vs scheduled:** both must emit receipts (`set_psc_off_ticks` / `PSC_ACTIVATION` event with `history_preserved=True`).
- **`OBSERVED_COMPOSITE`:** experimental motor-resolution mode; **not** canonical for primary validation.
- **Histories PSC may consume:** SMC rows only when withhold opened; not HSS bridge by default (bridge remains OFF unless labelled factor).
- **Matched PSC-OFF control:** `prospective_selection=LEGACY_FIRST` throughout (or twin of scheduled condition) — labelled `MODIFIED EXPERIMENT` relative to shipped competition default.

Intended developmental policy for validation conditions C2: early LEGACY_FIRST (or equivalent OFF operationalization) while SMC accumulates → enable competition and open withhold at tick 1000 without reset.

### V6 — Learning/change evidence
Separate: time-dependent exposure; random drift; environmental differences; motor availability; PSC intervention; genuine history-dependent change. Use matched seeds and counterfactual continuations only where architecture supports them without leakage.

### V7 — Two-agent interaction
Shared-world encounters; physical contacts; acoustic emissions/receptions; relative positions; action changes after legitimate sensory exposure; individual trace isolation. Do not call OSC “communication” without matched causal controls (H10).

---

## 4–12. Registries (detail in results/)

| Phase | Artifact |
|-------|----------|
| 4 Hypotheses H1–H10 | `HYPOTHESIS_REGISTRY.md` |
| 5 Conditions C0–C8 | `EXPERIMENTAL_CONDITIONS.md` |
| 6 Seeds/power | `SEED_AND_POWER_PLAN.md` |
| 7–8 Metrics + controls | `METRICS_AND_CAUSAL_CONTROLS.md` |
| 9 Failure taxonomy | `FAILURE_AND_INCONCLUSIVE_TAXONOMY.md` |
| 10–12 Analyzer + S0–S7 | `EXECUTION_PLAN.md` |

### Pilot / primary budget (summary)

| | Seeds | Ticks/seed |
|--|------:|----------:|
| Pilot | 4 | 1200 |
| Primary | 10 | 2000 (expand to 3000 under preregistered rule) |
| Max program ticks | | 80 000 |

Replication unit: **seed/run**. Opportunity-normalized metrics. Temporal autocorrelation accounted (no i.i.d. tick tests). Underpowered → `INCONCLUSIVE_UNDERPOWERED`, not FAIL.

### Execution order

S0 (requirements — this seam) → S1 preflight → S2 pilot → S3 power review (no post-hoc hypothesis rewrite) → S4 primary → S5 Analyzer → S6 scientific closure → **S7 Observer Product UX Consolidation only after S6**.

---

## Architecture verdict

**`B. READY_TO_EXECUTE_NOW_REQUIREMENT_COUNT_STALE`**

Both P7 “required” items are identified. Neither is a true blocker to starting S1 after this preregistration. Item 2 is in-protocol. Fingerprint unchanged. Validation not yet executed (`TOTAL_SIMULATED_TICKS = 0`).

**Recommended next slice:** S1 zero/short-tick configuration and evidence preflight (still no long ordinary validation run until pilot S2).
