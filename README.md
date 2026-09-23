# Mechanistic Mind 1.0 — Tiktaalik (Public Beta 3)

**Mechanistic Mind** is an experimental artificial-life / mechanistic simulation
environment. Observed behavioral structure should be treated as experimental
evidence requiring controlled comparison and ablation, not as evidence of
human-like cognition or subjective experience.

Do **not** treat observed behavior as proof of consciousness, intention,
recognition, communication, learning, or goal-directed seeking.

| Identity | Value |
|----------|-------|
| Model | Mechanistic Mind 1.0 — Tiktaalik |
| Release | Public Beta 3 |
| Public Observer | Psy Observer Web |
| Runtime | TwoAgentRuntime (recommended first run) |

Beta 3 includes: two-agent runtime, articulated body/head, physical near-field
vision, physical signaling, heterogeneous terrain / site mechanics, predictive
mechanisms (compression / equivalence / relevance), temporal prediction /
prospection, prospective composition, PSC, Scientific V3, Analyzer Next
(bounded-memory), Psy Observer, Save & Stop / restore, and multi-agent
behavioral reconstruction.

See `RELEASE_NOTES_BETA3.md` and `KNOWN_LIMITATIONS.md`.

---

## RECOMMENDED FIRST RUN

This is the recommended Beta 3 **baseline workflow**. Tick 1000 is a practical
experimental checkpoint, **not** a biologically privileged boundary.

1. **Apply** the Observer preset **MM 1.0 — Tiktaalik Public Beta 3**
   (**Apply & Reset World**) **before Play**. The public preset must be Applied
   to obtain the recommended **TwoAgentRuntime**. Starting Play on the default
   session without Apply still uses a single-agent runtime.
2. All normal Beta 3 mechanisms should initially be **ENABLED** except:
   - **Prospective Scenario Competition (PSC)** — **OFF**
   - **Climate Control** — **OFF**
3. **BEFORE pressing Play**, go to:

   **Experiment → Predictive → OBSERVED_COMPOSITE**

   `OBSERVED_COMPOSITE` must be selected **before Play even though PSC itself
   begins disabled**. Do not silently substitute `LEGACY_FIRST`, locomotion-only,
   `SHADOW`, or another mode.
4. Start the simulation with PSC **OFF**.
5. Allow the Tiktaaliks approximately **1000 simulation ticks** of initial
   history with PSC disabled.
6. At approximately tick 1000, **enable PSC** without resetting history,
   cognition, or body. Continue the same biography.
7. Climate Control remains **OFF** for this baseline unless you intentionally
   want a climate intervention experiment.

**Why PSC begins OFF:** the recommended run first allows a history of physical /
sensorimotor consequences to accumulate before prospective scenario competition
is enabled.

**Why OBSERVED_COMPOSITE is selected before Play:** so that when PSC is later
enabled, the intended Beta 3 motor-resolution regime is already configured and
the biography is not interrupted merely to change that setting.

**Do not reset** history / cognition / body when enabling PSC in this workflow.

Exact UI path:

```
Experiment → Predictive → OBSERVED_COMPOSITE
```

---

## Quick start

Unpack the archive, then launch Psy Observer. You do not need a port number or
the Python module name for normal use.

| Platform | Launcher | This packaging environment |
|----------|----------|----------------------------|
| **Linux** | `./launch_psy_observer.sh` or `./PsyObserver` | **TESTED** (bootstrap + Observer) |
| **macOS** | double-click `launch_psy_observer.command` | **STATICALLY AUDITED** (not executed here) |
| **Windows** | double-click `launch_psy_observer.bat` or `.cmd` | **STATICALLY AUDITED** (not executed here) |

Requirements:

- System Python **≥ 3.11** on PATH (used to create `.venv_psy_web` on first launch)
- Network on **first** launch (`pip install -r requirements-observer.txt`)
- Production UI is already in `mechanistic_mind/ui/psy_observer_web/web_dist/`
  (Node/npm is **not** required for normal use)

First launch may take a few minutes while `.venv_psy_web` is created.

Later launches reuse that environment.

The launcher binds **127.0.0.1** and prefers port **8768**, falling back to a
free port if 8768 is occupied. It opens a local browser when ready. Closing the
browser does **not** stop a running experiment.

Stop with **Quit** in the small ownership window, Ctrl+C in the launcher
terminal, or `./launch_psy_observer.sh --quit`.

