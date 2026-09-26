# Nested PE / TPS / TPE forgotten-history forensic

## Verdict

**BETA31_NESTED_PE_HISTORY_REPRESENTATION = PARTIAL** (audit complete; no payload-pool production change)

The ~14× class count is **real extra temporal evidence**, not 14 copies of outer PE members.

## Topology (t1000, seed 575, slot 0)

| store | learns | forgotten | unique member payloads | schemas |
| --- | --- | --- | --- | --- |
| `equivalence` | 999 | 264 | 264 | 1 |
| `temporal.inner` | 3978 | 3799 | 3799 | 1 |
| `tpe.lags.1.inner` | 3498 | 2207 | 2207 | 1 |
| `tpe.lags.3.inner` | 0 | 0 | 0 | — |

Nested forgotten **never reactivate** and **do not affect future cognition** (same `pe.retrieve` ACTIVE-only path).

## Why 14×

`tps.learn` calls `pe.learn` **four times per tick** (`LAGS = 1,2,3,4`) with:

- action `{act}|L{lag}` (four class namespaces)
- `_window_deltas` over different ring slices (four antecedents)

Forgotten lag buckets at t1000: L1=951, L2=950, L3=949, L4=949.

Outer PE is join-heavy (999 learns → 264 forgotten). Inner lag-learns almost always **FORM** after the cap of 32.  
`3799 / 264 = 14.39`.

TPE lag-1 is a **second TPS** over residual fragments, not a view onto `temporal.inner`.

## Duplication

- **FULL_RECORD_DUPLICATION_RATIO = 0**
- **MEMBER_PAYLOAD_DUPLICATION_RATIO = 0**
- **STRUCTURAL_SCHEMA_DUPLICATION_RATIO = 1.0** (one internable channel-key schema)

LEVEL 0–3 payload sharing is not available. LEVEL 4 (distinct temporal/residual history) is the bulk.

`TEMPORAL_INNER_COPIES_EXISTING_HISTORY = NO`  
`TPE_LAGS_SHARE_HISTORICAL_PAYLOAD = NO`

## Representation

Do not merge lag classes. Do not content-address member arrays (all unique). Hybrid G packing stays. Forgotten class `mean_c` may share the interned `_pack_keys` tuple (lossless). No 5k run: it would not change 40k OOM class.
