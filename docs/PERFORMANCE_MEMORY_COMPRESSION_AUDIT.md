# PERFORMANCE / MEMORY COMPRESSION AUDIT

**Date:** 2026-09-21  
**Scope:** Read-only architectural + runtime audit. **No optimizations implemented.**  
**Symptom under investigation:** ~1.5–2 s/tick near tick ~9000 with major cognition ON.

---

## 1. Executive diagnosis

**Central question:** After a higher-level compressed predictive structure forms, do its lower-level constituent fragments/relations continue to participate in ordinary PSC retrieval or composite search?

**Classification: B — LOWER LEVELS PARTIALLY RETIRED**

**Verdict line:** `COMPUTATIONAL_COMPRESSION_PARTIAL`

### What the code actually does

Mechanistic Mind does **not** run a single hierarchical memory that PSC expands.

There are **two parallel learned stores** fed from the same tick experiences:

| Store | Module | Role in ordinary cognition |
|-------|--------|----------------------------|
| `state["compression"]` | `mechanistic_mind/research/predictive_compression.py` | Bounded predictive structures; used by `pc.predict` in the **retrieval** loop |
| `state["prospection"]` | `mechanistic_mind/research/prospective_composition.py` | Bounded **transition** aggregates; used by `predict_one_step` / `compose_trajectories` / PSC |

For the **compression** store:

- Raw episodes are folded into `structures` (`_maybe_compress_transition`).
- `pc.predict` iterates **ACTIVE structures only** (capacity 64) — **not** `raw_log`.
- Each decision cycle ends with `pc.purge_redundant_raw(..., keep_recent=True)` when `bounded_memory` is on, physically deleting non-recent raw ids from `raw_log`.
- `expand_structure` is explicitly **researcher-side**, not agent cognition.

For **PSC / composition**:

- Soft match / compose operate on **transition rows** (`MAX_TRANSITIONS = 128`), each already an aggregate (`support`, `sum`, `var_sum`).
- Soft match does **not** re-open compression provenance, representatives, or purged raw fragments.
- Soft match **does** still compare the query against **peer transition rows** for the same action (bounded ≤128). That is sibling compressed transitions, not “every constituent of one structure.”

So: **storage compression of raw → structure is real and computationally retires raw from `pc.predict` and from PSC.**  
What is **not** present is a stronger hierarchical rule of the form “once structure P exists, never soft-match any transition that contributed to P.” Transitions remain independently eligible until capacity eviction.

### About the 1.5–2 s/tick claim

Prior measured science paths on this codebase **plateau near tens of ms/tick** after stores fill (`docs/PSC_COMPOSITION_PERFORMANCE.md`, `docs/LONG_RUN_OBSERVER_PERFORMANCE.md`, `results/live_optical_performance/`).  

A sustained **~1.5–2 s/tick** is **not explained** by unbounded re-scanning of compression constituents. Stronger matches from prior audits:

1. **Observer FULL / `cognition_public_view` amplification** (historically catastrophic via repeated `memory_cost` JSON serialization — partially mitigated by caches).
2. **Session evidence append / lock / UI** overhead (long-run Observer infra), not compression hierarchy failure.
3. Filled-store PSC work (`compose_trajectories` × full action repertoire) — **expensive but bounded**, typically ~25–45 ms/tick science in prior fills, not seconds.

This audit does **not** claim the user’s 9000-tick wall clock was mis-measured; it claims the **cause is not “compressed structures still expand all raw constituents every tick.”**

---

## 2. Actual runtime data-flow diagram

