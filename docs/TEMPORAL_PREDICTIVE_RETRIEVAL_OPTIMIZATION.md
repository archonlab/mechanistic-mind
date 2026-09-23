# TEMPORAL PREDICTIVE RETRIEVAL OPTIMIZATION

**Date:** 2026-09-21 (Europe/Oslo)  
**Source forensic:** `docs/LIVE_AGED_RUN_PERFORMANCE_FORENSICS.md`  
**Artifacts:** `results/temporal_predictive_retrieval_optimization/`  
**Git push:** none

---

## Verdict

**`TEMPORAL_RETRIEVAL_OPTIMIZATION_ACCEPTED`**

| Gate | Result |
|---|---|
| `SCIENTIFIC_EQUIVALENCE` | **EXACT_MATCH** (500 oracle queries + 250-tick integrated fingerprint) |
| `NORMAL_RETRIEVAL_NO_FULL_CLASS_SCAN` | **YES** (production path uses action-bucket index) |
| Scaling | Inspections track **bucket size**, not total ACTIVE+FORGOTTEN class count |
| Live / WEB mature | Optimized WEB (:8771) ~**17 ms/tick** past tick 6000 vs forensic aged :8768 ~**1.2 s/tick** at ~3106 |

---

## ROOT CAUSE

Live py-spy (`LIVE_AGED_BOTTLENECK = TEMPORAL_PREDICTIVE_RELEVANCE_CLASS_SCAN`) showed ~60% of samples in:

```text
temporal_predictive_structure.retrieve
  → predictive_relevance.retrieve
      for cls in eq_store["classes"].values():  # full dict scan
```

### Semantics that made a full scan age-dependent

1. **Retrieval candidate** = any class with `status=="ACTIVE"`, `action` exact-equal to the query action (temporal queries use `f"{action}|L{lag}"`), and `support >= MIN_CLASS_SUPPORT` (3).
2. **Exact pre-filters:** `ACTIVE`, `action` string equality, minimum support.
3. **Soft match (unchanged):** relevance `_partial_in` on `relevant` AABB keys (relevance path) or full `_in_aabb` (equivalence path). Continuation conflict uses L-inf vs `CONTINUATION_LINF`.
4. **Multi-match:** all hits collected; conflict if continuation means disagree with the **first** hit in dict order; else `max(hits, key=support)` (ties → first max = earlier insertion order).
5. **Ordering matters** for tie-breaking and conflict-vs-first comparison → index must preserve **insertion order among ACTIVE classes sharing an action**.
6. **Classes are mutable:** learn updates members/AABB/support; may split; may FORGOTTEN oldest when forming beyond `MAX_CLASSES` (32). FORGOTTEN rows **remain in `classes`**.
7. **Full scan therefore walks FORGOTTEN + wrong-action ACTIVE rows every call** → cost grows with lifetime class dict size and call fan-out (lags × actions × collect_entry_steps / diagnostics).

`collect_entry_steps` reuses TPS rows already in `predictions` when present; otherwise calls `tps.retrieve` again (common when compression already matched). `tps.diagnostic` also re-retrieves.

---

## IMPLEMENTATION

### 1. Exact action → class-id index (`predictive_equivalence.py`)

Derived fields (stripped from scientific compares):

- `_ix_action`: `action → [class_id, …]` in `classes` insertion order among ACTIVE
- `_ix_member`: `action\\0sig → class_id` for learn host lookup
- `_ix_gen` / `_ix_built_gen`: stale detection
- Rebuild via `rebuild_class_indexes` / lazy `ensure_class_indexes`
- Authoritative invalidation: `invalidate_class_indexes` after every `learn` mutation and `clear_derived_caches` (restore path)

Production `retrieve` / `predictive_relevance.retrieve` iterate **`iter_active_classes_for_action`** then apply the **same** soft matchers as before.

### 2. Legacy oracle (tests/debug only)

- `predictive_equivalence._retrieve_full_scan_reference`
- `predictive_relevance._retrieve_full_scan_reference`

Not used in normal production execution. Toggle `set_class_index_enabled(False)` forces full-scan collect for A/B benches.

### 3. Learn path

Host lookup uses `_ix_member`; continuation candidates use the action bucket. Matching/update/split/forget/form semantics unchanged.

### 4. Same-tick TPS memo (`temporal_predictive_structure.retrieve`)

Cache key:

```text
(cache_gen, inner_ix_gen, window_fragment_sigs…, action, lag, use_relevance)
```

- Generation bumps on `append`, `learn`, `refresh_relevance`
- **Does not** key on present-only (that incorrectly aliased different histories)
- Safe for `collect_entry_steps` / diagnostic duplicate queries within an unchanged ring+store

### 5. What was NOT changed

Thresholds, capacities, matching rules, 4.26–4.28, PSC design, Observer capture policy, science ordering of hits.

---

## SEMANTIC SAFETY (answers from code)

