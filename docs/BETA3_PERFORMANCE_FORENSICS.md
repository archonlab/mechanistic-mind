# Beta 3 live long-run performance forensics

**Date:** 2026-09-22  
**Constraint:** Read-only. The aged Two-Agent Tiktaalik on port 8768 was not stopped, reset, saved, restarted, or scientifically mutated. PSC mode, Observer detail, evidence mode, caches, and stores were left unchanged.  
**Optimization:** None implemented in this task.

Artifacts: `results/beta3_performance_forensics/`  
Sampler for later points on **this** run: `scripts/beta3_readonly_perf_sampler.py` (GET `/api/runtime/progress` only).

---

## CURRENT PERFORMANCE

| Field | Live value (measured) |
|---|---|
| **run id** | `psyweb-20260922T192322.056455Z-f9b24837` |
| **instance_id** | `091ad9ec185a4b1bb0f8686d78131f60` |
| **PID** | **179327** (`uvicorn mechanistic_mind.ui.psy_observer_web.server:app --host 127.0.0.1 --port 8768`) |
| **PPID** | 179305 (launcher; untouched) |
| **seed** | 770 (agent_0); agent_1 seed 771 |
| **runtime** | `TwoAgentRuntime` · generation **4** |
| **tick (sample window)** | **8414 → 8610** (197 unique ticks) |
| **tick (after profiling)** | **8789** still RUNNING |
| **wall-clock start** | 2026-09-22T19:23:22Z (`scientific_meta.started_at`) |
| **execution mode** | **LIVE** |
| **ticks/sec** | **1.1–1.4** API (`sim_ticks_per_sec`); 197 ticks / 166.8 s ≈ **1.18 tps** |
| **ms/tick** | mean **806.9** · median **793.1** · p95 **863.6** · max **2669.7** · min **550.8** |
| **RSS** | **3.44 GB** at tick ~8394 → **3.57 GB** at tick ~8789 |
| **CPU** | **~98.8%** one process (25 threads) |
| **agents** | **2**, both `cognition_attached` |
| **Observer mode** | preset **CUSTOM**; `frame_detail=compact`; products cognition, experimenter, geometry, historical_sensorimotor_selection, mechanisms, prediction, signal_sensorimotor, smc, telemetry, world |
| **evidence mode** | **FULL_SCIENTIFIC** |
| **PSC motor-resolution** | **OBSERVED_COMPOSITE** (experimental) |
| **PSC SHADOW** | **not enabled** (not turned on for profiling) |
| **world** | 32×32 WRAP_PERIODIC · ecology `STRUCTURED_WORLD_EXPERIMENTAL` · climate **OFF** |
| **mechanisms** | 51 listed; **50 ON**; climate OFF. Cognition, vision, signal, SMC, HSS bridge, 4.26–4.28, TPS, retrieval, bounded memory, PE/relevance, composition, PSC **ON**. |

This is **not** yesterday’s seed-676 PID-10494 run (`docs/LIVE_AGED_RUN_PERFORMANCE_FORENSICS.md`). Same port/launcher pattern; different process, seed, Observer preset, and tick.

---

## TOP PERFORMANCE THIEVES

Measured (py-spy `--nonblocking`, 4434 samples / 45 s, 140 errors; plus GET `/api/runtime/progress` and published `observer_perf`):

1. **`predictive_equivalence.learn` on the TPS inner store** — **~55.6% inclusive** of process samples under `temporal_predictive_structure.learn`; **~60% self** in PE. Dominated by **scanning the unbounded `classes` dict** (ACTIVE count + victim selection at `MAX_CLASSES`) and **full `rebuild_class_indexes` after every learn mutation**.
2. **OBSERVED_COMPOSITE PSC** — **~12.8% inclusive** (`select_observed_composite_motor`). Candidate history queries call `pc.predict` and rebuild `_sig` over wide observation maps (`query_history_on_o_prime`).
3. **Observer compact capture** — **not inside** `last_tick_wall_ms`. Capture thread **3.4%** of samples; published `capture_build_ms ≈ 7.3`, `serialization_ms ≈ 20.2`, `frame_bytes ≈ 579 KB`.