```text
observation (accessible fragment)
    │
    ├─► pc.observe(compression)                    [predictive_compression]
    │       append recent (≤128 ids)
    │       raw_log[id] = record
    │       _maybe_compress_transition → structures[key] (≤64)
    │           provenance / representatives / exceptions / PAE
    │
    ├─► pr.learn_transition(prospection)           [prospective_composition]
    │       transitions[antecedent_sig||action] += support/means (≤128)
    │       (+ optional SMC dual-writes under motor signatures)
    │
    ├─► smc.update(...)                            [sensorimotor_consequence]
    │       records[key] aggregates (≤256)
    │
    ├─► optional: multiscale / equivalence / temporal / instrumental learns
    │
    ▼
RETRIEVAL (if cfg.retrieval):
    for action in actions:
        pc.predict(compression, obs, action)       # scan structures ≤64
        fallbacks: temporal / equivalence retrieve
    │
    ▼
COMPOSITION (every cognition tick when prospective_composition on):
    pr.compose_trajectories(prospection, start=obs, branch_actions=actions)
        seeds: predict_one_step per action
            exact key OR soft_match over transitions for that action
        BFS ≤ MAX_DEPTH=8, MAX_BRANCH=4, MAX_EXPANSIONS=64, MAX_WORKSPACE=32
    optional: temporal bridge entry_steps, PCP, multistep MAP (add continuations)
    │
    ▼
PSC / selection:
    scenario_competition.compete_scenarios(...)    # ≤32 scenarios total
    composite motor factorization / observed_composite path
    │
    ▼
action realization → world/body
    │
    ▼
if bounded_memory: pc.purge_redundant_raw(keep_recent=True)

OBSERVER (optional, separate from cognition decision):
    runtime.cognitive_view() → cognition_public_view()
        includes pc.snapshot → memory_cost (JSON size; cached on occupancy key)
    LIVE compact frames intentionally avoid full cognitive_view
```

**Evidence anchors**

- Learn + retrieve + compose: `mechanistic_mind/physical_system/cognition.py` (~observe/learn ~390–660, retrieval ~582–625, compose ~656–662, purge ~1198–1200).
- Compression predict: `predictive_compression.predict` lines 349–372 (structures only).
- Soft match: `prospective_composition.predict_one_step` + `research/psc_opt` (`soft_match_legacy` loops `transitions.values()`).
- Capacities: `RECENT_CAPACITY=128`, `STRUCTURE_CAPACITY=64`, `MAX_TRANSITIONS=128`, SMC `DEFAULT_CAPACITY=256`.

---

## 3. Memory hierarchy table

| Level | Bounded? | Used by normal retrieval? | Constituents still searched? | Runtime cost can grow? |
|-------|----------|---------------------------|------------------------------|------------------------|
| Raw `raw_log` / recent ids | Yes (recent ≤128; purge deletes rest) | **No** for `pc.predict` / PSC soft_match | After purge: **No** in ordinary cognition; recent retained | Raw *count* plateaus; `raw_generated`/`raw_removed` counters grow |
| Compression `structures` | Yes (≤64; weakest forgotten) | **Yes** — `pc.predict` linear scan of ACTIVE | N/A (structure is the unit) | Cost plateaus once full; eviction churn possible |
| Structure representatives / provenance / exceptions / PAE | Yes (small caps) | **No** in PSC; used for revision + researcher `expand_structure` | Not in soft_match | Bounded |
| Prospection `transitions` | Yes (≤128) | **Yes** — PSC/composition primary | Transition is already aggregate; soft_match scans **sibling** transitions | Grows until 128 then plateaus; soft_match work scales with fill |
| SMC records | Yes (≤256) | Query by signature / optional scan | Aggregates, not raw O′ lists as primary PSC pool | Bounded |
| Multiscale local/broader | Mechanism-capped (see `multiscale` module) | When enabled, parallel to compression | Soft boosts via `relation_boost_ids` / `broader_member_ids` flags on prospection — **not** full expand | Bounded flags/sets |
| Causal trace events/edges | Ring buffers (public view shows last 64/192) | Observer/research | No | Bounded in view |

**STORAGE COMPRESSION:** Yes — raw folded into structures; purge deletes redundant raw.

**COMPUTATIONAL COMPRESSION:** Partial —

- Raw constituents **retired** from `pc.predict` and from PSC soft_match.
- Peer transition rows **remain searchable** (bounded).
- No rule retires a transition because a compression structure already covers that evidence.

