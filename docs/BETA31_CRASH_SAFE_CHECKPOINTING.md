# Beta 3.1 — crash-safe checkpointing

Persistence infrastructure only. Cognition, SMC, PE, compression, prospection, PSC, motor, physics, ecology, signals, vision, R3, and V3 **receipt** semantics are unchanged.

Cadence default is **OFF** (`checkpoint_every_ticks = 0`).

## What Save already persisted

`runtime.snapshot(persist=True)` aliases live cognition; `dump_persist` streams JSON without `json_prepare` mutation. Public `snapshot()` still deepcopies.

Included: tick, seed, config, world/ecology/optical field, body pose/velocity/head/osc, internal medium, cognition graph (SMC/PE/compression/prospective as stored), last observation/action/motor.

**Not in snapshot:** numpy RNG state; Observer UI buffers; Scientific V3 JSONL (append-only on disk). Restore therefore **cannot** resurrect unpersisted ticks after the checkpoint.

## Generations

Under `<live_dir>/runtime_checkpoints/`:

- `tmp/` write then fsync  
- atomic rotate: `previous ← current ← new`  
- restore reads **current**, else **previous**, never `tmp`  
- failed dump (including ENOSPC mock) leaves the last committed generation

API: `GET /api/checkpoint/status`, `POST /api/checkpoint/cadence`, `POST /api/checkpoint/now`, `POST /api/checkpoint/restore`.  
UI: header CHECKPOINT cluster (cadence OFF/1000/2500/5000, NOW, RESTORE). Do not use RESTORE on an unrelated live Observer.

## V3 branching

Restore assigns a **new** `run_id`, reopens writers, stamps:

- `resumed_from_checkpoint`  
- `checkpoint_tick`  
- `previous_run_id`  
- `branch_note`

Dead post-checkpoint receipts stay in the old live dir. Analyzer must treat them as a separate segment.

## Measurements (this work)

| Tick | Write s | Size MB | ru_maxrss Δ MB |
|---|---|---|---|
| 100 | 0.24 | 1.68 | ~1 |
| 250 | 0.30 | 1.98 | ~1 |

`CHECKPOINT_MEMORY_BOUNDED = YES` on these ages. Not measured at 10k+ (expensive; do not hide by skipping on purpose—call it not measured).

Crash injection: step 80, cadence 50, `os._exit(9)`, restore t50, continue to t58, new V3 meta. Two-agent session restore t40 → t46.

Pytest: `tests/test_beta31_crash_checkpoint.py`.

Suggested long-run cadence: **2500 or 5000** ticks, plus RSS watch. Checkpoints do **not** stop OOM; they bound how much biography is lost.
