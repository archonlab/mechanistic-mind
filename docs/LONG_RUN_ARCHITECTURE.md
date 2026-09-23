# LONG-RUN Observer architecture (Phase 1)

Development note for Mechanistic Mind 2.0 / Tiktaalik: Undercover.
Public Beta 1 is already published; this is **post-beta plumbing**.

## Separation of systems

```
                    SIMULATION
                         |
             +-----------+-----------+
             |                       |
             v                       v
     SCIENTIFIC WRITER          LIVE OBSERVER
       persistent                bounded/sample
             |                       |
             v                       v
      experiment history         current UI
```

| System | Role | Growth |
|--------|------|--------|
| Simulation | Authoritative current runtime | Per-tick work (not history scan) |
| Scientific history | Evidence / Analyzer / forensics | May grow with run age |
| LIVE Observer | Bounded current view + control | **Must not** grow with run age |

Analyzer may intentionally load scientific history.
Ordinary LIVE refresh must not.

## Bounded LIVE policy

Named constants live in:

- `mechanistic_mind/ui/psy_observer_web/live_bounds.py`
- `web/psy-observer/src/liveBounds.ts`

| LIVE surface | Authority | Cap (approx) |
|--------------|-----------|--------------|
| Current state | latest only | 1 frame |
| Map trajectory | `live_recent_trajectory` | embed ~96 compact; ring ≥2048 |
| Events | session event ring + embed | ring 2500; compact embed 16 |
| Interventions | session ring + embed | session 512; embed 64 |
| Signals LIVE | signal live_accum deque | existing bounded |
| Cognition LIVE | latest agents_views | not sci history |
| Sensors / World GT | current runtime | latest |
| FE timeline/events | replace-from-API + retainRecent | 400 / 500 |
| Scientific history | JSONL writer | unbounded (by design) |
| Analyzer | evidence package | intentional load |

**Critical:** `live_recent_trajectory` ≠ scientific trajectory ≠ agent memory.

## Architecture before

- Most Observer rings were already `deque(maxlen=…)`.
- **Pathology:** `_world_interventions` was an unbounded list and was embedded wholesale into LIVE frames / Apply receipts. With many LIVE ecology/mechanism interventions, serialize + WS payload scaled with intervention count (session age / operator activity), not with scientific necessity.
- Compact traj/telem already tailed, but intervention embed was not.
- FE aux lists replaced from API but lacked an explicit “ignore scientific_rows” projection helper.

## Architecture after

- `_world_interventions` → `deque(maxlen=LIVE_WORLD_INTERVENTION_SESSION_MAX)`.
- LIVE frames embed `tail_list(..., LIVE_WORLD_INTERVENTION_EMBED)` + summary `n`.
- Capture stamps `observation.live_bounds` and `history_elements_touched_by_live_refresh`.
- Trajectory/telemetry rings use named `LIVE_*_RING_MIN` (≥2048).
- FE `projectLiveAuxState` caps timeline/events and records `scientific_rows_ignored`.
- Existing async capture remains latest-wins (`_capture_pending` single slot; visual drops counted).

## What remains unbounded (and why)

| Item | Why |
|------|-----|
| Scientific JSONL / evidence files | Required for Analyzer / reproducibility |
| GEO empirical `_buckets` | Grows with unique visited (agent,cell,action); Observer GT, not sci cognition — monitor in Phase 2 |
| Process RSS with sci writer open | Writer + Python alloc; not LIVE payload |
| Analyzer in-memory when Analyze Current runs | Intentional |

## Root-cause classification (measured)

| Component | Class | Evidence |
|-----------|-------|----------|
| simulation core | NOT_CONTRIBUTING (age) | tick_ms ~19→23 ms 0.5k→10k (mild, not history-linear) |
| scientific writer | MINOR | disk/rows grow; not in LIVE refresh path |
| backend live serialization | CONTRIBUTING (fixed) | unbounded intervention embed → 77× bytes synthetic |
| API payload growth | NOT_CONTRIBUTING (after) | ~284–329 KB flat; touched=176 constant |
| frontend polling | NOT_CONTRIBUTING | aux replace; WS latest frame |
| frontend retained history | CONTRIBUTING risk (hardened) | caps + negative tests |
| frontend projection | NOT_CONTRIBUTING | ignores scientific_rows |
| React rendering | UNKNOWN (browser not attached) | backend does not force age growth |
| map trajectory | NOT_CONTRIBUTING | ring + embed bounded |
| signals UI | NOT_CONTRIBUTING | live_accum maxlen |
| cognition UI | NOT_CONTRIBUTING | latest view |
| Analyzer accidental live work | NOT_CONTRIBUTING | capture does not call evidence loader |
| Undercover request path | NOT_CONTRIBUTING (age) | input~22–29 ms across ages |
| memory pressure / GC | MINOR | RSS rises with sci history on disk/process |

## Run-speed controller (Phase 2 home)

Future PAUSE / 1× / 5× / 20× / MAX / HEADLESS should live next to:

- `SessionConfig.speed` + `tick_sleep_seconds` / `observer_capture_period` in `session.py`
- UI control strip (Observer attach/detach)

Do **not** couple display FPS to scientific tick rate (already decoupled via async capture + `ui_hz`).

## Snapshot readiness (design audit only)

Current: `GET /api/snapshot` → `runtime.snapshot()` schemas
`mm.physical_system.snapshot.v2` / `two_agent.snapshot.v1`.

| Need for deterministic resume | Status |
|-------------------------------|--------|
| World fields / bodies / internals | Captured in runtime snapshot |
| Cognition working stores | Partially — depends on runtime snapshot coverage |
| RNG streams | Must verify per-slot RNG in snapshot (Phase 2 gate) |
| Intervention / regime history | LIVE ring only; full provenance in sci events — restore must rebind Undercover |
| Scientific writer continuity | Not in snapshot; new run_id on restore today |
| Observer rings | Cleared on restore (by design) |

**Verdict:** resume-of-physics is supported; bit-exact continuation including sci history continuity is **not** Phase-1 complete.

## Telemetry bytes/tick (recommendation only)

Measured ~40 KB/tick scientific on-disk at 10k (rich writer). Estimates in
`results/performance/long_run_observer_audit/observer_age_profile.md`.

Future tiers:

- **LEVEL 0** — state checkpoints
- **LEVEL 1** — compact scientific timeline
- **LEVEL 2** — rich structural events / provenance

Do not truncate Analyzer evidence to make UI faster.

## Phase 2 recommendation (do not auto-implement)

Based on this audit, prefer in order:

1. **Tiered scientific telemetry** (storage dominates long-run cost)
2. **Deterministic snapshots/resume** (RNG + sci continuity)
3. **Run-speed controller + headless/MAX** (operator UX)
4. **Observer attach/detach** (headless then attach LIVE)
5. GEO bucket compaction / pruning policy if GT overlay cost appears at 50k+

## Scientific equivalence

Paired 120-tick runs with/without LIVE captures: **EXACT_MATCH** fingerprints.
UI-only bounded buffers may differ; scientific runtime must not.