---

## 4. PSC call path (one normal production decision)

Approximate per agent per tick when PSC + composition ON (from `results/psc_composition_performance/baseline_hotpath.json` filled regime + code limits):

| Stage | Approx magnitude | History-dependent? |
|-------|------------------|--------------------|
| Stores consulted | compression, prospection, SMC, optional temporal/eq/PCP/MAP/conflict | Store *occupancy*, not tick age after fill |
| `pc.predict` | ~1 × \|actions\| (~14) | Structures ≤64 — **constant after fill** |
| `compose_trajectories` | 1 call | Internally × branch_actions × BFS expansions |
| `predict_one_step` | ~70–120 / tick (2 agents filled) | Soft path grows as MATCH rate / store fill rises, then plateaus |
| soft_match | ~similar to soft-path predict_one_step | Scans rows for action; packed backend ~**1.2 rows/call** filled |
| Continuations | workspace ≤32; public slice often ≤8–16 | Bounded by MAX_* |
| Scenario competition | ≤4 per action, ≤32 total | Bounded |
| Composite ops | loco competition + side-channel factorization (or OBSERVED_COMPOSITE candidates) | Candidate count from SMC/history — capacity-bounded |

**Does PSC recompute what compression already computed?**

- **Not by expanding structure constituents.**
- **Yes in the weaker sense:** the same experience is learned into **both** `compression.structures` and `prospection.transitions`. Retrieval may `pc.predict` while composition soft-matches transitions — duplicate *representation*, not re-scan of raw provenance.

---

## 5. Composite / prospection call path

| Question | Answer |
|----------|--------|
| Seeds | One-step `predict_one_step` for each `branch_actions` entry from current observation; optional temporal-bridge `entry_steps` |
| Candidate transitions | Dict lookup by `_sig(_q(antecedent))\|\|action`, else soft_match over transitions for that action |
| Indexed vs scan | Exact key O(1); soft_match O(rows_for_action) with packed index preferred |
| Max branching | `MAX_BRANCH = 4` |
| Max depth | `min(prospective_depth, MAX_DEPTH=8)` (config often 3) |
| Expansion budget | `MAX_EXPANSIONS = 64`, workspace `MAX_WORKSPACE = 32` |
| Duplicates | BFS can revisit same `(antecedent_q, action)` (~34% dup fraction filled); cycle-cache attempted then **reverted** (no E2E win) |
| Old compressed evidence reopened? | **No** expand of compression provenance on this path |
| Runs every tick? | **Yes**, when prospective composition enabled (ablate only disables chaining) |
| Invalidation / reuse | No durable cross-tick composition cache in production; pack cache for soft_match backend |

Cheap ops × high call volume: `_sig`, soft_match, nested `predict_one_step` inside compose — **documented** as the filled-store science ceiling, not an unbounded history walk.

---

## 6. Observer amplification findings

| Path | Invokes cognition decision? | Notes |
|------|----------------------------|-------|
| LIVE compact frame (`causal_chain_compact_frame`) | **No** | Explicitly avoids `cognitive_view` |
| FULL / mind panels via `runtime.cognitive_view()` | **No new decision** | Rebuilds `cognition_public_view` (deepcopy + `pc.snapshot` → `memory_cost`) |
| `memory_cost` | Observer/research | JSON-serialize persistent maps; **cached** on occupancy tuple (mitigation) |
| Same-tick `cognitive_view` cache | Yes | `PhysicalSystemRuntime.cognitive_view` caches by tick |

**SIMULATION COST:** cognition decide + world/body (bounded store fill → plateau).  

**OBSERVATION COST:** can dominate if FULL capture / repeated public views / evidence disk / lock wait — see `docs/LONG_RUN_OBSERVER_PERFORMANCE.md`, `results/live_optical_performance/complexity_audit.json` (`COGNITION_STORE_FILL_PLUS_OBSERVER_FULL_CAPTURE`).

