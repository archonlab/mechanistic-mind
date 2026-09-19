# Mechanistic Mind

**Tiktaalik: Undercover — Public Beta 1**

Mechanistic Mind is an experimental simulation and research environment for studying how organized behavior can arise from coupling between a physical world, a body, local sensing, internal physical state, bounded memory, prediction, prospective composition, and action selection.

The project deliberately avoids hard-coding semantic psychological labels such as goals, beliefs, curiosity, fear, friendship, or communication into the agents. Agents are exposed to physical state. Higher-level patterns — if any — are tested through observation, intervention, and ablation rather than assumed by construction.

This release does **not** claim that semantic concepts, language, social cognition, or consciousness have emerged.

---

## Tiktaalik

**Tiktaalik** is the nickname for the simulated embodied agent lineage used in this release.

A Tiktaalik has:

- a physical body in a shared world
- internal physical state
- local sensory access
- movement and contact dynamics
- bounded predictive memory
- prospective / scenario-composition mechanisms
- interaction with environmental objects and resources
- physical near-field vision
- exposure to physical signal fields where enabled

**Observer knowledge is not agent knowledge.** The Observer UI can display ground-truth information that cognition cannot access. That separation is fundamental: what you see in the interface is not automatically what the agent “knows.”

---

## What is “Undercover”?

**Undercover** lets the experimenter enter the same physical world as another body, instead of writing into an agent’s cognition.

The Undercover participant follows ordinary world/body interaction rules. It can physically:

- move
- become optically visible to other bodies
- make contact
- perturb fields / environment where the runtime supports it

It must **not** inject semantic information into another agent’s cognition.

This is useful for physical interaction experiments while preserving the boundary between experimenter knowledge and agent-accessible information.

Undercover is **not** automatically teaching, imitation, or social learning unless a specific experiment establishes those claims.

---

## Physical Vision

Public Beta 1 includes physical near-field vision with LIVE candidate radii:

| Radius | Max Moore candidates |
|--------|----------------------|
| **R=1** (default) | 8 |
| **R=2** | 24 |
| **R=3** | 48 |

Vision uses body orientation, field of view (FOV), distance, illumination, environmental optical structure, and foreign-body optical response. Changing R=1 / R=2 / R=3 is LIVE: it does not reset the world, body, cognition, or history. There is no R=4 in this Beta.

Agent cognition receives only anonymous channels:

- `exo_0`
- `exo_1`
- `exo_2`

These are not object identities. Example:

> The Observer may know that another body produced an optical contribution.  
> The agent receives only the resulting local sensory values.

Optical exposure is **not** recognition.

---

## Physical Signals

`FIELD_A` / `FIELD_B` are physical fields.

- Emission does **not** imply intentional communication.
- Reception does **not** imply interpretation.
- Shared field dynamics do **not** prove a language.

**Signal Forensics** investigates physical emission/reception structure and possible context-dependent relationships without assuming meaning.

---

## Analyzer and Scientific Evidence

The Analyzer inspects scientific evidence for a run, including:

- trajectories and action occupancy
- resources / body state
- structured cognition events
- physical interactions and contacts
- signals
- visual / optical exposure
- configuration interventions
- causal provenance where available

Evidence statements are tagged, for example:

- `OBSERVED`
- `DERIVED`
- `CAUSALLY_LINKED`
- `TEMPORALLY_ASSOCIATED`
- `NOT_AVAILABLE`

Important distinctions:

- temporal association ≠ causation  
- visual exposure ≠ recognition  
- physical signal ≠ message  

**Analyze Current** takes a snapshot using the current run’s scientific history when available. If historical evidence is unavailable, historical Visual Forensics metrics are reported as `NOT_AVAILABLE` rather than false zeros.

---

## Observer

**Psychology Observer** (Psy Observer) is the local research UI. It separates:

1. **World / ground truth** — what actually happened in the simulation  
2. **Physical sensor / transduction** — what the sensing pipeline produced  
3. **Agent-accessible state** — what cognition can receive  
4. **Analyzer inference** — post-hoc research interpretation  

Typical tools (not an exhaustive catalog):