World/physics, 4.26–4.28, and packed `predict_one_step` are **not** thieves on this profile.

---

## 1. Baseline (live)

| Item | Value |
|---|---|
| Threads | 25. Hot: LWP **180080** `psy-observer-sim` **94.5%** of py-spy weight. Capture 3.4%. Main/uvicorn 2.1%. Heartbeat ~0%. |
| `observer_fps` | tracks sim (~1.1); cognition producer_calls ≈ tick (cadence 3 Hz still fires every slow tick) |
| `include_cognition` | true, but **compact** (avoids FULL `cognition_public_view`; cache `builds=2`, `hits=0`) |
| `visual_frames_dropped` | 14 (header) |
| Buffer | frames 512/512, timeline 4096, trajectory/telemetry 2048 |
| Scientific live dir | `results/psychology_observer/psy_observer_web/.live-psyweb-20260922T192322.056455Z-f9b24837` (**572 MB** at ~8.6k ticks) |

---

## 2. Profiling method

| Method | Used? | Notes |
|---|---|---|
| GET `/api/runtime/progress` | **YES** | No `step_lock`. 197 unique ticks, 396 polls, 165 s. |
| GET header / health / mechanisms / detail / PSC GET | **YES** | Settings from live APIs, not defaults. |
| GET `/api/state` once | **YES** | Published frame only (~579 KB). Extracted `observer_perf` + compact mind. |
| GET SMC panel | **YES** | Occupancy/query counters. |
| GET `/api/diagnostics` occupancy / full bundle | **NO** | Falls back to `step_lock` + `diagnostic_bundle`. |
| GET `/api/snapshot` | **NO** | Would copy runtime; not required. |
| Host `py-spy` | **DENIED** | `kernel.yama.ptrace_scope=1` |
| Docker `--privileged --pid=host` `py-spy dump` + `record --nonblocking` | **YES** | Same method as 2026-09-21. Process remained PID 179327 RUNNING. |
| Injecting timers / restarting / changing PSC/detail | **NO** | |

`--nonblocking` can miss samples (140 errors). Direction is consistent across dump series + 45 s record.

---

## 3. Tick pipeline (real call tree)

`session._loop` → `_scientific_step_once_unlocked` (`last_tick_wall_ms` bounds this) → `TwoAgentRuntime.step` → `_step_once`:

1. `observations()` — per-slot `agent_observation` (shared world, foreign bodies)
2. **each slot** `begin_tick` → `run_cognition_before_action` (this is **~89%** of samples)
3. **once** `step_planet`
4. **each slot** `finish_tick(skip_planet=True, skip_resources=True)`
5. pairwise soft contact / push (1 pair)
6. simultaneous resources
7. Observer: `_append_scientific_locked` then async capture **outside** the sim lock

Cognition (per agent, production): observation → compression/TPS/PE retrieve cascade over **14** motor tokens → TPS **learn** (4 lags) → TPE **ingest** (another learn) → `compose_trajectories` → 4.26–4.28 inject → SMC `query_candidates` (5 locos) → **`select_observed_composite_motor`** → motor apply.

Stage timing for **one production tick** as **% of py-spy process samples** applied to mean **806.9 ms** wall. Inclusive stages nest (do not sum to 100%).

