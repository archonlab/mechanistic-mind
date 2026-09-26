# Beta 3.1 — 40k RSS owner attribution

The failed e02e833b run’s ~465 MB RSS / 1000 ticks is **reachable PE forgotten-class retention**, not Observer frames, not V3 RAM, not Eye/FPV, not Signal Forensics V2.

Failed corpus path remains **read-only**.

## A/B (seed 575, TwoAgent, R3 / RICH / CORRELATED / OCCLUSION, failed-run mechanism map including PE)

Window t0–t1000, hard ceiling +2 GB (not hit).

| probe | RSS MB/1000 | RssAnon MB/1000 | PE forgotten/1000 | V3 disk MB/1000 |
|---|---|---|---|---|
| RUNTIME_ONLY | 707.7 | 707.4 | 522 | 0 |
| NORMAL | 713.8 | 713.7 | 522 | 37.6 |
| HEADLESS | 708.1 | 708.1 | 522 | 37.6 |
| PUBLICATION_SUPPRESSED | 712.7 | 712.6 | 522 | 37.6 |
| V3_ENCODE_SUPPRESSED | 713.2 | 713.1 | 522 | 0 |

Observer − runtime ≈ **6 MB/1000** (noise vs PE). `FULL_WORLD_FRAMES_RETAINED = 1` on NORMAL.

Without PE (earlier misconfigured pass): `ru_maxrss` ≈ **97 MB/1000** while SMC filled to 256 and prospection to 128 — then those stores are capped.

## Heap / GC / allocator

- `gc.collect()` at t1000: **0** objects, **0** RSS delta → not an unreachable leak.
- `malloc_trim(0)` diagnostic: **−31 MB** (~4%). Not the slope. Not used in production.
- `/proc` maps count stable; growth is **Private_Dirty in existing anon mappings**.
- Recursive sizeof undercounted (500k-object budget). Cardinality: ~264+258 forgotten classes at t1000, ACTIVE 32/32.

## Mechanism

`predictive_equivalence.MAX_CLASSES = 32` caps **ACTIVE** only. `_forget_lowest_support_active` sets `status=FORGOTTEN` and **leaves the class in `classes`**. Each member keeps `fragment`, `mean_c`, and `last_abs` float maps (wide under RICH+OCCLUSION). Learn copies these on FORM/JOIN. Forgotten rows do not participate in retrieve (P0).

Young slope **~708 MB/1000** is steeper than the 40k mean **465 MB/1000**. That is expected if unique visual antecedents form classes faster early; it is **not** a missing Observer leak.

## Why there is no production fix in this task

Valid RSS reduction would require changing PE **history policy** (drop/compact FORGOTTEN) or PE **capacities**. Both are frozen here. Allocator trim / periodic GC are invalid fixes.

Checkpoints still only bound *loss*, not live RSS.

## Operational projection (caution: not proven linear past t1000)

Using the **40k observed mean 465 MB/1000** (not the young 708): 10k ~4.7 GB, 20k ~9.3 GB, 40k ~18.6 GB (matches OOM), 100k ~46 GB. Using young 708: 10k ~7 GB, 40k ~28 GB.

A 40k publication run with PE ON on this machine remains **unsafe**.