- world map and body state
- cognition / mind views
- Sensors → Vision (including Vision Inspector and R1/R2/R3)
- signals and Signal Forensics
- Analyzer / Analyze Results / Visual Forensics
- interventions and world status

Closing the browser does not always stop the backend — use the launcher window or Stop controls.

---

## Getting Started

### Requirements

- **Python 3.11+** on `PATH`
- Network on **first launch** (dependencies install into a local `.venv_psy_web`)
- No Node.js required to run (the UI ships as a prebuilt `web_dist`)

Entry points at the package root:

| File | Platform |
|------|----------|
| `./launch_psy_observer.sh` or `./PsyObserver` | Linux |
| `launch_psy_observer.command` | macOS |
| `launch_psy_observer.bat` / `launch_psy_observer.cmd` | Windows |

First launch may run `scripts/bootstrap_psy_observer_env.py` and install `requirements-observer.txt`. Prefer the URL printed by the launcher (typically `http://127.0.0.1:8768`).

### Linux

1. Extract the release archive  
2. Run `./launch_psy_observer.sh` (or `./PsyObserver`)  
3. Complete first-run bootstrap if prompted  
4. Open the local Observer URL  

### macOS

1. Extract the archive  
2. If needed: `chmod +x launch_psy_observer.command`  
3. Double-click `launch_psy_observer.command`  
4. Allow Terminal / Python prompts if Gatekeeper asks  

Native macOS execution is supported by the launcher; full Gatekeeper edge-cases may still appear on some systems.

### Windows

1. Extract the archive  
2. Double-click `launch_psy_observer.bat`  
3. First run creates `.venv_psy_web` and installs dependencies  
4. Open the local Observer URL  

Ensure Python 3.11+ is installed with “Add to PATH” enabled.

---

## Quick Start

1. Launch Psychology Observer.  
2. In Experiment controls, enable **Two-agent runtime** if it is not already on, then **Start**.  
3. Open **Sensors → Vision**.  
4. Enable physical near-field vision if the selected preset does not already enable it.  
5. Try **R=1 / R=2 / R=3**.  
6. Let the simulation run.  
7. Click **Open Vision Inspector** for optical candidates.  
8. Open the **Analyze** tool / Analyze Results panel.  
9. Click **Analyze Current**.  
10. Compare physical exposure, actions, contacts, and signals — without assuming recognition or communication.

11. > [!IMPORTANT]
> ### Recommended setup order
>
> When creating a new experiment, configure it in this order:
>
> **1. Select/configure the agents → 2. Select/configure the world → 3. Adjust the remaining settings**
>
> Applying the world configuration also applies the currently selected agent configuration.  
> Therefore, choose your agents **before** pressing **Apply** in the world settings.
>
> Changing the order may result in a different agent configuration being applied than intended.

---

## Scientific Boundaries

This Public Beta does **not** by itself establish:

- consciousness or sentience  
- human-like cognition  
- language or communication  
- recognition or intention  
- social learning  

Mechanistic Mind studies mechanisms and measurable relationships. Claims should stay within what the evidence supports. See also `SCIENTIFIC_BOUNDARIES.md`.

---

## Current Status

**Mechanistic Mind 2.0 — Tiktaalik: Undercover — Public Beta 1**

Experimental research software. Rough edges are expected.

When reporting bugs, include:

- OS  
- Python version  
- seed  
- preset / configuration  
- tick  
- relevant Analyzer output or log (`.psy_observer/launcher.log` when useful)

---

## Repository / Data Notes

Long runs can generate substantial scientific telemetry under `results/` (and related Observer paths). That growth is intentional history retention.

Do **not** commit large generated run datasets, virtualenvs, or local Observer state. Local-only directories typically include:

- `.venv_psy_web/` — first-run Python environment  
- `.psy_observer/` — launcher state / logs  
- `results/` — saved runs and scientific timelines  

---

## License

This project is licensed under the **GNU Affero General Public License v3.0** (AGPL-3.0). See [`LICENSE`](LICENSE).

Commercial licensing terms, if applicable, are described in `COMMERCIAL_LICENSING.md`.

---

**Mechanistic Mind** · Tiktaalik: Undercover · Public Beta 1