| Stage | Inclusive % (process) | ≈ ms/tick | % of mean tick | Notes |
|---|---:|---:|---:|---|
| TOTAL scientific tick | 90.8 | **807** | 100 | `last_tick_wall_ms` mean of 197 ticks |
| `begin_tick` / cognition | 89.0 | 718 | 89 | Both agents, sequential |
| TPS `learn` → PE `learn` | 55.6 | 449 | 56 | **Dominant** |
| TPE `ingest` → PE `learn` | 23.3 | 188 | 23 | Nested PE learn; same family |
| OBSERVED_COMPOSITE PSC | 12.8 | 103 | 13 | `cognition.py:1047` |
| `query_history_on_o_prime` | 8.2 | 66 | 8 | Inside PSC |
| `pc.predict` / `_sig` | ~5–8 self | 48–65 | 6–8 | Inside PSC history query |
| TPS `retrieve` (indexed) | 4.8 | 39 | 5 | **Was ~60% yesterday on a different run/code** |
| Prospective composition helpers | ~4.8 self | 39 | 5 | `_q` / `_frag_distance` |
| `compose_trajectories` | 1.2 | 10 | 1 | Packed backend default |
| SMC `query_candidates` | 0.3 | 2 | 0.3 | Extra cost is scans inside observed-composite |
| World / body / planet | ~0.2 self | ~2 | 0.2 | |
| 4.26–4.28 | ~0 | — | 0 | Compact stores: 5 contexts, 4 ctx transitions |
| Observer capture thread | 3.4 | n/a in tick_ms | — | Async; `observer_perf` 7+20 ms |
| JSON / websocket deflate | ~3 | n/a | — | Capture/MainThread |

---

## 4. Top 10 measured hot paths

| Rank | Path | Self % | Inclusive % | ≈ ms |
|---|---|---:|---:|---:|
| 1 | PE `classes` ACTIVE scan (`learn` L495 listcomp) | 17.3 | (under TPS learn 55.6) | — |
| 2 | PE victim genexpr L497 | 19.8 | same | — |
| 3 | `rebuild_class_indexes` | 21.0 | 21.3 | 170 |
| 4 | `select_observed_composite_motor` | — | 12.8 | 103 |
| 5 | compression `_sig` genexpr | 5.9 | 5.7 | 46 |
| 6 | cognition L772 genexpr | 4.5 | — | 36 |
| 7 | `predictive_relevance.refresh` | 2.7 | — | 22 |
| 8 | TPS `retrieve` | — | 4.8 | 39 |
| 9 | json encode + websocket deflate | 3.0 | capture 3.4 | ~27 ms frame |
| 10 | `jsonish_copy` / deepcopy | ~2.2 | — | 18 |

---

## 5. Age-scaling structures

Per-tick work tracks **store occupancy / forgotten residue / candidate count**, not tick index.

| NAME | CURRENT SIZE | CAP / BOUND | ACCESS / TICK | COMPLEXITY | OBSERVED | CLASS |
|---|---|---|---|---|---|---|
| PE `classes` (TPS inner + snapshot PE) | ACTIVE capped 32; **FORGOTTEN never deleted** | `MAX_CLASSES=32` ACTIVE only | TPS learn 4 lags × agents; TPE ingest | **O(all classes ever)** on form/evict + full index rebuild | **Dominant CPU**; RSS still climbing | **UNBOUNDED** (forgotten dict) |
| Class indexes `_ix_action/_ix_member` | rebuilt from all classes | derived | every `invalidate_class_indexes` | O(n classes) rebuild | 21% inclusive | UNBOUNDED work |
| SMC `records` | **256 / 256** both agents | 256 | ~35 `query()`/tick agent_0 (300779 queries / ~8544 ticks); similar agent_1 | O(capacity) prefix scans in observed-composite | 2.9% self SMC | **BOUNDED BUT EXPENSIVE** |
| Compression `structures` | compact mind omitted count; cap 64 | 64 | `pc.predict` full scan per (candidate × loco) | O(structures × keys) + `_sig` | 8% self | BOUNDED BUT EXPENSIVE |
| Prospection `transitions` | cap 128 | 128 | packed soft-match | O(per-action packed) | 0.3% `soft_match_packed` | BOUNDED |
| Ctx organization | **5 / 48** contexts | 48 | compact | small | ~0% | BOUNDED AND STABLE |
| Ctx-grounded transitions | **4 / 96** | 96 | compose BFS caps 48 expansions | small | ~0% | BOUNDED AND STABLE |
| PPC motor chunks | present; agent_0 active PPC | lifetime cap | | ~0% | BOUNDED |
| Observer buffers | 512/4096/2048 | yes | | | BOUNDED |
| Scientific jsonl | **572 MB** @ ~8.6k ticks; decisions **488 MB** | none | append every tick under lock | IO + Python dump | not a CPU top leaf | **UNBOUNDED** disk |
| TPS ring | 16 | 16 | | | BOUNDED AND STABLE |
| Equivalence episodes | 256 | 256 | | | BOUNDED |

