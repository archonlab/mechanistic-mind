# Beta 3.1 post-PE-compaction memory reconciliation

Member-map packing of forgotten PE classes is lossless and remains in production.
This note explains the **remaining ~419–479 MB RSS / 1000 ticks**.

## Verdict

**BETA31_POST_PE_MEMORY_RECONCILIATION = PARTIAL**

The residual slope is mostly **retained nested PE forgotten history**, not allocator junk from forget-time compaction. gc.collect does not remove it. A second production fix was **not** applied: forgotten history is still not capped (hard freeze).

## RSS vs accounted

Seed 575, TwoAgent, R3/RICH/CORRELATED/OCCLUSION, compact PE ON, RUNTIME_ONLY:

| tick | RSS MB |
| --- | --- |
| 0 | 43.2 |
| 250 | 207.4 |
| 500 | 312.9 |
| 1000 | 521.9 |

t0–t1000: **478.7 MB / 1000**. t250–t1000: **419.3 MB / 1000**.

Recursive sizeof of both agents’ cognition at t1000 ≈ **241 MB**. World ndarrays ≈ 0.15 MB.  
**RSS_RECONCILIATION_RATIO ≈ 0.50** (accounted reachable / RSS delta). The other half is pymalloc arenas / untraced natives / sizeof gaps (interned keys counted once in a store walk, many times if summed per field).

## Nested PE, not just outer `equivalence`

At t1000 slot 0 (member maps already packed):

| store | forgotten classes | sizeof store |
| --- | --- | --- |
| `cognition.equivalence` | 264 | 7.3 MB |
| `cognition.temporal.inner` | 3799 | 64.5 MB |
| `cognition.temporal_prediction_error` | (lags each have a TPS/PE ring) | 45.0 MB |

TPS inner forms forgotten classes ~14× faster than outer PE under the same ACTIVE cap=32. Packing applies to all of these (`n_packed` matches forgotten). Compact forgotten history does **not** pin compression records.

SMC=256 and prospection transitions=128 are **bounded and filled by t500**.

## PE-OFF control

Disabling outer PE + TPS + TPE via cognition config (the first mis-wired probe left PE on):

| tick | RSS MB | PE forgotten |
| --- | --- | --- |
| 0 | 43.3 | 0 |
| 500 | 102.6 | 0 |
| 1000 | 143.1 | 0 |

SMC/prospection already at cap by t500. t500–t1000 still **~81 MB / 1000** (not a full plateau). Compact PE ON vs this PE-OFF is **~379 MB / 1000** attributable to the PE family.

## Owner #2

**SECONDARY_PRIMARY_RSS_DRIVER** = unbounded forgotten PE rows in TPS inner + TPE lag rings (and residual outer PE).  
**RETAINED**, not forget-time transient churn.  
**STRONG**. No second fix: cannot cap/delete forgotten history under the freeze; member packing already runs on every `pe.learn` forget.

40k linear projection from 479 MB/1000 remains OOM-class. 10k ≈ 4.8 GB is the practical bound on this machine class, not a 10k execution.
