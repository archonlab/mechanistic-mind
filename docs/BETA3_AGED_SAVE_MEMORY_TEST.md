# Beta 3 aged Save/Stop memory verification

**Date:** 2026-09-23  
**Kind:** persistence verification only (no P0 / cognition / physics changes).  
**Harness:** `experiments/run_beta3_aged_save_memory.py`  
**Raw measurements:** `results/beta3_aged_save_memory/`  
**Forensic t10231 live dir:** left untouched  
`results/psychology_observer/psy_observer_web/.live-psyweb-20260922T192322.056455Z-f9b24837/`

This is not a scientific reproducibility certification.

## Primary question

Can a realistically aged Beta 3 runtime now be saved with bounded transient memory usage?

**Answer:** Save no longer builds a second full JSON tree plus a giant `json.dumps` string. Transient RSS still includes **one extra in-memory snapshot** from `deepcopy(self.cognition)` (two agents). Peak RSS / baseline was **~1.7×–2.4×** on disposable states, not the old ~4× OOM chain (~3.5 GB live → ~14.6 GB). **READY_FOR_REAL_LONG_RUN = PARTIAL** until that deepcopy is accepted as the remaining bound or isolated.

## 1. Save memory architecture

```
canonical TwoAgentRuntime (live cognition, world, bodies)
    ↓ runtime.snapshot()
TwoAgentRuntime.snapshot
    → PhysicalSystemRuntime.snapshot × 2
        world serialize (agent 0 only; agent 1 pops world)
        deepcopy(cognition)
        deepcopy(last_agent_observation / last_motor_output)
    ↓ write_finalized_run
validate_persistence_boundary (tick/identity checks; no extra graph copy)
    ↓ _json_dump
json_prepare (in-place on string-key dicts; re-key only mixed keys)
    ↓ json.dump(..., indent=2, sort_keys=True, default=str) to *.part
flush + os.fsync
    ↓ os.replace(.part → physical_system_snapshot.json)
copy_scientific_into: shutil.copy2 of jsonl (disk)
    ↓ run.json (small) written the same way
json.loads(run.json) only — snapshot file is size-checked, not parsed
    ↓ os.rename(.tmp-* → published run dir)
save-job: phases + accepted/run_dir
```

HTTP Save & Stop: `POST /api/control/stop {save:true, wait:false}` starts a backend thread (`FINALIZING`), returns a compact frame; `GET /api/control/save-job` polls `lifecycle` / `save` / `phases`.

## 2. Remaining full-state copies

| Hold | During save? |
|---|---|
| Canonical runtime | Yes |
| Full snapshot dict (`deepcopy` cognition per slot) | **Yes** |
| Recursive `json_safe` clone of the snapshot | **No** (`json_prepare` in place) |
| Full JSON `str` / `BytesIO` / `StringIO` | **No** (`json.dump` to file) |
| Re-`json.loads` of the snapshot file in finalize | **No** |
| Scientific jsonl in RAM | **No** (`shutil.copy2`; `read_jsonl_range` parses one line at a time) |
| Session timeline `"".join(json.dumps(...))` | Bounded UI buffer only, not the aged snapshot |

**Does save hold canonical + full snapshot copy + full JSON simultaneously?**  
Canonical + snapshot copy: **yes**. Full JSON string: **no**.

Quantify (EXTREME disposable): baseline RSS 438 MB, peak 1044 MB (**+606 MB**), snapshot file 79 MB. Extra RSS is ~**7.7× file bytes** and ~**1.4× baseline**, consistent with a Python object snapshot (pointer-heavy PE/FORGOTTEN graphs) plus encoder/file buffers, **not** with file-sized JSON × N extra copies.

`tracemalloc` diffs after `write_finalized_run` returns **under-count the peak**: the snapshot tree is allocated and then dropped before the compare snapshot. RSS sampling (20 ms in-process + 30 ms parent `/proc`) is the authority. Parent peak includes **restore** (`json.loads` of the snapshot file after save).

## 3. Test-state sizes

Disposable `TwoAgentRuntime` + production `pe.learn` / `smc.update` / `pc.observe` / `pr.learn_transition`. Not a random giant dict. Ticks are small (6–16); occupancy is aged. Forensic t10231 artifacts were not copied.

