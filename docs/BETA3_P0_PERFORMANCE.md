# Beta 3 P0 — cognition performance (semantics-preserving)

**Date:** 2026-09-22  
**Constraint:** SCIENTIFIC_EQUIVALENCE EXACT_MATCH. No NumPy/Numba/C++/Rust/multiprocessing. No capacity cuts. GIT_PUSH=NO.  
**Baseline:** `docs/BETA3_PERFORMANCE_FORENSICS.md` (aged TwoAgent ticks 8414–8610, mean **806.9 ms/tick**).  
**Artifacts:** `results/p0_cognition_performance/`, `experiments/run_p0_cognition_performance.py`, `tests/test_p0_cognition_indexes.py`.

Debug index A/B (`pe.set_index_validate`) is **OFF by default** and is not used in production ticks.

---

## 1. Exact old bottleneck

On the TPS inner predictive-equivalence store, every `learn` mutation did:

1. **ACTIVE count** by list-comprehending **all** `classes` (ACTIVE + FORGOTTEN).
2. **Victim selection** at `MAX_CLASSES` via `min(classes.items() if ACTIVE)` — again over the unbounded dict.
3. **`rebuild_class_indexes()`** after UPDATE, JOIN, FORM, and forget — rebuilding `_ix_action` / `_ix_member` from every ACTIVE class even when a single member support changed.

FORGOTTEN rows were never deleted (`status="FORGOTTEN"` only). They stayed in the same `classes` mapping that the hot path scanned.

OBSERVED_COMPOSITE then scanned SMC `records` (capacity 256) by motor-signature prefix, and `query_history_on_o_prime` called `pc._sig(o_prime)` / `pr._q(o_prime)` once per action instead of once per query.

## 2. Why cost grew with history

`MAX_CLASSES = 32` caps **ACTIVE** rows only. Forgotten residue is **unbounded**. Form/evict work was therefore **O(all classes ever)**, plus a full index rebuild **O(active members)** on every learn including trivial UPDATEs. SMC occupancy saturates at 256; prefix scans and `_sig` over wide observation maps stay **O(occupancy × actions × channels)** every PSC tick.

## 3. PE architecture before → after

| | Before | After |
|---|---|---|
| Canonical | `classes`, episodes, counters | **unchanged** |
| Derived | `_ix_action`, `_ix_member` rebuilt wholesale | `_ix_action`, `_ix_member`, `_active_ids`, `_active_count` maintained incrementally |
| Count | scan `classes` | `active_class_count` → `len(_active_ids)` after `ensure_class_indexes` |
| Oracle | (none) | `rebuild_class_indexes`, `scan_active_class_count`, `rebuild_reference_index_payload` |

Canonical scientific identity still lives in `classes`. Indexes are derived; `strip_derived_fields` / `_DERIVED_STORE_KEYS` omit them from structure compares.

## 4. FORGOTTEN handling before → after

Inspected `learn` / `retrieve` / `find_host_class_by_member_sig`:

- **No FORGOTTEN→ACTIVE revival.**
- **No class merge.** Member **split** can drop a member from an ACTIVE host; it does not revive forgotten rows.
- **No deletion** of forgotten rows.

After: forgotten rows remain in `classes` (history, snapshot, Observer, analysis). They are **absent** from `_ix_action`, `_ix_member`, and `_active_ids`. Host lookup and retrieve only consult ACTIVE indexes. Tests: `test_forgotten_does_not_participate_in_retrieve_or_host`.

## 5. Index maintenance before → after

Transitions that change ACTIVE membership (enumerated from code):

| Event | Index update |
|---|---|
| FORM | `_index_add_active` |
| JOIN / member split | `_index_refresh_members` |
| UPDATE (same host) | `_mark_indexes_current` — **no rebuild** |
| ACTIVE→FORGOTTEN | `_forget_lowest_support_active` → `_index_remove_active` then `status=FORGOTTEN` |
| Restore/load | `clear_derived_caches` / `clear_derived_indexes` then lazy `rebuild_class_indexes` |

Victim tie-break: first minimum in `_active_ids` order = `classes` insertion order among ACTIVE (same as old `min(classes.items() if ACTIVE)`).

## 6. OBSERVED_COMPOSITE before → after

Query predicate for candidate generation is **locomotion prefix** `L:{loco}|` on `motor_signature`, then collapse by signature (max support) and sort `(-support, signature)`.

- Oracle: `observed_composites_for_loco_scan` (full `records` scan).
- Production: `observed_composites_for_loco` → `smc.iter_records_for_loco` using `_ix_loco`.
- `_find_row` motor-similarity walk uses `_ix_motor` instead of all records.
- Insert/evict in `smc.update` calls `_index_add_key` / `_index_drop_key`.

Same membership, support, and order required (and tested).

## 7. Signature reuse