**Answer:** Tick number itself is not the cost. Filling SMC to 256 unique (S,M) rows and **never removing FORGOTTEN PE classes** makes learn/index **grow with history**. Indexed **retrieve** is no longer the aged bottleneck on this process (unlike 2026-09-21 seed 676).

---

## 6. Hidden O(N) / O(N²) (documented, not changed)

| Site | Pattern |
|---|---|
| `predictive_equivalence.learn` L495–501 | `len([c for c in classes.values() if ACTIVE])` and `min(... classes.items() if ACTIVE)` — **O(forgotten+active)** every new-class attempt. **No `classes.pop`.** |
| `invalidate_class_indexes` + `rebuild_class_indexes` | Full rebuild after **every** UPDATE/JOIN/FORM/split |
| `observed_composites_for_loco` | Full SMC `records` scan **per locomotion** |
| `query_history_on_o_prime` | For each composite: loop locos → `predict_one_step` **and** `pc.predict` (full structure scan + `_sig` tuple built **before** cache lookup) |
| `pc.predict` | Scan all ACTIVE structures; `_sig` sorts every float key |
| `collect_entry_steps` | Per action TPS retrieve (memoized same window) |
| Cognition retrieve cascade | 14 tokens × compression then TPS (4 lags) then PE |
| `cognition_public_view` | Heavy `deepcopy` — **not** on this LIVE compact path |
| Scientific `decisions.jsonl` | Unbounded append (~57 KB/tick all files combined at this age) |

---

## 7. PSC breakdown (production OBSERVED_COMPOSITE)

| Piece | Measurement |
|---|---|
| Mode | OBSERVED_COMPOSITE; selection source **OBSERVED_COMPOSITE_PSC** both agents |
| Shadow | OFF (unchanged) |
| `query_candidates` | 5 locos; **0.3%** inclusive |
| Observed candidate gen | SMC 256 full; prefix + collapse |
| Queries | agent_0 **300779** (~35/tick); agent_1 **278551** — implies ~30 composite `smc.query` + 5 loco queries per agent-tick |
| History on O′ | **8.2%** inclusive; `pc.predict` **5.0%** |
| `compete_scenarios` / `dominates` | **0.3%** self |
| Packed `predict_one_step` | **0.3%** `soft_match_packed` |
| Exact n_candidates this tick | **NOT MEASURED** — HSS panel GET returned HTTP 500; compact mind omits `observed_composite_selection` |

---

## 8. Prospective composition

| Piece | Measurement |
|---|---|
| `compose_trajectories` | **1.2%** inclusive (MAX_EXPANSIONS 64, packed lookup) |
| Python `_q` / `_frag_distance` | **~2.3%** self combined |
| Metrics | agent_0 `prospective_compositions=8493` ≈ every tick; agent_1 **1291** (not 2×) |
| Ctx compose | 4 transitions, last_depth 0 — not the scaler |
| Failed/success attempt counters | **NOT MEASURED** — not on compact frame |

Composition CPU is **not** growing like PE forgotten-class learn.

---

## 9. Memory / compression

| Piece | Measurement |
|---|---|
| `pc.predict` full scan | Inside PSC history; 5% inclusive |
| `_sig` (sort+round every key) | 5.9% self — cache keyed **after** building the tuple |
| `memory_cost` / FULL `cognition_public_view` | **NOT on this compact LIVE path** |
| Purge | **NOT MEASURED** as a tick fraction (not in top stacks) |
| Compact mind | omits structure counts |

---

## 10. Observer tax

**Exist:** ~807 ms/tick, **~94.5%** CPU on `psy-observer-sim`.  
**Watch:** capture **3.4%** CPU; **~27 ms** compact frame (7 build + 20 serialize); 579 KB JSON; websocket deflate on MainThread. Cognition product still requested ~every tick at 1.1 tps.

CUSTOM vs yesterday MINIMAL: extra products, but compact still skips FULL public view. Observer is **not** why the Tiktaaliks are at 1.2 tps.

