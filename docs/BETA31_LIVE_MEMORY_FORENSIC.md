# Beta 3.1 live-run memory forensic

Two evidence streams. They are not interchangeable.

## Owner attribution (same live PID 368895)

Read-only. No restart, POST, compact, or attach.

**RSS growth is CONFIRMED** across three windows on this process:

| ticks | ΔRSS | MB / 1000 ticks | MB / tick |
| --- | --- | --- | --- |
| 5398→5574 | +118 MB / 176 | 672 | 0.67 |
| 6538→6598 | +39 MB / 60 | 644 | 0.64 |
| 9105→9204 | +61 MB / 99 | **614** | **0.61** |

At ticks 9105–9204: RSS 5893→5954 MB. `RssAnon` rose by the same **60.82 MB**. `[heap]` anonymous stayed **19.32 MB, Δ0**. Mapping count stayed **507**. Thirty-two anonymous `rw-p` regions (~192 MiB aligned) hold **~5767 MB RSS** and are filling in place.

That is allocator/native high-water (thread/arena mmap), not a growing `[heap]` of retained Python objects, and not SMC/PE/FPV/WS.

### Store table (live V3 JSONL + Observer GET; both agents)

SMC from `scientific_decisions.jsonl` tails (production occupancy on the live run):

| store | agent | tick | entries | est. bytes | Δentries/tick | Δbytes/tick | cap | eviction | bound |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SMC | 0 | 9107 / 9203 | 256 / 256 | ~1.28 MB / ~1.28 MB | 0 | 0 | 256 | occupancy evict | bounded |
| SMC | 1 | 9107 / 9203 | 256 / 256 | ~1.28 MB / ~1.28 MB | 0 | 0 | 256 | occupancy evict | bounded |
| Observer `_buffer` | session | 9105 / 9204 | 512 / 512 | latest frame JSON ~672 KB (not ring sum) | 0 | ~0 | 512 | deque | bounded |
| Observer timeline | session | | 4096 | bounded | 0 | | 4096 | deque | bounded |
| FPV/Eye | session | | 1 latest | ~55 KB | payload Δ −279 B | | latest-wins | replace | bounded |
| WS | session | | last_text | one frame | | | latest-wins | replace | bounded |
| V3 RAM buffers | session | | flushed | queue ~0 | | | 50k lines | flush_every 32 | bounded RAM |
| V3 decisions **disk** | run | | append | 638→646 MB file | | **~75 KB/tick disk** | none | append | unbounded disk |
| identity_map | run | | 2 bodies | 1048 B | 0 | 0 | lifecycle | | bounded |
| canonical_history | | | not resident | Analyzer-only | | | | | not in live RAM |

Predictive compression / PE / prospection: compact LIVE `/api/mind` is **2676 B** and does not dump those maps. Reproduction at t=60 showed them filling toward documented caps (PC recent 128, structures 64, PE 32 classes, prospection 128). They cannot produce 0.61 MB/tick after cap. Live SMC `updates` equals tick (9107) while occupancy stays 256 → eviction is active.

### Slope vs 0.65 MB/tick

Window 9105–9204: **0.614 MB/tick**. Named stores above explain **~0%** of that delta. **100%** of the delta is `RssAnon` / large anonymous mmap arenas.

Disk V3 grew **8.9 MB / 99 ticks ≈ 0.09 MB/tick** (not RSS; `RssFile` stayed 28.31 MB).

### Python retained heap vs RSS

`[heap]` Δ = **0 MB / 99 ticks** → **PYTHON_RETAINED_HEAP_MB_PER_1000_TICKS = 0.0** on the process brk heap.

Full pymalloc/mimalloc *reachable* object graph was **not** traced (no attach). Classification of the 6 GB RSS: **allocator/native/high-water**, fed by per-tick construction churn (V3 `json.dumps` ~32–42 KB × 2 agents, Observer `ndarray.tolist`, NFE sample dicts). Freed objects need not return those 192 MiB arenas to the OS.

### Spatial Vision combinatorial test (live, not disabled)

All sampled observation receipts have **exactly 68 keys** (head 300, tail 400, both samples). Spatial family is on for the whole JSONL. Unique **signatures** are essentially 1 per row (value diversity), but **key-set cardinality is 1** (no extra channel explosion). SMC occupancy is already at 256 for both agents — further unique signatures evict, they do not grow RAM occupancy.

**SPATIAL_VISION_COMBINATORIAL_GROWTH = PARTIAL** (wider 68-ch records vs 48; unique values every tick) **not** unbounded extra keys, **not** the RSS slope.

### Duplicate representations of one tick

Persistent by design: SMC (capped), compression recent (capped), PE/prospection (capped), V3 JSONL on disk, Observer compact frame + 512-ring, FPV latest payload.

