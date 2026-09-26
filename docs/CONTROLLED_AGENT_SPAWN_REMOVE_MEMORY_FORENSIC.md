# Controlled Tiktaalik spawn/remove — memory forensic

**Do not treat this as a causal explanation of the 15.4 GB OOM.** That incident is independently identified. This document records a bounded attempt to **falsify** a spawn→remove leak.

## Phase 0 — historical OOM (PID 269596)

| Field | Evidence |
|---|---|
| Time | 2026-09-23 06:52:14 local (`kern.log`) |
| Task | `python` pid **269596**, uid 1000 |
| RSS | anon-rss **15410428 kB ≈ 15.4 GB**, total-vm ≈ 15.9 GB |
| Invoker | `ChatGPT` (desktop) tripped the OOM killer (`oom_score_adj=300`); victim was the largest anon consumer |
| Cmdline | process gone; no `/proc/269596`; no coredump |
| Identity | **Observer Python during Analyze / evidence load**, not spawn/remove |

Authoritative prior forensic: `docs/BETA3_LONG_RUN_ANALYZER_FAILURE.md`

- Live dir `results/psychology_observer/psy_observer_web/.live-psyweb-20260923T015520.874726Z-f390c468/`
- Dominant term: `scientific_decisions.jsonl` **1.90 GB** materialized in-process
- Expected RAM order **10–20 GB**, matching the kill
- Later bounded Analyzer job: **1.82 GB** peak on the same corpus

Related but **different** python OOMs on this host:

- 2026-09-22 05:59 pid **20829** ≈ 19.9 GB (not this task)
- 2026-09-22 23:03 pid **179327** ≈ 14.6 GB — Save & Stop (`docs/BETA3_SAVE_STOP_FAILURE.md`)

`HISTORICAL_OOM_PROCESS_IDENTIFIED = YES`  
`HISTORICAL_OOM_LINK_TO_CONTROLLED_AGENT = DISPROVED` for PID 269596.

## Phase 1 — ownership graph (production)

```
POST /api/experimenter/spawn
  → ObserverSession.experimenter_spawn
      → (if PhysicalSystemRuntime) promote_physical_to_two_agent_host
           TwoAgentRuntime.__init__/reset constructs two throwaway slots, then
           host.slots = [live_psr]  # throwaways become unreachable (one-time)
      → spawn_experimenter_body
           new PhysicalSystemRuntime(cognition_enabled=False)
           append to TwoAgentRuntime.slots
           experimenter_slot = last index
      → controller.begin_recording → deepcopy(runtime.snapshot())  # one S0 dict
      → _capture_locked(detail=full)  # one retained public frame

POST /api/experimenter/remove
  → remove_experimenter_body
      pop last slot (must be experimenter)
      experimenter_slot = None
      trim _agent_stats / _prev_xy / process_order
      controller.active = False
      intervention_active stays True (provenance)
      does NOT demote TwoAgentRuntime → PhysicalSystemRuntime  (by design)
      does NOT stop recording / drop s0_snapshot  (one dict, replaced next spawn)
```

Observer: `_buffer` maxlen **1** (`FULL_PUBLIC_FRAME_RETAIN`). Eye uses `_eye_prev_fpv` keyed by living agent ids; HEADLESS skips Eye work.

Scientific V3: spawn may append one `EXPERIMENTER_BODY_SPAWNED` event. No second recorder/sink is created.

## Reproduction (ceiling = baseline + 800 MB; abort if >40 MB/cycle after warmup)

Harness: `experiments/run_controlled_agent_memory_forensic.py`  
Results: `results/controlled_agent_memory_forensic/summary.json`  
Tests: `tests/test_controlled_agent_memory_forensic.py`

Did **not** drive RSS toward 15 GB. Did **not** restart live :8768.

### Direct TwoAgentRuntime spawn→remove

| | RSS MB | PSR count | cognition object ids |
|---|---|---|---|
| 10 cycles baseline | 45.6 | 2 | stable |
| after first spawn | 50.1 | 3 during spawn | autonomous ids unchanged |
| after 10 cycles | 58.1 | 2 | same ids |
| 50 cycles baseline | 57.5 | 2 | |
| after 50 cycles | 77.4 | 2 | same ids |
| Δ/cycle (post-warmup, 50) | **0.41 MB** | returns | **no duplicate graph** |

Classification: **STABLE**. Gentle RSS creep with **returning object counts** is consistent with glibc arena retention, not a reachable PSR/cognition leak.

Isolated Eye/LIVE spawn/remove: PSR 2→3→2, extras **0** after GC.

### Promotion

- Autonomous `cognition` / `body` identities preserved.
- After remove of a promoted single-agent host: **TwoAgentRuntime with 1 slot** (intentional; not a leak).
- Re-spawn uses last slot again; no stacked experimenters.

### Observer session

| | notes |
|---|---|
| full frames retained | **1** / cap 1 — no 512-ring regression |
| HEADLESS 10 cycles | 75.5 → 117 MB, Δ ≈ 4.4 MB/cycle; agents=2; cognition ids preserved |
| Eye+FPV 5 cycles | 112 → 135 MB, Δ ≈ 5.6 MB/cycle; `_eye_prev_fpv` keys `agent_0`,`agent_1` only |
| S0 snapshot | 1 deepcopy held after last spawn (`begin_recording`); not a per-cycle list |
| controller | `active=False` after remove |

Observer Δ/cycle is higher than bare runtime because spawn forces a **full frame** + **snapshot deepcopy**. It flattened far below the abort threshold and far below 15 GB.

## Case classification

**CASE 1 — no reproducible abnormal growth / reachable leak.**

`CONTROLLED_AGENT_MEMORY_BUG = NOT_REPRODUCED`

No production patch. Historical 15.4 GB OOM remains the Analyzer JSONL-materialization incident (already mitigated by bounded Analyzer 1.2 subprocess). Spawn/remove near a restart/update remains a **time coincidence**, not a demonstrated mechanism for that kill.

## Semantics

`SCIENTIFIC_SEMANTICS_CHANGED = NO`  
`COGNITION_SEMANTICS_CHANGED = NO`  
`VISION_SEMANTICS_CHANGED = NO`  
`RUNTIME_BEHAVIOR_CHANGED = NO`  
`BETA3_REFERENCE_MODIFIED = NO`  
`GIT_PUSH = NO`
