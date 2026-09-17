# Mechanistic Mind 1.0 — Tiktaalik

**Public Beta 1**

Mechanistic Mind is an experimental research runtime for studying whether **mind-like organization** can emerge from explicit, inspectable, low-level mechanisms — without inserting high-level psychological concepts (fear, belief, goal, curiosity, communication, habit) as privileged semantic variables inside the agent.

It does **not** attempt to simulate a mind by naming its parts. It attempts to discover which **minimal mechanisms** are sufficient for mind-like organization to appear under controlled physical history.

The primary public interface is **Psy Observer Web**: a local scientific observation UI for the live Tiktaalik runtime.

| Layer | Identifier |
|-------|------------|
| Model | **MM 1.0 — Tiktaalik** |
| Public release | **Beta 1** |
| Observer | **Psy Observer Web v0.2.0** |
| Python package (`pyproject.toml`) | **0.5.4** (packaging lineage only) |

> Release posture: **READY_WITH_KNOWN_LIMITATIONS**  
> See [`results/mm_1_0_tiktaalik/`](results/mm_1_0_tiktaalik/) and [`RELEASE_NOTES_BETA1.md`](RELEASE_NOTES_BETA1.md).

**License:** [AGPL-3.0-or-later](LICENSE) · [Commercial licensing](COMMERCIAL_LICENSING.md)  
Copyright © 2026 Sergii Derebchynskyi

---

## Table of contents

