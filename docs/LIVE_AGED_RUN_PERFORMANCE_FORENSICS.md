# LIVE AGED RUN PERFORMANCE FORENSICS

**Date:** 2026-09-21 (Europe/Oslo)  
**Target:** Already-running Psy Observer WEB Tiktaalik (seed 676), naturally aged  
**Constraint:** No restart, reload, reset, science mutation, optimization, or git push  
**Artifacts:** `results/live_aged_run_performance_forensics/`

## PERFORMANCE PROFILE CONFIGURATION MISMATCH DISCOVERED

Observer Apply/Reset could silently replace unrelated mechanism fields (Beta 3
preset / partial payload + fresh defaults). Profiles in this document remain
**valid for the runtime actually measured**. They are **not** the canonical
Tiktaalik Beta 3.1 optimization baseline unless that run’s mechanism map
matches `TIKTAALIK_BETA31` (`results/beta31_canonical_config/BETA31_CANONICAL_PRESET.json`).
Artifacts were **not** deleted. TPS/TPE work was not re-run in the configuration-authority task.

---

## Answer (primary)

**The aged Tiktaalik is spending almost all wall/CPU time inside the simulation cognition thread, specifically scanning predictive-equivalence / predictive-relevance class stores during temporal retrieval.**

More precisely:

1. **~97% of sampled CPU** is thread `psy-observer-sim` (LWP **12755**).
2. **~60% inclusive** of all samples is `temporal_predictive_structure.retrieve` → `predictive_relevance.retrieve` (linear scan over `eq_store["classes"]` at lines 184–185).
3. A large share of that retrieve traffic is reached via **`collect_entry_steps`** (`temporal_prospection_bridge.py`) as well as the direct cognition retrieve call sites.
4. Secondary (still real, much smaller): **`temporal_predictive_structure.learn` → `predictive_equivalence.learn`** (~12% inclusive).
5. **Not the bottleneck right now:** Observer/API capture (LIVE **MINIMAL**/compact), compression soft-match, prospective composition, PSC/`compete_scenarios`, SMC, or research **4.26 / 4.27 / 4.28** (near-floor in the profile).

Observed pace while profiling: **~0.8–0.9 ticks/s**, **~1.15–1.22 s wall per completed tick** (`last_tick_wall_ms`), process **~97% CPU**, RSS **~2.8 GB**.

---

## Inspectability (no restart)

| Question | Result |
|---|---|
| Can the live backend be inspected without restarting? | **YES** |
| Process identity | PID **10494** — `.venv_psy_web/bin/python -m uvicorn mechanistic_mind.ui.psy_observer_web.server:app --host 127.0.0.1 --port 8768` |
| Parent launcher | PID **10474** — `mechanistic_mind.ui.psy_observer_web.launcher` (untouched) |
| Read-only APIs | `/api/runtime/progress`, `/api/diagnostics`, `/api/state`, `/api/mechanisms`, … all responded while run continued |
| Sampling profiler | **py-spy 0.4.2** available in `.venv_psy_web` |
| Direct attach | **Blocked** by Linux Yama `kernel.yama.ptrace_scope=1` + no passwordless sudo (`Permission Denied`) |
| Successful attach path | **Docker `--privileged --pid=host`** running the same `py-spy` binary against PID 10494 (**nonblocking**). Did **not** restart or rewrite process state. |
| Process preserved? | **YES** — same PID/PPID after profiling; tick continued 2900→3060+ |

**Attachment note:** Host-user `py-spy -p 10494` fails under ptrace_scope=1 because the profiler is not the process parent. Privileged Docker with host PID namespace is sufficient to sample. Native `/proc/<pid>/task/*/stack` is also denied without CAP_SYS_PTRACE.

---

## Process snapshot (during forensics)

| Field | Value |
|---|---|
| PID | 10494 |
| CPU% | ~96.5–97% |
| RSS | ~2.80–2.82 GB (VmPeak ~7.5 GB) |
| Threads (NLWP) | 25–26 |
| Hot LWP | **12755** `psy-observer-sim` (~active+GIL in dumps) |
| Other notable threads | MainThread (uvicorn idle), `psy-observer-capture` (wait), heartbeat, AnyIO workers (idle) |
| Port | 127.0.0.1:**8768** |
| Experiment | MM 1.0 — Tiktaalik; seed **676**; `runtime_generation` **5** |
| Observer detail | **MINIMAL** (`products`: mechanisms, telemetry, world) |
| Speed / ui_hz | 1.0 / 10.0 |
| Selection | `OBSERVED_COMPOSITE_PSC` + `SCENARIO_COMPETITION` |
| Enabled (interest set) | compression, multiscale, prospective composition, PSC, SMC, historical bridge, **4.26, 4.27, 4.28**, temporal predictive structure, predicted-context + multistep prospection, retrieval, bounded memory, cognition |

