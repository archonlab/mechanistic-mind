# Beta 3 snapshot memory optimization

**Date:** 2026-09-23  
**Kind:** persistence capture/encoding only. Cognition, PE, SMC, world, and motor semantics unchanged.  
**Prior aged-save data:** not overwritten (`results/beta3_aged_save_memory/`).  
**This run:** `results/beta3_snapshot_memory_optimization/`  
**Forensic t10231 live dir:** untouched.

## Why deepcopy existed

`PhysicalSystemRuntime.snapshot()` historically returned `deepcopy(self.cognition)` so the snapshot dict was **independent of later `step()`** and of **in-place `json_prepare`**.

Save/Stop does **not** hold `_step_lock` for the JSON write:

1. `_join_runner()` stops SIM.
2. Short lock: tick boundary + `_capture_locked()`.
3. Lock released.
4. `finalize_run` → `runtime.snapshot()` → encode → disk.

`json_prepare` mutates string-key dicts in place (rewrites nested values, re-keys mixed keys, turns tuples into lists). Pointing it at live cognition would corrupt the runtime.

**DEEPCOPY CURRENTLY GUARANTEED (public `snapshot()`):**

1. A frozen copy at call time: later `rt.step()` does not change the returned dict.
2. Callers (`json_prepare`, tests, `GET /api/snapshot`) can mutate the dict without mutating live stores.
3. Restore after further ticks still reconstructs the captured tick.
4. Two agent cognition graphs are not aliased through the snapshot payload.

That guarantee is **still required** for the public API. It is **not** required for Save & Stop after the runner is joined, **if** encoding is read-only.

## Consistency boundary

| Boundary | What | Duration |
|---|---|---|
| CONSISTENCY | SIM stopped; `snapshot(persist=True)` aliases canonical cognition; world/body/config already copied by existing serializers | ~2 ms (EXTREME) |
| SERIALIZATION | C `json.dump` of the persist view to `.part` (no full JSON string) | ~5 s (EXTREME compact) |
| LOCK | Observer `_step_lock` is **not** held during dump | dump is outside lock |

Do not `snapshot(persist=True)` while the runtime can still `step()`.

## Canonical vs derived vs ephemeral

| Class | Examples | Persist |
|---|---|---|
| CANONICAL | PE `classes` (ACTIVE+FORGOTTEN), members, episodes, SMC `records`, compression structures, prospection transitions, config, world, body, internal, tick/seed | Yes |
| DERIVED | `_ix_action`, `_ix_member`, `_active_ids`, `_active_count`, `_ix_*`, `_mean_c_cached`, SMC indexes | May appear in compact JSON; **dropped on restore** via `clear_derived_indexes` |
| EPHEMERAL / CACHE | retrieve caches | Same |
| UI/OBSERVER | session timeline/telemetry buffers | Bounded session files, not cognition |

## json_prepare mutation

`json_prepare` **must not** run on live cognition. Production dump uses `dump_persist`:

- str-key trees: CPython `json.dump` (read-only)
- mixed int/None keys: non-mutating walker that stringifies keys on the fly
- no `json.dumps(full_snapshot)`, no `BytesIO`/`StringIO` of the snapshot

Public `snapshot()` still `deepcopy`s cognition so existing tests and `GET /api/snapshot` stay detached.

## Implementation chosen

Smallest safe change:

1. `snapshot(persist=False)` default — deepcopy (public).
2. `snapshot(persist=True)` — alias live `cognition` / last observation / last motor.
3. `write_finalized_run` uses `persist=True`.
4. Compact JSON for `physical_system_snapshot.json`; pretty `run.json` kept for small metadata.

Rejected: copy-on-write, locking the runtime for the whole dump, field-by-field second graph.

## Architecture before → after

```
BEFORE: live cognition → deepcopy → json_prepare(mutate copy) → json.dump indent=2
AFTER:  live cognition → persist view (alias) → json.dump compact, read-only
```

## OLD vs NEW aged memory (Save & Stop)

OLD = deepcopy + pretty JSON + in-process tracemalloc during save  
NEW = persist view + C compact dump, no tracemalloc

| STATE | OLD ΔRSS | NEW ΔRSS | MEMORY REDUCTION | OLD TIME | NEW TIME | SPEEDUP | OLD SIZE | NEW SIZE |
|---|---|---|---|---|---|---|---|---|
| SMALL | 43.7 MB | 1.31 MB | 42.4 MB | 6.56 s | 0.53 s | 12.5× | 5.70 MB | 2.60 MB |
| MEDIUM | 74.1 MB | 1.40 MB | 72.7 MB | 11.81 s | 0.78 s | 15.2× | 9.31 MB | 4.02 MB |
| AGED | 289.6 MB | 1.21 MB | 288.4 MB | 59.69 s | 2.76 s | 21.6× | 37.95 MB | 13.37 MB |
| EXTREME | 606.0 MB | 1.04 MB | 604.9 MB | 123.03 s | 5.16 s | 23.9× | 78.67 MB | 26.73 MB |

EXTREME NEW: baseline 196.9 MB, peak 198.0 MB, **peak/baseline 1.005**. `.part` peak = final file size.

