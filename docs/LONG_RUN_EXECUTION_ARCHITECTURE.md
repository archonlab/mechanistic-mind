# Long-run execution architecture

**Principle:** measure first; accelerate wall-clock execution of the *same* scientific ticks. Presentation policy is not a different world.

## Modes (presentation / wall-clock only)

| Mode | Sim wall-clock | Observer sample | Live map frames | Scientific ticks |
|------|----------------|-----------------|-----------------|------------------|
| **LIVE** | ~1× throttle | ~10 Hz | yes | every tick |
| **FAST** | ~10× throttle | ~5 Hz | yes (latest-wins) | every tick |
| **MAX** | CPU-limited (`speed=MAX`) | ~2 Hz | yes (async, non-blocking) | every tick |
| **HEADLESS** | CPU-limited | no normal capture | no | every tick |

Presets live in `EXECUTION_MODE_PRESETS` (`session.py`). APIs:

- `POST /api/control/execution-mode` `{mode, target_tick?}`
- `POST /api/control/observer-hz` `{hz}`
- `POST /api/control/target-tick` `{target_tick}`

## Clock decoupling (mandatory)

```
SIMULATION LOOP          OBSERVER SAMPLE LOOP
  tick                     sample (bounded Hz)
  tick                          sample
  tick                               sample
  …
```

- Observer Hz does **not** define simulation Hz.
- Live visualization is **latest-state** (obsolete presentation frames drop).
- Scientific history is **not** UI frame history.
- HEADLESS skips presentation capture entirely; progress still exposes `sim_tick` / `sim_ticks_per_sec` / ETA on the header overlay.

## Backpressure

| Path | Class | Notes |
|------|-------|-------|
| HTTP/API serialize | NON_BLOCKING | on demand |
| Live WS/push | NON_BLOCKING_BOUNDED | latest-wins; timeout skip |
| Live frame gen | BOUNDED | async capture worker; coop lock yield |
| Scientific V2 writer | BLOCKING_ON_SIM | append on SIM path; flush every 32 |
| Presentation queue | BOUNDED | drop obsolete LIVE frames only |

No unbounded presentation queues for MAX/HEADLESS.

## Target tick / long run

`target_tick` pauses the runner at the boundary (`PAUSED`). UI shows current / target / t/s / ETA (operational only — never written into cognition).

## Attach / detach

MAX/HEADLESS continue without requiring a browser. Attaching Observer samples current runtime at bounded Hz; detach stops presentation only. Scientific trajectory must not change because Observer attached (fingerprint gate: modes EXACT_MATCH).

## Search worker boundary (future)

```
SEARCH SCHEDULER
  ├── worker (HEADLESS runtime, seed A) → compact metrics
  ├── worker (HEADLESS runtime, seed B) → compact metrics
  └── …
```

Process-level parallelism; no shared RNG. Evidence tiers (config only — no semantic “interestingness” yet):

1. **FULL_SCIENTIFIC** — normal research runs  
2. **SEARCH_COMPACT** — bounded metrics + required mechanism evidence  
3. **SEARCH_CANDIDATE** — promote richer evidence when a *factual* condition fires  

## UI vs runtime vs Search throughput

- **UI speedup:** fewer/cheaper presentation frames (FAST/MAX/HEADLESS).  
- **Runtime speedup:** less work per scientific tick (future hot-path work).  
- **Aggregate Search throughput:** sum of world-ticks/sec across workers.

See `results/performance_architecture/SUMMARY.md` for measured numbers on this machine.