1. [Why this exists](#why-this-exists)
2. [What “Tiktaalik” means](#what-tiktaalik-means)
3. [Architecture (causal loop)](#architecture-causal-loop)
4. [Psy Observer Web](#psy-observer-web)
5. [What has been demonstrated](#what-has-been-demonstrated)
6. [Instrumental behavior (claim boundary)](#instrumental-behavior-claim-boundary)
7. [Multi-agent world and physical signals](#multi-agent-world-and-physical-signals)
8. [What has not been demonstrated](#what-has-not-been-demonstrated)
9. [Scientific method](#scientific-method)
10. [Quick start](#quick-start)
11. [First experiment (beginner workflow)](#first-experiment-beginner-workflow)
12. [Repository map](#repository-map)
13. [Reproducibility](#reproducibility)
14. [Future research](#future-research)
15. [Known limitations](#known-limitations)
16. [Terminology / claim boundary](#terminology--claim-boundary)
17. [License](#license)

---

## Why this exists

Most “cognitive” simulations start by wiring high-level labels into the agent:

```text
FEAR, BELIEF, GOAL, CURIOSITY, COMMUNICATION, HABIT, …
```

Mechanistic Mind asks a different question:

```text
If we implement only lower-level mechanisms —
physical dynamics, body state, limited observation,
bounded memory, prediction, compression, action selection,
physical interaction, environmental consequence —
what higher-level organization can those mechanisms support?
```

The constitution states this explicitly: agents begin without preset personality, trust, anxiety, preferences, or beliefs about the world; differences should emerge from psyche architecture × body × environment × history ([`docs/MECHANISTIC_MIND_CONSTITUTION.md`](docs/MECHANISTIC_MIND_CONSTITUTION.md)).

Five levels must remain distinct:

```text
WORLD TRUTH          → objective environment
BODY TRUTH           → objective physiology
ACCESSIBLE SIGNALS   → what the organism can actually sense
AGENT MODEL          → what the psyche has stored or inferred
BEHAVIOR             → actions produced by current system state
```

**Observer / experimenter ground truth is not agent knowledge.** Psy Observer may inspect full causal structure; the agent may not.

Mechanistic Mind has **not** solved this research program. Public Beta 1 publishes a reproducible integration stage with explicit claim boundaries.

---

## What “Tiktaalik” means

**Tiktaalik** is the codename for the first named **canonical** Mechanistic Mind integration: one reproducible physical + cognitive runtime with explicit experimental boundaries ([model card](results/mm_1_0_tiktaalik/MM_1_0_TIKTAALIK_MODEL_CARD.md)).

It is intentionally a *transitional* stage:

| Tiktaalik is | Tiktaalik is not |
|--------------|------------------|
| A continuous embodied causal loop (world ↔ body ↔ bounded cognition ↔ action ↔ world) | A human mind simulator |
| An integration of previously staged mechanisms under one runtime | A complete cognitive architecture |
| A research instrument with honest NOT_DEMONSTRATED boundaries | AGI / general intelligence |

The name is a **release codename**, not a biological claim.

---

## Architecture (causal loop)

Canonical runtime: **`PhysicalSystemRuntime`** (`mechanistic_mind/physical_system/`).  
Optional multi-body wrapper: **`TwoAgentRuntime`** (experimental; not the default).

Conceptual loop (terminology follows the runtime, not psychology textbooks):

```text
WORLD  (planet: topology, temperature, flow, resources, fields)
   ↓
PHYSICALLY AVAILABLE INPUT  (body-local sampling; no hidden global oracle for the agent)
   ↓
OBSERVATION  (accessible signals only)
   ↓
BODY + INTERNAL STATE  (morphology, orientation, deformation, work reservoir, internal medium)
   ↓
BOUNDED MEMORY / COMPRESSION  (recent fragments; predictive compression)
   ↓
PREDICTION / PROSPECTIVE STRUCTURE  (multiscale prediction; prospective composition)
   ↓
ACTION SELECTION  (scenario competition over first_action / root-edge support)
   ↓
MOTOR WORK / PHYSICAL CONSEQUENCE  (discrete MOVE / WAIT; work accounting)
   ↓
WORLD CHANGES
   ↺
```

### Important runtime facts

- **Discrete actions** on the Tiktaalik path include at least **MOVE** and **WAIT** (model card). Other action bridges (e.g. selected EMIT) may still be marked bridge-missing in Observer serialization.
- **Work / cost** is physical (finite mechanical work reservoir, deformation work, discrete action work accounting where promoted) — not “motivation.”
- **Cognition**, when enabled, is bounded: predictive compression (4.21), multiscale organization (4.22), prospective trajectory composition (4.23), with scenario competition selecting among supported **first** actions. Distal-consequence-driven present selection is **NOT_DEMONSTRATED**.
- **Experimental** toggles (e.g. physical signal fields) are labeled honestly in the Observer; default Tiktaalik remains one body.

### Ground truth vs agent information

| Available to Psy Observer | Available to the agent |
|---------------------------|------------------------|
| Full planet / body / internal state | Body-local accessible observation |
| Causal events, provenance, MIXED/UNKNOWN | No sender identity in signal perception |
| Experimenter configuration & ablations | No semantic season / “goal” labels injected as truth |

---

## Psy Observer Web

**Public interface:** `mechanistic_mind.ui.psy_observer_web`  
Launchers: `PsyObserver`, `launch_psy_observer.sh`, `.command`, `.bat` / `.cmd`  
Legacy tkinter `psychology_observer` is **not** the Beta 1 product ([`LEGACY.md`](LEGACY.md)).

### Tabs

| Tab | Role |
|-----|------|
| **WORLD** | Shared physical scene, fields, spatial structure |
| **AGENT** | Selected body / agent-facing state and causal “why” chains |
| **MIND** | Bounded cognitive structures (prediction, compression, prospection) |
| **TIMELINE** | Event stream with agent attribution |
| **EXPERIMENT** | Configuration (e.g. agent count, mechanism toggles) |
| **DATA** | Run / pack oriented scientific data views |
| **ANALYZE RESULTS** | Local summaries of saved runs (Analyzer product surface still partially deferred) |
| **OVERVIEW** | Local run catalog |

### Modes and controls

- **Modes:** `LIVE` · `INSPECT` · `REPLAY`
- **Controls:** Play · Pause · Step · Stop · Reset
- **Speed:** 0.25× … 10× and **MAX** (wall-clock observer pacing)

**Speed vs science:** Observer rendering / wall-clock sleep is decoupled from scientific ticks. Regression tests show that the same number of ticks yields the same scientific fingerprint across 1× / 10× / MAX (`tests/test_observer_speed_decoupling.py`). Speeding up the UI does not skip scientific ticks.

Closing a browser tab does **not** stop the experiment. Use **Quit Psy Observer**, Ctrl+C, or `./launch_psy_observer.sh --quit`.

Details: [`PSY_OBSERVER_LAUNCHER.md`](PSY_OBSERVER_LAUNCHER.md).

---

## What has been demonstrated

Statuses below reuse repository vocabulary. They are **not** confidence scores.

| Capability / mechanism | Evidence (examples) | Status | What this does **not** imply |
|------------------------|---------------------|--------|------------------------------|
| Integrated physical world + body loop | Tiktaalik runtime; `results/mm_1_0_tiktaalik/` | **CANONICAL** integration | A living organism; metabolism-as-biology |
| Bounded predictive compression | Research module; knowledge EXP-4.21; promotion | **CANONICAL** / staged evidence | Belief; unlimited memory; “understanding” |
| Multiscale predictive organization | EXP-4.22 lineage; promotion | **CANONICAL** | Semantic hierarchy; labeled “levels of thought” |
| Prospective trajectory composition | EXP-4.23; `mm_prospective_scenario_competition/`, `mm_multistep_action_prospection/` | Composition **ASSERTED** / **DEMONSTRATED** under stated protocols | Planning; goals; distal-driven present choice |
| Deep-future action competition | Model card / architecture audit | **NOT_DEMONSTRATED** | — |
| Scenario competition → first_action bridge | Tiktaalik path | Operational under competition rules | Desire; intention; free-form inventing of MOVE alternatives in every ecology |
| Acquired observability + learned predictive use | EXP-4.25 (C1, C2) | **ASSERTED** (listed seeds) | Curiosity; information-seeking rewards |
| Self-initiated instrumental observation | EXP-4.25 (C3) | **NOT ASSERTED** | — |
| Endogenous motor / body coupling | `mm_endogenous_motor_*` | Causal motion / coupling evidenced; claim boundary forbids agency language | Will; motivation; discrete MOVE policy from coupling alone |
| History-dependent prediction / selection | Prospective / entrenchment packs | Measured under protocols | Habit; personality; helplessness |
| Early experience entrenchment / hysteresis | `mm_early_experience_entrenchment/` | Path-dependent thresholds **DEMONSTRATED**; some framings unresolved | Infinite lock; dedicated WAIT drive as psychology |
| Two-agent shared world + independent cognition | `TwoAgentRuntime`; `mm_two_agent_*` | Physics / inspection **DEMONSTRATED**; wrapper **EXPERIMENTAL** | Social mind; theory of mind |
| Physical signal emit / propagate / perceive | `mm_two_agent_physical_signals/` | Physics **DEMONSTRATED** | Communication; language; intentional messaging |
| Signal-conditioned prediction → behavior change | Same pack | **NOT_DEMONSTRATED** | — |
| Learned two-agent communication | Model card / design boundaries | **NOT_DEMONSTRATED** | — |
| Observer speed invariance (scientific fingerprint) | `tests/test_observer_speed_decoupling.py` | **PASS** in regression | Real-time wall-clock identity of UX |
| Deterministic seeds / reproducible fingerprints | Runtime + tests | Supported where tests/packs assert | Bit-identity across all OS/hardware without caveats |

**Evidence caveat:** Some early EXP-4.21–4.25 *update* result directories are referenced from knowledge provenance but are **not** shipped as full `results/update42*` trees in this public cut. Integration status is carried by Tiktaalik promotion, research modules, knowledge experiment records, and selected `results/mm_*` packs.

---

## Instrumental behavior (claim boundary)

Instrumental behavior is scientifically important because it sits between **passive sensation** and **self-initiated seeking**.

From EXP-4.25 (*Emergent Instrumental Observation*):

| Claim | Status |
|-------|--------|
| **C1** acquired physical observability | **ASSERTED** (seeds 17, 23, 41, 59, 83) |
| **C2** learned predictive use of that observability | **ASSERTED** (same seeds) |
| **C3** self-initiated instrumental interaction | **NOT ASSERTED** |
| Novel mediated prospective composition (related) | **ASSERTED** |

Architecture notes from that lineage: physical transduction only; **no** TOOL / INFORMATION / EPISTEMIC reward channels.

### Components vs full instrumental loop

Present as components (conservative reading):

```text
observation availability  →  predictive use  →  (action bridges vary)
```

**Missing bridge (explicit):** learned prediction → autonomous seeking / conditional action (**C3**). Related Observer/promotion notes also mark some action bridges (e.g. instrumental EMIT bridge) as **BRIDGE_MISSING**.

### Do not collapse into

- “the agent has goals”
- “the agent intentionally investigates”
- “the agent is curious”

Those are **not** established by C1/C2.

---

## Multi-agent world and physical signals

**`TwoAgentRuntime`** (experimental):

- One **shared** physical planet
- Two **independent** `PhysicalSystemRuntime` slots (body / internal / cognition / seeds)
- Agent-specific bodies; optional soft contact / field coupling
- Physical signal fields default **OFF** unless enabled

### Signals (`FIELD_A` / `FIELD_B`)

Documented bridge behavior ([`results/mm_two_agent_physical_signals/FINAL_REPORT.md`](results/mm_two_agent_physical_signals/FINAL_REPORT.md)):

- Deposit, decay, neighbor spread, additive superposition
- Local perception through ordinary observation (`local.FIELD_*`)
- **No** sender identity / internal-state leakage in the signal itself
- Provenance may be **UNKNOWN** or **MIXED**; senders are not guessed

**PHYSICAL SIGNALING ≠ DEMONSTRATED COMMUNICATION.**

Physics emit / propagate / perceive: **yes**.  
Signal-conditioned prediction and selected behavioral change: **not demonstrated**.  
Learned two-agent communication: **NOT_DEMONSTRATED**.

Enable two-agent mode in the Observer **EXPERIMENT** tab (`agent_count: 2`). Inspect agents independently; selection must not invent peer mind state.

---

## What has not been demonstrated

Public Beta 1 does **not** establish:

| Claim | Why current evidence does not justify it |
|-------|------------------------------------------|
| Consciousness / subjective experience / sentience | No measurement protocol; mechanisms are operational only |
| Self-awareness | No self-model claim in Tiktaalik boundaries |
| Beliefs / desires / emotions | High-level variables are deliberately not ontology |
| Semantic understanding / language | No language channel; signals are physical fields |
| Semantic / intentional communication | Explicit **NOT_DEMONSTRATED** |
| Human-like cognition / AGI / general intelligence | Narrow mechanisms under lab protocols |
| Full intentionality / curiosity | C3 instrumental seeking **NOT ASSERTED** |
| Full planning / distal-driven present selection | Composition ≠ planning; deep-future competition **NOT_DEMONSTRATED** |
| Strong endogenous time as psyche faculty | 4.24 lineage preserves temporal NULL claims |
| Autonomous scientific reasoning | Observer/ARCHON roles are for experimenters |

This list increases credibility: it marks where interpretation must stop.

---

## Scientific method

Mechanistic Mind treats “a behavior occurred” as insufficient. Where packs and tests support it, the project uses:

- **Deterministic seeds** and reproducible run fingerprints
- **Controlled protocols** and matched histories
- **Ablations** and broken / shuffled / cached controls (see EXP-4.23 lineage notes)
- **Counterfactual comparison** where designed
- **Bounded stores** (capacity limits are part of the claim)
- **Explicit claim matrices** (ASSERTED / NOT ASSERTED; SUPPORTED / NOT_SUPPORTED; DEMONSTRATED / NOT_DEMONSTRATED)
- **Provenance** and runtime identity in Observer health (`app=Psy Observer`, `model=MM 1.0 — Tiktaalik`)
- **Speed-invariance** tests for scientific tick fingerprints
- Selected **`results/mm_*` evidence packs** for inspection

Causal necessity is only as strong as the specific control/ablation design of each experiment. Do not upgrade a staged ASSERTED component into a system-level psychological faculty.

Principles: [`docs/MECHANISTIC_MIND_CONSTITUTION.md`](docs/MECHANISTIC_MIND_CONSTITUTION.md).

---

## Quick start

### Requirements

- System **Python ≥ 3.11** on `PATH` (used to create the project environment)
- Network on **first** launch (`pip install -r requirements-observer.txt`)
- Production UI already shipped in `mechanistic_mind/ui/psy_observer_web/web_dist/` — **Node/npm not required** for ordinary use

### Public flow

1. Clone or extract this repository  
2. Launch the platform launcher  
3. On first run, the launcher creates `.venv_psy_web`, installs Observer requirements, and writes a readiness marker  
4. Psy Observer Web opens locally (`127.0.0.1`, preferred port **8768**, free-port fallback)

Later launches **reuse** `.venv_psy_web` and do not reinstall unnecessarily.

### Platform launchers

| Platform | How to start | Status |
|----------|--------------|--------|
| **Linux** | `./PsyObserver` or `./launch_psy_observer.sh` | **NATIVE TESTED — PASS** |
| **macOS** | double-click `launch_psy_observer.command` | **NATIVE TESTED — PASS** |
| **Windows** | double-click `launch_psy_observer.bat` (or `.cmd`) | **STATICALLY VERIFIED — NOT YET NATIVELY TESTED** |

macOS Gatekeeper: first open may require **right-click → Open** if the `.command` file is quarantined ([launcher notes](PSY_OBSERVER_LAUNCHER.md)).

### Developer / manual launch (after env exists)

```bash
PYTHONPATH=. .venv_psy_web/bin/python -m mechanistic_mind.ui.psy_observer_web
```

Equivalent entry (delegates to launcher):

```bash
PYTHONPATH=. .venv_psy_web/bin/python -m mechanistic_mind.ui.psy_observer_web.launcher
```

Optional frontend rebuild (developers only):

```bash
cd web/psy-observer && npm install && npm test && npm run build
```

---

## First experiment (beginner workflow)

1. Launch Psy Observer (see above).  
2. Open **EXPERIMENT** and keep the canonical **single-agent** Tiktaalik configuration.  
3. Press **Play** (or **Step**) and watch **WORLD**.  
4. Open **AGENT** and **MIND** to inspect body-local state and bounded cognitive structures.  
5. Use **TIMELINE** for event attribution.  
6. Try **Pause**, change speed (including **MAX**), and **Step** — scientific ticks remain the unit of advancement.  
7. **Stop** / save to create a local run artifact (writes under `results/psychology_observer/psy_observer_web/` on your machine).  
8. Inspect **ANALYZE RESULTS** and **OVERVIEW** for local summaries / catalog.  

Optional: set `agent_count: 2` in **EXPERIMENT** to enter `TwoAgentRuntime`, then switch selected agent (`agent_0` / `agent_1`) without expecting peer-mind fallback.

Do **not** use Legacy Psychology Observer for Beta 1.

---

## Repository map

| Path | Contents |
|------|----------|
| `mechanistic_mind/` | Scientific runtime + Psy Observer Web backend |
| `web/psy-observer/` | Observer frontend source (production build is in `web_dist/`) |
| `experiments/` | Experiment runners / protocols |
| `results/mm_*/` | Selected scientific evidence packs (intentionally versioned) |
| `knowledge/` | Structured research knowledge / claim records |
| `tests/` | Regression and scientific tests |
| `worlds/` | Environment definitions |
| `scripts/` | Bootstrap and tools (incl. first-run env bootstrap) |
| `docs/` | Constitutions, archaeology notes, design docs |
| `configs/` | Configuration assets |

Local Psy Observer run history is **not** shipped as a public catalog; a fresh user starts with an empty personal Overview unless they generate runs locally.

---

## Reproducibility

1. Read the Tiktaalik pack: [`results/mm_1_0_tiktaalik/`](results/mm_1_0_tiktaalik/) (model card, readiness, known failure modes).  
2. Browse related `results/mm_*` packs for mechanism-specific claims.  
3. Prefer listed **seeds** in experiment records when re-running protocols.  
4. Run Observer / signal / two-agent regressions from this tree:

```bash
PYTHONPATH=. .venv_psy_web/bin/python -m pytest \
  tests/test_mm_psy_observer_web_api.py \
  tests/test_psy_observer_*.py \
  tests/test_physical_signal_provenance.py \
  tests/test_observer_signal_mechanism_wiring.py \
  tests/test_two_agent_*.py \
  tests/test_observer_speed_decoupling.py \
  -q
```

Determinism claims apply where tests and packs assert them; treat cross-machine bit-identity as a hypothesis until verified on your platform.

---

## Future research

These are **directions**, not shipped capabilities.

### Scientific roadmap

- Stronger instrumental loops (close C3 / missing action bridges)
- Distal / deep-future competition where currently **NOT_DEMONSTRATED**
- Historical entrenchment and behavioral transition / hysteresis as open science
- Decision under unavoidable state transition
- Compression-regime adaptation; retrospective predictive importance
- Richer persistent ecologies / seasonal or moving resources
- Longer developmental histories
- Multi-agent development and whether **signaling conventions** can emerge (today: physics only)
- Endogenous temporal organization without injecting clocks into cognition
- Integration of still-isolated research stages into the canonical loop

### Observer / tooling roadmap

- Deeper **Analyzer** live integration (today: honest CATALOG_ONLY / NOT AVAILABLE where applicable)
- **COMPARE RUNS**
- **WORLD INTERPRETER**

Beta 2+ UI items are deferred; shipping Beta 1 does not imply new cognition or physics.

---

## Known limitations

- Beta software — APIs and UI may still evolve  
- Research system: computational / storage cost can be nontrivial for long runs  
- Incomplete integration between some staged mechanisms  
- Some experiments remain isolated research stages (knowledge records may point at packs not fully mirrored here)  
- Analyzer product surface not fully integrated  
- COMPARE RUNS not implemented  
- WORLD INTERPRETER deferred  
- Windows launchers not yet natively verified  
- Legacy modules retained for import / reproducibility only ([`LEGACY.md`](LEGACY.md))  
- Interpretation must stay inside claim matrices — do not anthropomorphize operational mechanisms  

---

## Terminology / claim boundary

| We say | We do **not** automatically mean |
|--------|----------------------------------|
| prediction | belief |
| intrinsic / body state transition | emotion |
| acquired preference / selection bias | desire |
| prospective composition | planning |
| physical signaling (`FIELD_*`) | communication |
| history-dependent behavior | habit |
| acquired observability | curiosity |
| endogenous motor activity | intention / will |
| scenario competition | goals |
| agent | person / mind in the ordinary sense |

Anthropomorphic words appear in this README only to mark what the evidence **does not** establish.

---

## License

Mechanistic Mind is available under a dual-licensing model.

### Open-source license

Mechanistic Mind is licensed under the
[GNU Affero General Public License v3.0 or later](LICENSE)
(`AGPL-3.0-or-later`).

You may use, study, modify, distribute, and use Mechanistic Mind
commercially under the terms of the GNU AGPL.

The exact rights and obligations of the open-source licensing path are
defined by the full license text in [LICENSE](LICENSE).

### Alternative commercial license

Organizations or individuals that require licensing terms different
from the AGPL may obtain a separate commercial license from the
copyright holder.

This may be appropriate for proprietary products, services,
integrations, or deployments whose intended licensing model is
incompatible with the applicable AGPL requirements.

Commercial licensing is provided only through a separate written
agreement and may have independently negotiated terms.

See [COMMERCIAL_LICENSING.md](COMMERCIAL_LICENSING.md).

**Copyright © 2026 Sergii Derebchynskyi**

The availability of alternative commercial licensing does not reduce,
replace, or revoke rights already granted under the AGPL.

---

## Screenshots

No publication screenshots are bundled yet. Optional placeholders are listed in [`docs/images/README.md`](docs/images/README.md). Do not commit screenshots that contain private desktop content.

---

## Further reading

- [`LICENSE`](LICENSE)  
- [`COMMERCIAL_LICENSING.md`](COMMERCIAL_LICENSING.md)  
- [`COPYRIGHT`](COPYRIGHT)  
- [`RELEASE_NOTES_BETA1.md`](RELEASE_NOTES_BETA1.md)  
- [`PSY_OBSERVER_LAUNCHER.md`](PSY_OBSERVER_LAUNCHER.md)  
- [`LEGACY.md`](LEGACY.md)  
- [`docs/MECHANISTIC_MIND_CONSTITUTION.md`](docs/MECHANISTIC_MIND_CONSTITUTION.md)  
- [`results/mm_1_0_tiktaalik/MM_1_0_TIKTAALIK_MODEL_CARD.md`](results/mm_1_0_tiktaalik/MM_1_0_TIKTAALIK_MODEL_CARD.md)  
- [`results/mm_two_agent_physical_signals/FINAL_REPORT.md`](results/mm_two_agent_physical_signals/FINAL_REPORT.md)  