| Label | PE forgotten / agent | TPS inner forgotten / agent | SMC | Prospection | Compression structs | jsonl lines |
|---|---|---|---|---|---|---|
| SMALL | 1 | 10 | 256 | 128 | 64 | 40 |
| MEDIUM | 401 | 204 | 256 | 128 | 64 | 4_000 |
| AGED | 6_001 | ~3_005 | 256 | 128 | 64 | 25_000 |
| EXTREME | 14_001 | 7_004 | 256 | 128 | 64 | 40_000 |

Two agents throughout. ACTIVE PE cap 32. Host: MemTotal 23.4 GiB, MemAvailable ~15.6 GiB at start. Fill abort at 6 GiB RSS (not hit).

## 4. Memory table

RSS/VM from `/proc/<pid>/status` (VmRSS / VmSize). Peak from dense sampling, not one sample. `parent_peak` includes post-save restore.

| STATE | BASELINE RSS | PEAK RSS | DELTA RSS | parent peak RSS | SNAPSHOT SIZE | tmp .part peak | MEMORY AMPLIFICATION (ΔRSS / file) | peak / baseline | SAVE TIME | write MB/s | RESTORE | RESULT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SMALL | 65.58 MB | 109.32 MB | 43.74 MB | 122.27 MB | 5.695 MB | 5.695 MB | 8.05 | 1.667 | 6.559 s | 0.87 | OK + P0 + step | PASS |
| MEDIUM | 79.73 MB | 153.83 MB | 74.11 MB | 182.52 MB | 9.312 MB | 9.312 MB | 8.35 | 1.929 | 11.812 s | 0.79 | OK + P0 + step | PASS |
| AGED | 233.52 MB | 523.15 MB | 289.62 MB | 623.58 MB | 37.947 MB | 37.947 MB | 8.00 | 2.240 | 59.689 s | 0.64 | OK + P0 + step | PASS |
| EXTREME | 437.97 MB | 1043.91 MB | 605.95 MB | 1271.89 MB | 78.670 MB | 78.670 MB | 8.08 | 2.384 | 123.032 s | 0.64 | OK + P0 + step | PASS |

VM: EXTREME 1065 → peak 1750 MB (not 18.5 GB). After `gc.collect()`, RSS **did not drop** (arenas). That is not proof the snapshot dict is still live.

Old incident (t10231): ~14.6 GB RSS / ~18.5 GB VM during FINALIZING; empty `.tmp-*`; no published run.

## 5. Peak allocation source

Remaining large allocator on the save path:

`mechanistic_mind/physical_system/runtime.py` — `PhysicalSystemRuntime.snapshot` — `deepcopy(self.cognition)` (and observation/motor). TwoAgent calls this twice.

Not found on the finalize write path:

- `json.dumps(snapshot)`
- `BytesIO` / `StringIO` of the snapshot
- `json.loads` of `physical_system_snapshot.json` inside `write_finalized_run`

`read_run_snapshot()` still `read_text` + `json.loads` the full file; it is used for restore tests, not for finalize.

`json_prepare` `list(obj.items())` is per-dict, not a second graph.

## 6. Save-time scaling

Snapshot bytes vs save seconds (pretty-printed JSON, `indent=2`):

| STATE | file MB | save s | ~MB/s |
|---|---|---|---|
| SMALL | 5.7 | 6.6 | 0.87 |
| MEDIUM | 9.3 | 11.8 | 0.79 |
| AGED | 37.9 | 59.7 | 0.64 |
| EXTREME | 78.7 | 123.0 | 0.64 |

Time scales with snapshot size (roughly linear). Throughput is encoder+fsync limited, not RAM-copy of a giant string. A t10231-class pretty snapshot of hundreds of MB would take minutes, but that is duration, not the old OOM multiplier.

## 7. Async API behavior

`TestClient`: `POST /api/control/stop {save:true, wait:false}`

| Check | Result |
|---|---|
| POST duration | **0.0084 s** (not held for snapshot I/O) |
| Immediate lifecycle | `FINALIZING` |
| Mid-poll `pending` | true |
| Terminal lifecycle | `STOPPED` |
| Terminal save layer | `succeeded` |
| Phases | `flushing_telemetry` → `saving_snapshot` → `scientific_history_copied` → `saving_results` → `saved` → `scientific_live_staging_removed` |

No fake percent. Phases are backend-owned.

Default `wait` is **true** if the POST body is omitted; the Observer client must send `wait: false`.

## 8. Atomic publish

Successful saves:

- `.part` created; peak `.part` size **equals** final snapshot size (complete write)
- fsync + `os.replace` of the snapshot file
- `os.rename` of `.tmp-*` to the published run dir
- `run.json` + `physical_system_snapshot.json` present
- no leftover `.part` / `.tmp-*` under the size-test run dirs