Isolated AGED deepcopy capture still costs **+51.5 MB / 0.83 s**. Persist view: **+0.16 MB / 1 ms**.

## Pretty vs compact (same persist view, C encoder)

| | MEDIUM | AGED |
|---|---|---|
| compact bytes | 4.022 MB | 13.367 MB |
| pretty bytes | 9.187 MB | 35.605 MB |
| compact time | 0.665 s | 2.447 s |
| pretty time | 0.710 s | 2.651 s |
| json.loads equal | yes | yes |
| RSS during dump | ~+0 MB | ~+0 MB |

Pretty is only slightly slower once deepcopy is gone. Compact is still preferred: ~2.6× smaller files. Runtime snapshots are machine persistence; `run.json` stays indented.

## Lock / capture timing (NEW EXTREME)

- persist capture: **1.9 ms**
- snapshot dump: **5.03 s** (outside `_step_lock`)
- HTTP `wait:false` POST: **33 ms**, then poll `FINALIZING` → `STOPPED`

## Restore / P0 / step

All four sizes: restore OK, PE/SMC indexes rebuilt, one post-restore step. Oracle test: persist file vs JSON-roundtripped deepcopy snapshot, then `step()` action/position match (`tests/test_snapshot_persist_view.py`). P0 tests passed.

JSON cannot preserve tuple vs list; both paths round-trip to lists. That was already true of `json_prepare`.

## Async / failure / atomic / repeat

- POST `save:true, wait:false` returns immediately; phases include `saving_snapshot` … `saved`
- Injected `MemoryError` → `SAVE_FAILED`, not stuck `FINALIZING`; 0 published runs
- `.part` → fsync → replace → tmp-dir rename
- Three saves on one MEDIUM runtime: RSS 157.2 MB flat

## ~3.5 GB aged Observer (cautious)

Save transient ΔRSS was **~1 MB at every synthetic size**, not proportional to snapshot bytes. Encoder buffers did not scale like a second cognition graph.

**Plausible Save & Stop peak:** live RSS + a few MB + OS page cache for the write, **not** 2× cognition.

**Uncertainty:** world `serialize_planet_state` still copies the planet; a much larger world grid would add its own copy. Restore/`GET /api/snapshot` still materialize a full graph.

**Remaining OOM risk:** opening the snapshot in RAM (restore, inspect); public `snapshot()` deepcopy; calling `persist=True` while SIM is running; host RAM below live RSS + file write cache.

## Files changed

| Path | Change |
|---|---|
| `mechanistic_mind/physical_system/runtime.py` | `snapshot(persist=...)` |
| `mechanistic_mind/physical_system/two_agent.py` | pass `persist` |
| `mechanistic_mind/ui/psy_observer_web/run_finalize.py` | `dump_persist`, compact snapshot, persist timings |
| `tests/test_snapshot_persist_view.py` | oracle + mutation tests |
| `tests/test_run_finalize_json_safe.py` | live mixed keys survive save |
| `experiments/run_beta3_snapshot_memory_optimization.py` | NEW matrix |
| `experiments/run_beta3_aged_save_memory.py` | timings; no tracemalloc during save |

`GIT_PUSH=NO`.

## Acceptance

| Gate | Result |
|---|---|
| DEEPCOPY_PURPOSE_IDENTIFIED | PASS |
| SNAPSHOT_CONSISTENCY_DEFINED | PASS |
| REFERENCE_SNAPSHOT_ORACLE | PASS |
| COGNITION_FULL_DEEPCOPY_REMOVED_OR_REDUCED | PASS (save path; public snapshot still copies) |
| LIVE_RUNTIME_NOT_MUTATED_BY_JSON_PREPARE | PASS |
| COMPACT_JSON_BENCHMARKED | PASS |
| COMPACT_JSON_SEMANTIC_EQUIVALENCE | PASS |
| AGED_MEMORY_MATRIX | PASS |
| PEAK_RSS_REDUCED | PASS |
| SAVE_TIME_REDUCED | PASS |
| LOCK_HELD_TIME_MEASURED | PASS |
| AGED_RESTORE | PASS |
| P0_INDEX_REBUILD | PASS |
| POST_RESTORE_STEP_EQUIVALENCE | PASS |
| ASYNC_SAVE_JOB_REGRESSION | PASS |
| FAILURE_RECOVERY_REGRESSION | PASS |
| ATOMIC_PUBLISH_REGRESSION | PASS |
| REPEATED_SAVE_NO_LIVE_OBJECT_LEAK | PASS |
| SCIENTIFIC_SEMANTICS_PRESERVED | PASS |
| READY_FOR_REAL_LONG_RUN | **PASS** |

## READY_FOR_REAL_LONG_RUN

**PASS** for Save & Stop memory: EXTREME save no longer allocates a second cognition graph (ΔRSS ~1 MB, ratio ~1.00). Compact snapshot is ~3× smaller and ~24× faster than the previous pretty+deepcopy save. Async job and FINALIZING recovery still work.

Public `snapshot()` deepcopy and full-file restore remain by design. Do not treat this as a guarantee that a 3.5 GB live process plus a huge restore in the same process cannot OOM.