| # | Question | Answer |
|---|---|---|
| 1 | Retrieval candidate? | ACTIVE class, matching action, support≥3, then soft span/relevance gate |
| 2 | Possible-match fields? | Exact: status, action, support floor. Soft: AABB / relevant keys |
| 3 | Exact equality? | `action`, `status==ACTIVE` |
| 4 | Approximate? | AABB intervals (±1e-12), continuation L-inf |
| 5 | Ordering affect result? | **Yes** (conflict vs means[0]; support ties) |
| 6 | Multiple classes match? | **Yes** |
| 7 | First-match significant? | Not first-match exit; ordered collect then max/conflict |
| 8 | Classes mutable? | **Yes** |
| 9 | Index invalidation? | learn create/update/join/split/forget; restore `clear_derived_caches`; TPS append/learn/refresh for memo |
| 10 | Learn merge/revise/remove? | join / update / split_member / FORGOTTEN; no reorder of dict keys except new inserts |

---

## BEFORE / AFTER

### Microbench (mature fill, 32 ACTIVE, many actions)

| | Full scan | Indexed |
|---|---|---|
| Inspections / call | **32.0** | **~1.78** |
| µs / call | ~10.9 | ~9.4 |

### Integrated headless (seed 676, live-like flags)

| Checkpoint | Indexed ms/tick | Indexed insp/retrieve | Full-scan insp/retrieve (sample) |
|---|---|---|---|
| 500–3000 | ~44–48 | **3.4** | **23.0** at t1500/t3000 |

Indexed inspections stay flat with age; full-scan inspections remain higher because every retrieve walks the entire `classes` dict.

### Scientific equivalence

- 500× `prl.retrieve` == `_retrieve_full_scan_reference` → exact
- 250-tick TwoAgentRuntime indexed vs full-scan fingerprint → exact

### Production WEB

| | Forensic aged (:8768, pre-opt code) | Optimized WEB (:8771) |
|---|---|---|
| Tick region | ~3106 (later stopped ~4089) | ~6298+ |
| `last_tick_wall_ms` | ~1200 (later ~1776) | **~17** (POST-PSC sample) |
| Observer | MINIMAL | MINIMAL |
| Process | preserved / not restarted for forensics | **new** process loading optimized code |

**WEB caveats (honest):**

- :8771 validation host reported `PhysicalSystemRuntime` (1 agent), while the forensic run was `TwoAgentRuntime`. Cognition retrieval stack is the same modules; absolute ms are not a perfect paired A/B.
- :8771 was run at elevated `speed` for maturation; forensic :8768 was realtime-ish (`speed≈1`).
- :8768 was **not** modified or restarted by this work (left on pre-optimization bytecode until process exit/stop).
- `psc_motor_resolution` on :8771 sample ended as `LOCO_FACTORIZED` (POST/PRE PSC here toggled `prospective_scenario_competition` only).

PRE-PSC vs POST-PSC wall means on :8771 were both ~16–21 ms (one PRE outlier 150 ms); **PSC is not the dominant cost once retrieval scanning is indexed**.

---

## LONG-RUN SCALING

See `results/temporal_predictive_retrieval_optimization/long_run.json` (`checkpoints_indexed`, `checkpoints_full_scan_sample`).

- `tps_retrieves_per_tick` ≈ 10 (stable)
- Indexed `inspections_per_retrieve` ≈ 3.4 ≈ lags × mean bucket (~1)
- Full-scan `inspections_per_retrieve` ≈ 23 on the same seeds/checkpoints
- Bucket stats: mean/median/max bucket **1** when actions are well partitioned; mature multi-action fill mean bucket ~**2.9**, max **3**

**Retrieval cost is now primarily bucket-sized, not total class-dict sized.**

---

## MEMORY COST

- Index stores **class id strings** and member-sig keys only (references into existing `classes`), not duplicated predictive payloads.
- Bound: ≤ `MAX_CLASSES` ACTIVE ids in action buckets; member map ≤ ACTIVE × `MAX_MEMBERS`.
- TPS memo: per-tick query map cleared on generation bump; entries are result dict references.
- No measurable RSS experiment beyond normal run variance; structural overhead is small vs ~2.8 GB aged process RSS from the forensic run.

---

## REMAINING HOTSPOTS

After this change, expected next costs (not optimized here):

- `predictive_equivalence.learn` / temporal learn fan-out (was ~12% live; now uses action buckets too)
- Prospective composition / PSC when candidate sets grow
- Observer FULL cognitive_view (not in MINIMAL path)
- Signal-context episode grouping (small in forensic profile)

---

## TESTS

`tests/test_temporal_predictive_retrieval_index.py` covers empty/one/many classes, shared buckets, relevance oracle, learn/forget reindex, clear_derived rebuild, same-tick memo + invalidation, collect_entry_steps reuse, strip_derived.

Existing predictive equivalence / relevance / temporal / bridge tests pass.

---

## FILES TOUCHED

- `mechanistic_mind/research/predictive_equivalence.py` — index, learn host/candidates, retrieve split, oracle
- `mechanistic_mind/research/predictive_relevance.py` — indexed retrieve + oracle
- `mechanistic_mind/research/temporal_predictive_structure.py` — same-tick memo; gen bump on append/learn/refresh
- `tests/test_temporal_predictive_retrieval_index.py` — new
- `docs/TEMPORAL_PREDICTIVE_RETRIEVAL_OPTIMIZATION.md` — this file
- `results/temporal_predictive_retrieval_optimization/*` — JSON artifacts

**No git push.**