On macOS, first open may need **right-click → Open** if Gatekeeper quarantines
the `.command` file. Homebrew is not required.

On Windows, WSL is not required. If Python is missing, the window stays open
with an error.

Manual equivalent after the environment exists:

```bash
PYTHONPATH=. .venv_psy_web/bin/python -m mechanistic_mind.ui.psy_observer_web
```

Rebuild the UI only if you change frontend sources:

```bash
cd web/psy-observer && npm install && npm test && npm run build
```

### New-user path

unpack → launch → bootstrap if required → Psy Observer opens → create/start
experiment (Public Beta 3 preset) → verify Experiment → Predictive →
OBSERVED_COMPOSITE → Play → Pause → Analyze Current → Save & Stop →
reopen/restore a saved run.

Results are written under **project-relative**
`results/psychology_observer/psy_observer_web/` (the package root, not the
caller's working directory). Saved runs are `psyweb-*` directories. Live
staging uses `.live-*` until a successful Save & Stop.

---

## Observer workflow

**Transport:** Play / Pause / Step / Stop / Reset.

**Execution (wall-clock only; scientific `dt` unchanged):** REALTIME (LIVE) /
FAST / MAX / HEADLESS.

**Observer detail:** MINIMAL / NORMAL / FULL — how much the human UI captures,
not agent memory.

**Evidence:** FULL SCI writes Scientific V3 JSONL. Compact evidence modes reduce
what is stored; they do not change physics.

**Experiment:** seed, map size, ecology preset, two-agent, mechanisms, Apply &
Reset World vs Apply Live.

**Predictive / PSC:** Experiment → Predictive. PSC enable/disable is a live
mechanism toggle. Motor resolution is `LOCO_FACTORIZED` or `OBSERVED_COMPOSITE`.

**FOV / vision overlays:** Observer visualization of optical exposure. Not
equivalent to agent-accessible observation.

**Analyze Current:** paused reconstruction of recorded Scientific V3 into
TickStories / Behavioral Reconstruction. HTTP stays compact.

**Save & Stop:** asynchronous snapshot publish. Failure should leave live state
retryable.

**Restore:** reopen a saved `psyweb-*` run and continue ticks from the published
snapshot.

### Four layers (do not collapse them)

| Layer | What it is |
|-------|------------|
| Simulation state | Bodies, world, cognition stores at a tick |
| Scientific evidence | Recorded receipts (O→D→M→C, pose, signals, contacts) |
| Observer visualization | Human overlays, FOV, terrain paint |
| Analyzer-derived reconstruction | TickStories, episodes, derived metrics |

Observer overlays are not agent-accessible merely because humans can see them.

---

## Scientific evidence / Analyzer

Scientific V3 core chain:

**Observation → Decision → Motor → Consequence**

Analyzer Next reconstructs TickStories and behavioral episodes from recorded
evidence. FULL coverage requires successful consumption of that history, not
metadata that rows exist.

**Observed / recorded:** physical observations, DecisionReceipts, MotorReceipts,
ConsequenceReceipts, pose/geometry where recorded, signals, visual exposure,
contacts.

**Derived (explicitly labeled):** approach / withdrawal candidates, geometric
relationships, motor reversals, sensorimotor trend-reversal candidates, other
derived metrics.

**Not established merely by observation:** recognition, communication,
intention, wanting, deliberate navigation, learning.

Physical signaling is not automatically communication.
Distance reduction is not automatically seeking.
Terrain-assisted displacement is not automatically intentional terrain use.

---

## Configuration note

Low-level `CognitionConfig` still defaults `psc_motor_resolution` to
`LOCO_FACTORIZED` (legacy scripts). Fresh Observer experiments using the
**Public Beta 3 recommended preset** set two-agent mode and
`OBSERVED_COMPOSITE`, with PSC and Climate Control off. README and that preset
must agree; applying a custom experiment without the preset does **not**
silently migrate motor resolution.

Default session Play without Apply still constructs a single-agent runtime.
Use Apply & Reset World with the Public Beta 3 preset for the recommended
two-agent first run.

---

## Tests (developers)

```bash
PYTHONPATH=. python3 -m pytest tests/test_analyze_current_paused_v3.py \
  tests/test_save_stop_enospc_retry.py \
  tests/test_beta3_recommended_public_preset.py \
  tests/test_p0_cognition_indexes.py \
  tests/test_psy_observer_save_stop.py -q
```

GIT_PUSH is not part of this release process.