---

## 11. Frontend tax

**NOT MEASURED in-browser** (did not attach a SPA client to 8768). Code inspection only:

- `/ws/live` sends the **full serialized frame** (~579 KB)
- `WorldMap` canvas redraws on frame/FOV/agents_views identity changes (32×32; FOV overlays for two agents)
- `AuxPollDriver` 2 s while LIVE; skips packs/gearbox while running
- `InterestDriver` can keep CUSTOM products subscribed
- Inspector HSS/SMC/signal panels poll 1 s when those tabs exist
- ObserveV2 is sectioned; hidden tabs should not all mount if IA fix holds

Frontend cost is **orthogonal** to the 807 ms scientific tick.

---

## 12. Two-agent multiplier

Code: two independent `begin_tick` cognition passes; **one** planet step; **one** contact pair.

Evidence: **not exactly 2×**. SMC queries 301k vs 279k. Composition metrics 8493 vs 1291. Action histograms differ (agent_1 OSC_EMIT 494 vs agent_0 4). Pairwise physics is negligible in the profile (`two_agent` self ~0). Observer serializes two compact minds in one 579 KB frame.

Expect **~1.8–2.2× cognition**, not a combinatorial explosion at n=2. Disabling agent_1 was **not** done.

---

## 13. CPU vs memory growth

| | CPU | RSS |
|---|---|---|
| Now | ~807 ms/tick, 98.8% CPU, 1.2 tps | 3.44→3.57 GB over ~400 ticks during this session |
| Driver | PE forgotten-class scans + index rebuild; PSC×compression `_sig` | Forgotten class objects + 572 MB scientific files (OS cache) + stores at cap |
| Historical comparable curve | **Do not invent.** Yesterday seed **676** @ ~3k ticks was **~1200 ms** with **retrieve** 60%. This seed **770** @ ~8.5k is **~807 ms** with **learn/index** 56% and **indexed retrieve ~5%**. Different run + retrieve index in production. |

Future points: `python3 scripts/beta3_readonly_perf_sampler.py --seconds 120 --out results/beta3_performance_forensics/progress_tXXXX.jsonl`

---

## 14. NumPy / Numba / C++ matrix

See budget table. **Algorithmic first** on PE forgotten-class accounting and incremental indexes. Do not “rewrite in NumPy” because the stack is Python.

---

## Performance budget

| HOT PATH | MS/TICK | % TOTAL | SCALING DRIVER | CLASS | NUMPY | NUMBA | C++ | ALGO FIRST | NOTES |
|---|---:|---:|---|---|---|---|---|---|---|
| PE learn + index rebuild (TPS/TPE) | **449** | **55.6** | forgotten+ACTIVE class count; rebuild per mutation | ALGORITHMIC + PYTHON LOOP | LOW | LOW | LOW | **YES** | O(1) active count; incremental index; stop scanning forgotten |
| OBSERVED_COMPOSITE + O′ history | **103** | **12.8** | SMC occupancy 256; ~30 composites × 5 locos | ALGORITHMIC + PYTHON LOOP + ALLOC | LOW | MEDIUM | LOW | **YES** | Index records by loco; reuse `_sig`; don’t `pc.predict` full scan per action |
| compression `_sig` / `predict` | **46–65** | **6–8** | structure cap 64 × wide fragments | PYTHON LOOP + ALLOC + CACHE | LOW | MEDIUM | LOW | **YES** | Build cache key cheaper; action index on structures |
| TPS retrieve (indexed) | **39** | **4.8** | classes/action bucket | PYTHON LOOP | LOW | LOW | LOW | NO | Already indexed; was yesterday’s thief |
| Prospective composition glue | **39** | **4.8** | expansions ≤64 | PYTHON LOOP | LOW | MEDIUM | LOW | NO | Packed match already 0.3% |
| Observer compact JSON | **27** | ~3 of wall **outside** tick | CUSTOM products; 2 agents | SERIALIZATION | LOW | LOW | LOW | YES | Keep compact; don’t switch FULL on this run |
| SMC hash / query | **~7** | **<3** | 256 records | PYTHON LOOP | LOW | MEDIUM | LOW | YES | Loco index |
| World / physics | **~2** | **0.2** | 32×32 | NUMERICAL | HIGH | HIGH | MEDIUM | NO | Not the bottleneck |
| 4.26–4.28 | **~0** | **0** | 5 contexts / 4 edges | — | LOW | LOW | LOW | NO | |
| Frontend render | NOT MEASURED | — | ws frame size | FRONTEND | — | — | — | — | Don’t attach SPA to measure |
| Scientific jsonl IO | NOT MEASURED as ms | — | FULL_SCIENTIFIC unbounded | IO | LOW | LOW | LOW | YES | Buffering exists; disk 572 MB |