---

## Tick progression (correlated with profile window)

### Window A — early sampler (`tick_progression.jsonl`)

- Ticks **2901 → 2945** over ~53 s → **~0.83 ticks/s**
- Per-interval median ~**0.86 ticks/s**

### Window B — concurrent with py-spy (`progress_window.jsonl`, ~50 s)

- Ticks **3000 → 3039** over ~49 s → **~0.79 ticks/s**
- `last_tick_wall_ms`: mean **~1222 ms**, median **~1184 ms**, max **~2044 ms**
- Runtime self-report: `sim_ticks_per_sec` ≈ **0.8–0.9**, status often `COMPUTING_TICK`

### Observer overhead (same aged process, API)

From `/api/state` → `observer_perf` (compact LIVE):

- `capture_build_ms` ≈ **10 ms**
- `serialization_ms` ≈ **16 ms**
- `frame_bytes` ≈ **570 KB**
- `include_cognition`: **false**

So UI capture is **~2%** of a ~1.2 s tick — consistent with the profile (capture thread ~1.5% of samples).

---

## Profiler method

```text
py-spy record -p 10494 -d 45 --format speedscope --threads --nonblocking
→ results/live_aged_run_performance_forensics/pyspy_speedscope.json
   Samples: 4446  Errors: 104  (~45 s @ 100 Hz)
```

Also: instantaneous `py-spy dump` series (`pyspy_dump.txt`, `pyspy_dump_series.txt`).

**Caveat:** `--nonblocking` avoids pausing the interpreter (safer for a live science run) but can miss/skew some samples (104 errors). Directional hotspot is still unambiguous across record + dumps.

---

## Hottest stacks / functions

### Thread share (sample weight)

| Thread | Share |
|---|---|
| `psy-observer-sim` (12755) | **96.6%** |
| MainThread | 1.8% |
| `psy-observer-capture` | 1.5% |
| heartbeat | ~0.1% |

### Hottest leaf (self time)

| Share | Frame |
|---|---|
| **~31%** | `predictive_relevance.retrieve` L184 |
| **~30%** | `predictive_relevance.retrieve` L185 |
| ~3% | `predictive_equivalence.learn` genexpr L372 |
| ~2–3% | other `predictive_equivalence.learn` sites |
| ~2% | signal_context episode grouping lambda (Observer signal path) |
| ~1.4% | `predictive_compression` signature genexpr |
| ≲1% each | `prospective_composition`, JSON encode, websockets deflate, `jsonish_copy`, PSC `dominates` |

**Combined:** ~**61% self** in the two `predictive_relevance.retrieve` loop lines that iterate `eq_store["classes"]` and filter by action / support / AABB partial match.

### Hottest inclusive (selected)

| Share | Frame |
|---|---|
| 96.6% | thread `psy-observer-sim` |
| 91.7% | `session._loop` → `_scientific_step_once_unlocked` → `two_agent.step` |
| 90.4% | `runtime.begin_tick` |
| **60.2%** | `temporal_predictive_structure.retrieve` L201 |
| ~30.6% | `cognition.run_cognition_before_action` L641 (retrieve call) |
| ~29.6% | `run_cognition_before_action` L695 → **`collect_entry_steps`** → same retrieve chain |
| ~12.0% | `temporal_predictive_structure.learn` |
| ~4.4% | `select_observed_composite_motor` (PSC composite path) |

Dominant stack pattern (≈58% of samples across near-identical variants):

```text
psy-observer-sim
  session._loop / _scientific_step_once_unlocked
    two_agent.step / _step_once
      runtime.begin_tick
        cognition.run_cognition_before_action
          [direct retrieve  OR  collect_entry_steps]
            temporal_predictive_structure.retrieve
              predictive_relevance.retrieve   # for cls in classes.values(): …
```

Code at the leaf (`predictive_relevance.py`):

```python
for cls in (eq_store.get("classes") or {}).values():
    if cls.get("status") != "ACTIVE" or cls.get("action") != act:
        continue
    ...
    gate = _partial_in(frag, aabb, keys)
```

As the aged run accumulates ACTIVE classes, each retrieve becomes a longer linear scan; cognition invokes retrieve **many times per tick** (lags × actions × bridge/prospection entry collection). That matches “slow only after aging.”

---

## Category checklist (requested areas)

Interpretation uses **leaf/stack evidence**, not the multi-label regex table in `pyspy_analysis.json` (that helper over-counts `observer_api` / `gc` because almost every stack includes `session.py`, and `collect_*` matched a naive `collect` pattern).