Transient: accessible observation / last_fragment (replaced each tick), V3 write buffers (flushed), WS last_text.

Not found: full historical V3 duplicated in RAM; FPV history; growing WS queue.

### FPV / Observer

Live Eye still **2FPS + FPV**, payload **~55 KB**, `update_count` +53 / 99 ticks (rate-limited). Payload size did not grow. Did **not** POST OFF (would not change science, but would change that Observer diagnostic). Server-side: `_eye_last_payload` latest-wins; `_buffer` at cap 512; state GET **shrunk** 3.7 KB.

## CURRENT LIVE RUN EVIDENCE

Inspected **without** reset, restart, Save & Stop, store compact, or mechanism changes.

| Field | Value |
| --- | --- |
| Instance | `9a8d195a180b420892a046041df0acaf` |
| URL | http://127.0.0.1:8768/ |
| Server PID | 368895 |
| Owner PID | 368875 |
| Runtime | TwoAgentRuntime · seed 373 / 374 · `RUNNING` |
| Agents | 2 |
| R | 3 |
| Surface | RICH |
| Optical mapping | **INDEPENDENT** (live actual; not CORRELATED) |
| Spatial vision | OCCLUSION, 5 bins |
| PSC motor resolution | OBSERVED_COMPOSITE |
| Evidence | FULL_SCIENTIFIC |
| Observer detail | MINIMAL |
| Eye at inspect | 2FPS + FPV on (~55 KB latest payload) |

Process samples (`results/beta31_live_memory_forensic/process_samples.json`):

| i | tick | RSS_MB | VMS_MB | PSS_MB | tps | threads | fds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 6538 | 4540.14 | 5736.40 | 4516.29 | 2.5 | 22 | 16 |
| 1 | 6566 | 4546.71 | 5802.40 | — | — | — | — |
| 2 | 6598 | 4578.75 | 5828.40 | — | — | — | — |

Earlier independent window (ticks 5398–5574, 176 ticks, 78 s): **+118.27 MB → 672 MB / 1000 ticks**.

Later window (ticks 6538–6598, 60 ticks): **+38.61 MB → 643.5 MB / 1000 ticks**. Piecewise in that window: +6.57 MB / 28 ticks then +32.04 MB / 32 ticks.

The two windows agree on order of magnitude (~640–670 MB / 1000 ticks). That is still a short-run slope on a ~4.5 GB process, not a single-point leak claim.

Current live evidence directory (mtime match):

`results/psychology_observer/psy_observer_web/.live-psyweb-20260923T121756.427328Z-7efa948d` ≈ **543 MB on disk**.

Largest file: `scientific_decisions.jsonl` ≈ **446 MB**. Identity map on disk ≈ 1 KB. V3 streams to JSONL; RAM writer queue is flushed (flush_every 32, max_queue_lines 50_000).

`CURRENT_RUN_RESTARTED = NO`. `CURRENT_RUN_MUTATED_BY_FORENSIC = NO` (read-only `/proc` + GET). Occupancy GET was skipped to avoid a diagnostic deepcopy on the live process.

## REPRODUCTION EVIDENCE

Separate in-process `ObserverSession` (seed 373, two agents, FULL_SCIENTIFIC, OCCLUSION). Never attached to PID 368895.

| tick | obs keys | spatial keys | SMC n (a0/a1) | PC raw_log | PE classes | prosp. transitions | published_json_kb | v3 queue |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 37 | 0 | 0/0 | 0 | 0 | 0 | 753 | — |
| 30 | 68 | 20 | 24/26 | 29 | 0 | 72/77 | 501 | 20 |
| 60 | 68 | 20 | 28/33 | 59 | 0 | 81/95 | 517 | 0 |

LEGACY same 60 ticks: 48 observation keys, 0 spatial keys, SMC 32/34 (similar counts, **smaller per-record JSON** ~3.1k vs ~5.1k sample).

Cognition stores are **capacity-bounded** (SMC 256, PC structures 64 / recent 128, PE classes 32, prospection transitions 128). They cannot explain 4.5 GB RSS.

## Owners (updated after attribution)

**PRIMARY_MEMORY_OWNER:** native **anonymous mmap arenas** (~32 × 192 MiB `rw-p` regions, ~5.8 GB RSS). Mapping count stable; RSS rises as arenas commit. ΔRSS = ΔRssAnon. Not SMC, not FPV, not `[heap]`.

**PRIMARY_OWNER_MB_PER_1000_TICKS:** **614** (ticks 9105–9204).

**SECONDARY_MEMORY_OWNER:** per-tick **allocation churn** that feeds those arenas — especially V3 decision JSON (~75 KB/tick disk from 32–42 KB JSON × 2 agents) and Observer world `tolist` / NFE dict construction. Disk itself is not RSS (`RssFile` flat).