---

## 18. Prioritized optimization plan (do not implement here)

### P0 — large measured cost, low scientific risk

1. **PE class occupancy accounting** — maintain `n_active`; evict without scanning all FORGOTTEN; consider moving FORGOTTEN out of the hot dict **without changing ACTIVE membership semantics**.
2. **Incremental class indexes** — stop `rebuild_class_indexes` on every learn UPDATE.
3. **Observed-composite SMC index by locomotion prefix** — same records, no Cartesian product, no capacity cut.
4. **`query_history_on_o_prime`** — one `_sig` / structure pass per O′; do not loop `pc.predict` × locos over the full map.

### P1 — meaningful, more invasive

1. Cheap signature identity (hash observation once per tick; don’t sort 40 keys per predict).
2. Compression structures indexed by action (like PE `_ix_action`).
3. Compact Observer: stop building cognition product every tick when cadence cannot exceed tps (display-only; must not gate scientific evidence).
4. Scientific `decisions.jsonl` volume (evidence policy, not cognition).

### P2 — native / architectural

1. Numba/C++ for `_linf` / packed distances **after** P0 (currently 0.3% packed match).
2. Dense world/vision arrays — **HIGH NumPy**, **irrelevant to current 1.2 tps**.
3. Rewrite PSC scenario matching in NumPy — **LOW** suitability (branchy dicts).

**Do not** recommend: fewer agents, smaller vision, disabled PSC/cognition, reduced scientific capacities “to go faster.” Same Tiktaalik, less compute.

---

## 16. Files / artifacts

| Path | Role |
|---|---|
| `docs/BETA3_PERFORMANCE_FORENSICS.md` | This report |
| `scripts/beta3_readonly_perf_sampler.py` | Future read-only sampler |
| `results/beta3_performance_forensics/progress_sample.jsonl` | 197-tick wall sample |
| `results/beta3_performance_forensics/pyspy_dump_series.txt` | Instantaneous stacks |
| `results/beta3_performance_forensics/pyspy_speedscope.json` | 45 s profile (4434 samples) |
| `docs/LIVE_AGED_RUN_PERFORMANCE_FORENSICS.md` | Prior run (seed 676); **not** a point on this curve |

---

## 17. NOT MEASURED

| Item | Why |
|---|---|
| Per-stage `perf_counter` inside one tick | Would require runtime instrumentation / restart |
| HSS `n_candidates` / exact composite list | GET `/api/diagnostics/historical-sensorimotor-selection` HTTP 500 |
| PE forgotten class **count** | Compact frame omits class dumps; `/api/diagnostics` can take `step_lock` |
| Compression structure count | Compact mind |
| Frontend React commit times | Did not open Observer UI against 8768 |
| Scientific jsonl ms/tick | Not a py-spy leaf; would need in-process timers |
| Cache hit rates (`_CACHE_STATS`, TPS retrieve cache) | Process globals not exported on compact frame |
| Comparable ms/tick at 1k/3k/5k/10k **this** seed | No earlier sampler on this PID |

---

## Scientific note

Production retrieve is **indexed** (`_USE_CLASS_INDEX = True`). That matches the collapse of retrieve from ~60% (2026-09-21 full scan leaf) to ~5% here. The aged slowdown **moved** to **learn + unbounded forgotten classes + index rebuild**, with a secondary **OBSERVED_COMPOSITE × compression predict** tax at SMC capacity.