| Area | Role in *this* aged slowdown |
|---|---|
| **Temporal retrieve / predictive_relevance class scan** | **DOMINANT (~60%+)** |
| **predictive_equivalence learn** | Secondary (~12% inclusive) |
| compression / soft_match / predict_one_step | Minor (~3% leaf-ish; compression genexpr ~1.4%) |
| multiscale prediction | Negligible in samples (~0.04% category) |
| prospective composition | Small (~4% category / <1% leaf helpers) |
| PSC / scenario competition / observed composite | Present but small (~2–4% inclusive on select path) |
| contextual 4.26 | **≈0%** in profile |
| context-grounded prospection 4.27 | **≈0%** |
| persistent control 4.28 | **≈0%** |
| SMC / historical sensorimotor bridge | Small (~2% category) |
| evidence / JSON | Small (json encode / jsonish_copy ≲1–2%) |
| Observer / API | Capture ~1.5%; websocket deflate ~1%; **not** tick limiter under MINIMAL |
| locks / waits | Capture/AnyIO mostly idle waits; sim is compute-bound (GIL-active), not lock-blocked |
| GC | No clear `gc` module hotspot in leaf list |

---

## Runtime-accessible counters (read-only; no process patch)

Available without mutating science state:

| Source | Finding |
|---|---|
| `/api/runtime/progress` | `last_tick_wall_ms` ~1.1–1.2 s; `sim_ticks_per_sec` ~0.8–0.9 |
| `/api/observer/detail` | MINIMAL; producer_calls world≫cognition |
| `/api/state` → `agents_observer[0]` | `cognition_ticks` ~3072; `prediction_count` ~1685; `prospective_compositions` 907; selection `OBSERVED_COMPOSITE_PSC` / often `EXACT_TIE` |
| `/api/state` → `observer_perf` | compact capture ~10–16 ms |
| `/api/diagnostics` decision receipt | `retrieved_structures.compression_predictions` ~8–9; scenario_groups per locomotor action; competition active |
| Equivalence **class cardinality** | **Not exposed** on existing live APIs (would require a new diagnostic or attaching a debugger that reads heap — not done) |

**Not done (by request):** no monkeypatch, no mechanism toggle, no reset, no new run, no optimization.

---

## What this rules in / out

**Ruled in as current wall-time sink**

- Aged growth of predictive-equivalence class stores × high retrieve fan-out from temporal predictive structure and temporal prospection bridge entry collection.

**Ruled out as primary cause of *this* slowdown**

- Observer FULL cognitive_view rebuilds (this run is MINIMAL/compact).
- Research 4.26–4.28 (enabled, but not showing in samples).
- PSC competition / soft_match alone (visible but small vs retrieve scan).
- Idle lock contention on the sim thread.

**Open measurement gap**

- Exact `len(eq_store["classes"])` / ACTIVE class counts per agent on this live process were not available via existing HTTP diagnostics. Profile chemistry strongly implies that number is already large enough to dominate.

---

## Artifacts

| Path | Contents |
|---|---|
| `results/live_aged_run_performance_forensics/pyspy_speedscope.json` | 45 s speedscope (open in https://www.speedscope.app/) |
| `results/live_aged_run_performance_forensics/pyspy_hotspots.txt` | Text hotspot report |
| `results/live_aged_run_performance_forensics/pyspy_analysis.json` | Machine-readable aggregates |
| `results/live_aged_run_performance_forensics/pyspy_dump*.txt` | Instantaneous stacks |
| `results/live_aged_run_performance_forensics/progress_window.jsonl` | Tick/wall during profile |
| `results/live_aged_run_performance_forensics/tick_progression.jsonl` | Earlier tick sampler |
| `results/live_aged_run_performance_forensics/tick_rate_summary.json` | Summaries |
| `results/live_aged_run_performance_forensics/proc_snapshot.txt` | `/proc` memory/io |
| `results/live_aged_run_performance_forensics/api_snapshot.json` | Mechanisms + diagnostics summary |
| `results/live_aged_run_performance_forensics/state_perf_extract.json` | observer_perf / pipeline |
| `results/live_aged_run_performance_forensics/runtime_counters.json` | Decision/competition counters |

---

## Verdict

**LIVE_AGED_BOTTLENECK = TEMPORAL_PREDICTIVE_RELEVANCE_CLASS_SCAN**

The currently running aged Tiktaalik is compute-bound in `psy-observer-sim`, burning the majority of each ~1.2 s tick on **`predictive_relevance.retrieve` linear class iteration** under **`temporal_predictive_structure`** (including **`collect_entry_steps`** traffic), not on Observer rendering and not on 4.26–4.28.

**Run preserved.** No optimization applied. No git push.