Observer does **not** need to re-run PSC to hurt FPS; serializing/deep-copying mature cognitive state is enough.

---

## 7. Complexity analysis

| Pattern | Where | Effective class | Grows with run age after fill? |
|---------|-------|-----------------|--------------------------------|
| `for action in actions: pc.predict` | cognition retrieval | O(A × S) A≈14, S≤64 | **No** |
| soft_match over transitions | predict_one_step miss path | O(T_action) ≤128; packed ~1.2 rows | **No** after fill |
| compose BFS × actions × expansions | compose_trajectories | O(A × expansions) capped 64 | **No** (MATCH rate saturates) |
| Nested predict inside compose | hot path | Dominant filled cost | Plateaus |
| `memory_cost` json.dumps | Observer snapshot | O(bytes of stores) | Mild with occupancy; cached |
| Evidence JSONL append | session | O(1)/tick I/O; disk grows | Disk/RSS, not decide loop |
| Compression constituents × PSC candidates | — | **Not present** | — |

**Hidden multiplication found:** action-repertoire × compose expansions × soft_match — **scientifically intentional under current keys**, not raw×history.

**Not found:** `for raw in all_raw_history: for candidate in candidates` on the production PSC path.

---

## 8. Profiling results

### A. This audit — bare `PhysicalSystemRuntime` (seed 17, default cognition, no Observer)

Artifact: `results/performance_memory_compression_audit/bare_psr_scaling.json`

| Tick | ms p50 (last 40) | transitions | structures | raw_retained | raw_removed | recent |
|------|------------------|-------------|------------|--------------|-------------|--------|
| 100 | 4.33 | 6 | 64 | 99 | 0 | 99 |
| 300 | 4.70 | 8 | 64 | 128 | 171 | 128 |
| 600 | 4.72 | 8 | 64 | 128 | 471 | 128 |
| 1000 | 4.72 | 8 | 64 | 128 | 871 | 128 |

Interpretation: structures saturate at 64 quickly; raw_retained plateaus at recent capacity after purge; **tick ms flat**. (This default PSR fill is lighter than Observer “all mechanisms” fills.)

### B. Prior filled-store science (Observer-class cognition) — reused, not re-run to 9000

From `docs/PSC_COMPOSITION_PERFORMANCE.md` / `baseline_hotpath.json`:

| Regime | ~t/s | ~ms/tick |
|--------|------|----------|
| Early | ~43 | ~23 |
| Filled | ~29.5 | ~34 |
| Plateau | ~28 | ~35 |

From `docs/LONG_RUN_OBSERVER_PERFORMANCE.md` bare PSR aging ~200→5k: **~1.14×** (6.2→7.0 ms).

From `results/live_optical_performance/long_exposure_profile.json`: after transition store fills (~128), **stabilizes**; “no unbounded O(history) in science path.”

### C. Controls (from prior docs; semantics unchanged)

| Control | Finding |
|---------|---------|
| Headless / science only | Plateaus after store fill |
| Observer LIVE compact | Capture ~5–7 ms stable (prior) |
| Observer FULL / public view | Historically catastrophic; caches mitigate |
| PSC / compose dominant when ON | ~44% staged time in compose (includes nested predict) |

9000-tick full reproduction not required to answer the **compression retirement** question; store caps make asymptotic behavior visible by ≤1–2k filled ticks.

---

## 9. Central-question classification

### **B. LOWER LEVELS PARTIALLY RETIRED**

**Code evidence**

1. **Retired from compression retrieval:** `pc.predict` only walks `structures` (`predictive_compression.py` 349–372).  
2. **Retired from durable raw retention:** `purge_redundant_raw` deletes non-recent raw (`cognition.py` ~1198–1200 + `predictive_compression.py` 375–407). Bare probe: `raw_removed` climbs while `raw_retained` stays 128.  
3. **Not used by PSC soft_match:** soft_match iterates prospection `transitions`, not compression provenance/representatives (`psc_opt` / `predict_one_step`).  
4. **Still active as peer compressed transitions:** up to 128 transition aggregates remain soft-match eligible; SMC dual-writes add more keys under capacity.  
5. **No hierarchical “cover ⇒ exclude constituents” rule** linking `structures[key]` to transition retirement.