`query_history_on_o_prime`: one `pr._q(o_prime)` and one `pc._sig(o_prime)` per query; `predict_one_step(..., _ant_q=)` and `pc.predict(..., antecedent_sig=)`.

`_sig` still builds the sorted-tuple key per call (existing `_SIG_CACHE` is digest-only). P0-E is **same-query reuse**, not a new cross-tick cache.

## 8. Files changed (this task)

- `mechanistic_mind/research/predictive_equivalence.py` — O(1) ACTIVE set, incremental indexes, validate helper
- `mechanistic_mind/research/predictive_compression.py` — `predict(..., antecedent_sig=)`
- `mechanistic_mind/physical_system/sensorimotor_consequence.py` — `_ix_loco` / `_ix_motor`
- `mechanistic_mind/physical_system/psc_motor_resolution_shadow.py` — indexed vs scan oracle
- `mechanistic_mind/physical_system/o_prime_history_bridge.py` — per-query `_sig` / `_q`
- `mechanistic_mind/physical_system/cognition.py` — `clear_derived_indexes`
- `mechanistic_mind/physical_system/runtime.py` — restore drops derived indexes
- `tests/test_p0_cognition_indexes.py`
- `experiments/run_p0_cognition_performance.py`
- `docs/BETA3_P0_PERFORMANCE.md` (this file)
- `results/p0_cognition_performance/{microbench,disposable_two_agent,summary}.json`

Left alone: TPS retrieve, `compose_trajectories`, packed `predict_one_step`, world/vision, Observer, frontend, evidence volume.

## 9. Differential semantic tests

`tests/test_p0_cognition_indexes.py` (12 tests) plus PE / observed-composite / O′ / copy-safety suite.

**57 passed** (`pytest` 2026-09-22, ~10 s):

- learn assignment trace replay
- ACTIVE count vs full scan through forget
- victim order vs old `min`
- incremental index payload **==** full rebuild (content, not counts)
- retrieve indexed **==** `_retrieve_full_scan_reference` with forgotten present
- SMC candidate signatures/support/order
- OBSERVED_COMPOSITE winner vs scan-backed `collect_observed_candidates`
- `query_history_on_o_prime` result with reused signatures

Oracles are the **old scan/rebuild**, not the new code.

## 10. Save/Resume

`PhysicalSystemRuntime.restore` and `TwoAgentRuntime.restore` (slots via `PhysicalSystemRuntime.restore`) call `clear_derived_indexes`. PE/SMC indexes rebuild from canonical `classes` / `records`. Tests: `test_save_resume_reconstructs_pe_and_smc_indexes`, `test_two_agent_save_resume_indexes` (continue one tick; actions match a second restore).

## 11. OLD vs NEW microbenchmarks

Synthetic PE stores (`MAX_CLASSES=32` ACTIVE). Hardware: local CPython, `experiments/run_p0_cognition_performance.py`.

| Store | classes | forgotten | old count ms | new count ms | speedup | old learn-tax* ms | new learn-tax ms | tax speedup |
|---|---|---|---|---|---|---|---|---|
| small | 32 | 0 | 0.0013 | 0.0003 | 4.5× | 0.0216 | 0.0053 | 4.1× |
| medium | 96 | 64 | 0.0031 | 0.0003 | 10.6× | 0.0291 | 0.0052 | 5.6× |
| aged | 544 | 512 | 0.0156 | 0.0003 | **56.5×** | 0.0871 | 0.0053 | **16.4×** |

\*learn-tax = ACTIVE count + victim min + (old) full `rebuild_class_indexes` vs O(1) count + min over `_active_ids` only.

Aged victim select: 0.0303 → 0.0050 ms (6.1×). Incremental UPDATE `learn`: ~0.040 ms (no full rebuild). New count **does not grow** with forgotten (0.0003 ms at 0, 64, and 512 forgotten).

SMC 256 occupancy, loco `MOVE:E` candidate list: scan 0.162 ms vs index 0.128 ms (**1.27×**). Candidate lists equal. `parse_motor_signature` dominates this microbench; the forensic **~103 ms** was PSC × history `_sig`/`predict`, not this prefix walk alone.

`_sig` five calls vs one digest reused five times: **5.0×** (0.133 → 0.027 ms).

## 12. Disposable run checkpoints

**New** TwoAgent seed **901**, 3000 ticks, experimental cognition flags including PE/TPS/SMC/HSS/`OBSERVED_COMPOSITE`. **Not** the aged port-8768 run. No Observer, no scientific JSONL.

| tick | ms/tick | ticks/s | RSS MiB | PE tot/act/for (ag0) | TPS inner tot/act/for (ag0) | SMC occ/cap (ag0) |
|---|---|---|---|---|---|---|
| 100 | 37.46 | 26.7 | 63.4 | 1/1/0 | 4/4/0 | 4/256 |
| 1000 | 44.67 | 22.4 | 122 | 1/1/0 | 4/4/0 | 8/256 |
| 2000 | 46.18 | 21.7 | 154 | 1/1/0 | 4/4/0 | 8/256 |
| 3000 | 47.95 | 20.9 | 176 | 1/1/0 | 4/4/0 | 8/256 |