Controlled failure: **0** published `psyweb-*` dirs with `run.json`. Live staging under the failure dest is unpublished `.live-*` only.

## 9. Restore result

For every size: `TwoAgentRuntime.restore` tick match, two slots, `pe.ensure_class_indexes` + `active_class_count == scan_active_class_count`, `smc.ensure_indexes`, one subsequent `step()` (`tick+1`).

## 10. Controlled failure

Injected `MemoryError` in `write_finalized_run` (no host OOM):

- session `SAVE_FAILED` (not stuck `FINALIZING`)
- backend process alive; runtime tick still 3
- job `lifecycle=SAVE_FAILED`, `layers.save=failed`, `layers.http=n/a_server`
- error string: `injected aged-save verification`
- no valid published run

## 11. Repeated-save memory

Three `write_finalized_run` cycles on one MEDIUM-occupancy runtime:

| i | before MB | after GC MB |
|---|---|---|
| 0 | 105.30 | 111.46 |
| 1 | 111.46 | 113.44 |
| 2 | 113.44 | 113.45 |

+8.15 MB vs first baseline, then flat. Consistent with pymalloc arena retention, **not** an unbounded live snapshot leak.

## 12. Files changed

Persistence production code: **unchanged** (verification did not require a new fix).

| Path | Role |
|---|---|
| `experiments/run_beta3_aged_save_memory.py` | disposable harness (child RSS sampler + sizes + API + failure + repeat) |
| `docs/BETA3_AGED_SAVE_MEMORY_TEST.md` | this report |
| `results/beta3_aged_save_memory/` | `summary.json`, per-size `child_result.json` / `parent_wrap.json`, published disposable runs |

`GIT_PUSH=NO`. Forensic live directory not modified.

## 13. Acceptance table

| Gate | Result |
|---|---|
| AGED_STATE_CONSTRUCTED | **PASS** (real constructors/schemas; ticks not 10231; jsonl synthetic not forensic 677 MB) |
| STREAMING_PATH_VERIFIED | **PASS** (`json.dump`; `.part` size = final file; no snapshot `dumps`/`BytesIO`) |
| NO_FULL_JSON_DUPLICATE | **PASS** |
| AGED_SAVE_COMPLETES | **PASS** |
| PEAK_RSS_MEASURED | **PASS** (in-child 20 ms + parent `/proc`) |
| MEMORY_AMPLIFICATION_BOUNDED | **PARTIAL** (no JSON triplication; still ~2× RSS from snapshot `deepcopy`; ΔRSS/file ~8 because object graph ≠ UTF-8 file) |
| ATOMIC_PUBLISH | **PASS** |
| AGED_RESTORE | **PASS** |
| P0_INDEX_REBUILD_AFTER_RESTORE | **PASS** |
| ASYNC_SAVE_JOB | **PASS** |
| CONTROLLED_FAILURE_RECOVERY | **PASS** |
| NO_STUCK_FINALIZING | **PASS** |
| REPEATED_SAVE_NO_LIVE_OBJECT_LEAK | **PASS** (RSS plateau after first save) |
| READY_FOR_REAL_LONG_RUN | **PARTIAL** |

## 14. READY_FOR_REAL_LONG_RUN

**PARTIAL.**

Facts that support a real long run vs t10231:

- Streaming write is real (`.part` tracks the file; finalize does not reload the snapshot).
- HTTP Save & Stop can return in milliseconds; SAVE vs HTTP layers are distinct.
- FINALIZING cannot stick on injected save failure.
- Incomplete output is not published.
- Disposable states larger in PE-FORGOTTEN occupancy than a naive early runtime saved at **~1.0 GB peak RSS**, not 14 GB.

Facts that keep it PARTIAL:

- Save still holds **live runtime + deepcopy snapshot** for the whole `json.dump`.
- Peak/baseline grew to **2.38×** at EXTREME and stayed there after GC.
- Forensic live RSS was ~3.5 GB. The same 2.4× multiplier would predict **~8 GB** peak if cognition dominates that RSS — safer than 14.6 GB on this 24 GB host, still unsafe if live RSS is higher or the host is smaller.
- Pretty-print `indent=2` makes large snapshots slow (minutes possible) even when RAM is bounded.

No persistence redesign was applied in this task. The remaining knob, if a later isolated fix is wanted, is `PhysicalSystemRuntime.snapshot` cognition copying — not PE/SMC matching semantics.