If forced to pick a second label: aspects of **D** apply — hierarchical compression and PSC transitions are **different mechanisms** sharing a learning tick, not parent/child search retirement inside one index.

---

## 10. Top runtime bottlenecks (ranked by measured / documented cost)

1. **`compose_trajectories` + nested `predict_one_step` / soft_match** over full action repertoire (filled science; ~tens of ms/tick).  
2. **Observer FULL `cognition_public_view` / historical `memory_cost` serialization** (observation tax; can dwarf science if uncached / repeated).  
3. **Session evidence append + UI lock/heartbeat issues** (long-run Observer UX; not compression expand).  
4. **Duplicate BFS revisits** inside compose (~7 ms/tick estimated; cache reverted).  
5. **Compression `pc.predict` linear scan** — real but small (≤64 × A) vs compose.

**Not in top causes:** re-processing all raw constituents of each compressed structure every tick.

---

## 11. Why tick cost grows (or does not) with runtime

| Phase | Behavior | Cause |
|-------|----------|-------|
| Early | Rising ms/tick | Empty → filling transitions/structures; rising MATCH rate → more compose expansions that succeed |
| Mid | Approaches plateau | Capacities hit (64 / 128 / 256) |
| Late science | ~flat (prior ~1.1–1.5× to 5k) | Bounded stores; soft_match packed |
| Pathological seconds/tick | **Not explained by compression constituent re-scan** | Prefer Observer/FULL capture, I/O, lock wait, or a different enabled diagnostic path |

**Evidence-backed statement:** Forming compressed structures **does** allow ordinary cognition to avoid walking purged raw evidence. It does **not** remove the need to soft-match among up to `MAX_TRANSITIONS` peer aggregates, nor the per-tick compose over the action list.

---

## 12. Possible architectural remedies (DO NOT IMPLEMENT)

Listed only for later work; **not** done here:

1. Explicit **computational retirement**: when a compression structure covers a transition key, mark transition ineligible for soft_match unless prediction failure / novelty / conflict gates reopen it.  
2. Align compose `branch_actions` with locomotion competition set — **model change**, needs new fingerprint baseline (`docs/PSC_COMPOSITION_PERFORMANCE.md`).  
3. Durable same-tick or short-horizon composition memoization with measured E2E gain (prior cycle-cache failed).  
4. Keep Observer default on compact capture; never call full `cognitive_view` on the LIVE hot path (mostly already true).  
5. Separate “research expand” APIs from any accidental live panel refresh.  
6. Profile a true 9k-tick run under **headless vs LIVE compact vs FULL** with stage timers to attribute any remaining 1.5–2 s symptom.

---

## Final verdict

**COMPUTATIONAL_COMPRESSION_PARTIAL**

Compressed predictive structures **do** retire raw/recent constituents from ordinary `pc.predict` and from PSC soft_match (storage + retrieval retirement of raw).  

They **do not** implement full hierarchical computational compression for PSC: peer transition aggregates remain searchable, and PSC does not treat compression structures as parents that suppress constituent evidence.  

The severe multi-second tick costs described at ~9000 are **unlikely** to be caused by re-expanding compressed constituents; investigate **Observer/capture/I/O** and **bounded-but-heavy compose** first.

---

### Artifacts

- `docs/PERFORMANCE_MEMORY_COMPRESSION_AUDIT.md` (this file)
- `results/performance_memory_compression_audit/bare_psr_scaling.json`
- Supporting prior: `docs/PSC_COMPOSITION_PERFORMANCE.md`, `docs/LONG_RUN_OBSERVER_PERFORMANCE.md`, `results/live_optical_performance/complexity_audit.json`, `results/psc_composition_performance/baseline_hotpath.json`