Agent 1 similar (TPS inner 6, SMC 11). Tick cost rose ~28% from tick 100→3000 while **forgotten PE stayed 0** and SMC did **not** fill. This run **did not enter** the forensic regime (unbounded forgotten + SMC 256/256). RSS growth is the process/world, not a forgotten-index graveyard.

Does tick cost still grow strongly with forgotten accumulation? **On the synthetic aged PE store, the new count/victim tax does not.** **On this 3k world, forgotten never accumulated, so E2E cannot answer that question.**

## 13. Memory / index overhead

| Structure | Purpose | Bound | Lifecycle | Restore |
|---|---|---|---|---|
| PE `_active_ids` | ACTIVE id list (insertion order) | ≤ 32 | add/remove on FORM/forget | rebuild from `classes` |
| PE `_active_count` | O(1) count | 1 int | with `_active_ids` | rebuild |
| PE `_ix_action` | action → ACTIVE ids | ≤ 32 ids | incremental | rebuild |
| PE `_ix_member` | `(action, member_sig)` → cid | ≤ 32×12 | refresh on join/split; drop on forget | rebuild |
| SMC `_ix_loco` | loco → record keys | = occupancy ≤ 256 | add/drop on insert/evict | rebuild from `records` |
| SMC `_ix_motor` | motor_signature → keys | = occupancy ≤ 256 | same | rebuild |

Forgotten PE rows still occupy **canonical** `classes` (same as before). They are **not** duplicated into search indexes.

## 14. Semantic divergence

None found. Index-validate mode compared incremental vs rebuild payloads during tests; production leaves it off.

## 15. Remaining hot paths after P0

- **`pc.predict` still scans ACTIVE compression structures** per action (sig is reused; the loop is not).
- Indexed **TPS retrieve** (~4.8% in forensics) — untouched.
- **`compose_trajectories`**, packed **`predict_one_step`** — untouched.
- **Observer compact capture** (~27 ms/frame outside `last_tick_wall_ms`) and **FULL_SCIENTIFIC JSONL**.
- SMC **eviction** still `min(records)` at capacity (bounded 256).
- Member-index refresh still scans `_ix_member` keys for one class id (bound: active members).

## 16. Acceptance gates

| Gate | Result | Notes |
|---|---|---|
| PE_ACTIVE_COUNT_O1 | **PASS** | Maintained `_active_count`; invariant vs scan in tests |
| FORGOTTEN_HOT_SCAN_REMOVED | **PASS** | Forgotten not in retrieve/host/victim/index; kept in `classes` |
| PE_INCREMENTAL_INDEX | **PASS** | UPDATE no rebuild; FORM/JOIN/forget incremental |
| PE_INDEX_EQUIVALENCE | **PASS** | Payload equality vs full rebuild |
| SMC_INDEX | **PASS** | `_ix_loco` / `_ix_motor`; eviction drops keys |
| SMC_CANDIDATE_EQUIVALENCE | **PASS** | Scan oracle vs index; PSC winner matched |
| SIGNATURE_REUSE | **PASS** | One `_sig`/`_q` per O′ query |
| REFERENCE_VS_OPTIMIZED_SEMANTICS | **PASS** | 12 P0 tests + 57-file suite |
| SAVE_RESUME_REGRESSION | **PASS** | Derived dropped; rebuilt; one-tick continue |
| TWO_AGENT_REGRESSION | **PASS** | Two-agent save/restore/step |
| AGED_STATE_BENCHMARK | **PASS** | 544-class / 512-forgotten microbench |
| END_TO_END_SPEEDUP | **PARTIAL** | 3k disposable ~38–48 ms/tick **without** Observer/JSONL and **without** forgotten PE; cannot claim 807→48 ms on the aged Observer process |
| MEMORY_INDEX_BOUNDED | **PASS** | Indexes ≤ ACTIVE 32 / SMC 256 |
| SCIENTIFIC_SEMANTICS_PRESERVED | **PASS** | No formula/capacity/mode changes; oracles matched |

## 17. Recommended NEXT profiling target

1. Re-profile a **long Observer Beta 3** run with this code (py-spy on `psy-observer-sim`) once PE forgotten and SMC 256 appear — confirm the 55% `learn` leaf is gone.
2. If PSC remains expensive: **`pc.predict` ACTIVE-structure scan** (index by `(domain, action, antecedent_sig)` with the same MATCH rule).
3. Then Observer capture / scientific JSONL volume — not cognition algorithms.

Do not start NumPy/C++ until that second live profile.