**SECONDARY_OWNER_MB_PER_1000_TICKS:** not a retained store slope; **~90 MB/1000 ticks disk** for all V3+timeline files in this window.

**EXPLAINED_RSS_FRACTION:** ~**1.0** of measured ΔRSS is anonymous arena commit; ~**0.0** is capped cognition/Observer/FPV/WS stores.


**Eye/FPV:** latest-wins. OFF → no FPV. 2FPS/5FPS/PER_TICK → ~60 KB payload, `prev_fpv_keys=2`. Does not accumulate historical receipts. Live run currently requests 2FPS FPV (~55 KB); that is not the 4.5 GB RSS.

**WebSocket:** `hub.last_text` latest-frame. No unbounded server queue found.

**Spatial Vision:** Live JSONL always 68 keys; unique key-set = 1. SMC both agents at cap 256. Wider records vs LEGACY 48, not unbounded extra channels. Not the RSS slope.

**Python heap vs RSS:** live `[heap]` Δ = 0. Tracemalloc on reproduction still only tens of MB; live RSS is gigabytes of anonymous arenas.

## Classification of growth

| Kind | Finding |
| --- | --- |
| A legitimate scientific history | V3 JSONL on disk (unbounded file); SMC/PE/PC/prospection bounded |
| B stores at cap | **SMC 256/256 both agents** by tick 9107; Observer ring 512/512 |
| C allocator / RSS high-water | **PRIMARY.** ~0.61 MB/tick anonymous mmap arenas; mapping count 507 stable |
| D duplicate representations | same tick exists as SMC + V3 disk + compact Observer frame; FPV latest only. **Not** an unbounded RAM duplicate of history |
| E unreachable leak | **not evidenced** as a named Python store |
| F unbounded queues | **not evidenced** in RAM (V3 flushed; WS/FPV latest). Unbounded **disk** JSONL yes |

## Allocation churn (reproduction only)

Same live PID **368895** was not profiled with tracers, `malloc_trim`, or config changes.

Reproduction: seed 373, 2 agents, R3/RICH/OCCLUSION, warmup 20 + window 50 ticks, isolated child processes.

| condition | RSS MB/1000 | JSON MB/tick | t/s | malloc_trim release MB |
| --- | --- | --- | --- | --- |
| A full V3+Observer | 5500 | 1.002 | 0.50 | 113 |
| B V3 off (SEARCH_COMPACT) | 5493 | 0.961 | 0.52 | 114 |
| C Observer frame suppressed | **990** | 0.043 | 0.77 | 17 |
| D FPV OFF | 5501 | 0.845 | 0.55 | 129 |
| E HEADLESS + no frame | 909 | 0.043 | 0.77 | 16 |
| F V3 capture, no encode/write | 5498 | 0.973 | 0.49 | 112 |
| F2 V3 encode, no disk | 5497 | 1.000 | 0.49 | 112 |
| G Spatial LEGACY | 5982 | 0.968 | 0.61 | 145 |

JSON site split (A): Observer session **0.957 MB/tick**, V3 writer **0.033 MB/tick**, V2 history **0.007**, receipts hash negligible. `live_frame` dict estimate **0.73 MB/tick**. Max dump **841 KB**.

V3 one-tick (2 agents, early window): ~20 KB receipts → ~27 KB JSONL/tick. Producing live’s ~90 MB/1000 ticks of JSONL does **not** require hundreds of MB of extra RSS vs Observer frames (B/F/F2 ≈ A).

`gc.collect()` after stopping ticks: RSS unchanged. `malloc_trim(0)` on the **reproduction** process only: **−113 MB**. Allocator retained free pages. Live was not trimmed.

Young reproduction: mapping count +6–7, large anon 1→3, Private_Dirty = RssAnon. Aged live: mapping count stable, existing anon maps commit pages.

Allocator: CPython 3.12.3 **pymalloc** + **glibc ptmalloc** (`libc.so` only; not jemalloc/tcmalloc/mimalloc). ~840 KB JSON strings bypass pymalloc.

SAFE source tweaks (not loaded by PID 368895): `_flat_grid` single `ravel().tolist()`, JSONL flush without `"\\n".join`, skip utf-8 copy for published-frame byte count. After RSS **5488** vs before **5500** (no fill-window win). Next-run leverage is demand-driven JSON / not retaining 512 full world-list frames.

## SAFE vs next-run


No change was applied inside PID 368895. Observer demand-driven publication + 1 full WORLD frame is in the source tree for the **next** process (`docs/BETA31_OBSERVER_FRAME_MEMORY_FIX.md`).

**SEMANTICS_SENSITIVE:** SMC/PE/prospection/PSC/spatial family/V3 receipt contents / `_json_hash`.

Artifacts: `results/beta31_live_memory_forensic/` and `results/beta31_observer_frame_memory_fix/`.
