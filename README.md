# Mechanistic Mind 1.0 — Tiktaalik

**Public Beta 1**

**Mechanistic Mind** is a research runtime for studying embodied, physically grounded agents with explicit, inspectable mechanisms — not a claim of consciousness or AGI.

**Tiktaalik** is the **MM 1.0** model cut: a canonical physical world/body/work stack plus bounded predictive cognition. The primary public interface is **Psy Observer Web**.

| Identity | Value |
|----------|-------|
| Model | Mechanistic Mind 1.0 — Tiktaalik |
| Release | Beta 1 |
| Public Observer | Psy Observer Web (`mechanistic_mind.ui.psy_observer_web`) |
| Observer component version | v0.2.0 |

---

## What can the current model do?

**Canonical (default-on physical gears)** include distributed morphology, orientation, deformation, deformation work, complementary environmental resources, mechanical work reservoir, endogenous motor drive, and a separate discrete action channel — with explicit accounting where promoted.

**Cognition** (when enabled) provides bounded prediction, compression, prospective scenario competition, and action bridging into physics — without inventing belief, desire, language, or communication.

**Experimental** mechanisms (toggleable) include e.g. physical signal fields for multi-agent coupling. Signals are **physical field deposits**, not messages.

---

## Psy Observer Web

Local scientific observation UI for the live runtime:

**Tabs:** WORLD · AGENT · MIND · TIMELINE · EXPERIMENT · DATA · ANALYZE RESULTS · OVERVIEW  

**Modes:** LIVE · INSPECT · REPLAY  

Use it to inspect causal chains, mind state, timeline attribution, configure experiments, save runs, and browse Analyze Results / Overview.

---

## Quick Start

### Public flow (Beta 1)

1. Download and extract the archive  
2. Double-click the launcher for your OS  
3. On **first launch**, the launcher creates `.venv_psy_web` and installs `requirements-observer.txt` (progress is shown; may take a few minutes and needs network once)  
4. Psy Observer Web opens  

Later launches reuse `.venv_psy_web` and do **not** reinstall dependencies unless that environment is missing or incomplete.

### Requirements

- System Python **≥ 3.11** available on PATH (used only to create the project environment)
- Network access on **first** launch (pip install from `requirements-observer.txt`)
- Production UI assets are already in `mechanistic_mind/ui/psy_observer_web/web_dist/` (Node/npm **not** required for normal use)

If Python ≥ 3.11 is missing, the launcher exits with a clear message and a link to https://www.python.org/downloads/

### Launch (platform launchers)

| Platform | File | Verification |
|----------|------|----------------|
| **Linux** | `./launch_psy_observer.sh` or `./PsyObserver` | **NATIVE TESTED — PASS** (incl. first-run bootstrap) |
| **macOS** | double-click `launch_psy_observer.command` | **NATIVE TESTED — PASS** (incl. first-run bootstrap) |
| **Windows** | double-click `launch_psy_observer.bat` (or `.cmd`) | **STATICALLY VERIFIED — NOT YET NATIVELY TESTED** |

Launchers resolve the project root from their own location (cwd-independent; paths with spaces OK), bootstrap `.venv_psy_web` when needed, require `web_dist`, open the browser, and bind `127.0.0.1` with preferred port **8768** (free-port fallback).

Manual / developer equivalent (after the environment exists):

```bash
PYTHONPATH=. .venv_psy_web/bin/python -m mechanistic_mind.ui.psy_observer_web
```

Optional SPA rebuild after frontend changes:

```bash
cd web/psy-observer && npm install && npm test && npm run build
```

Stop with Quit in the ownership window, Ctrl+C, or `./launch_psy_observer.sh --quit`.

Details: `PSY_OBSERVER_LAUNCHER.md`.

**Do not use** Legacy Psychology Observer / tkinter Observer for Beta 1.

---

## Canonical vs experimental

- **Canonical** — promoted integrated gears used by default Tiktaalik runs.
- **Experimental** — optional toggles (e.g. `experimental_physical_signal`); honest labels in Observer.
- **Not yet integrated / deferred** — COMPARE RUNS, full Analyzer, WORLD INTERPRETER (Beta 2+).

Two-agent mode: set `agent_count: 2` in EXPERIMENT (uses `TwoAgentRuntime`). Signal forensics preserve UNKNOWN/MIXED attribution; senders are never guessed.

---

## Scientific claim boundary

This release demonstrates **operational mechanisms** (physics, accounting, prediction, selection bridges, observation). It does **not** claim consciousness, understanding, emotion, intentional communication, or general intelligence.

See also: `docs/MECHANISTIC_MIND_CONSTITUTION.md`, `results/mm_1_0_tiktaalik/`.

---

## Results / saving runs

Save & Stop writes under:

`results/psychology_observer/psy_observer_web/`

Packs and gearbox artifacts under `results/mm_*` are scientific documentation for the Observer DATA views.

---

## Tests

```bash
PYTHONPATH=. python -m pytest \
  tests/test_mm_psy_observer_web_api.py \
  tests/test_psy_observer_*.py \
  tests/test_physical_signal_provenance.py \
  tests/test_observer_signal_mechanism_wiring.py \
  tests/test_two_agent_*.py \
  tests/test_observer_speed_decoupling.py \
  -q
```

Frontend:

```bash
cd web/psy-observer && npm test && npm run build
```

---

## Known limitations (Beta 1)

- Beta software — APIs and UI may still evolve.
- Analyzer not fully integrated (honest CATALOG_ONLY / NOT AVAILABLE where applicable).
- COMPARE RUNS deferred.
- WORLD INTERPRETER deferred.
- Some mechanisms remain EXPERIMENTAL.
- Windows launchers are statically verified; not yet natively tested on Windows.
- Legacy tkinter Observer is **not** the Beta 1 public interface (kept only where shared imports require it).
- Scientific interpretation stays deliberately conservative.

---

## Future work

Beta 2 candidates (not in this release): COMPARE RUNS, deeper Analyzer integration, WORLD INTERPRETER. No new cognition/physics is implied by shipping Beta 1.

---

## License

**LICENSE: NOT DEFINED** — publication decision for the owner before public GitHub push.

---

## Version scheme

| Layer | Identifier |
|-------|------------|
| Model | MM 1.0 — Tiktaalik |
| Release | Beta 1 |
| Python package (`pyproject.toml`) | 0.5.4 (packaging lineage) |
| Psy Observer Web | 0.2.0 |

Health endpoint reports `app=Psy Observer` and `model=MM 1.0 — Tiktaalik`.
