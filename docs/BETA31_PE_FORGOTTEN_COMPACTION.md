# Beta 3.1 PE forgotten compaction

Lossless packing of FORGOTTEN PE member maps at the forget boundary.
Does not change PE formation, ACTIVE cap, forget victims, prediction, SMC, PSC, vision, or V3 production semantics.

## What changed

When `_forget_lowest_support_active` sets `status=FORGOTTEN`, `compact_forgotten_class` replaces each member’s `fragment` / `mean_c` / `last_abs` dicts with packed `{v: array('d'), p: array('B')}` under interned `_pack_keys`. Class id, support, AABB, class `mean_c`, provenance, and relevance stay.

Legacy full forgotten rows compact once on `clear_derived_caches` (restore). Source save files are not rewritten.

`set_forgotten_compaction(False)` remains a test/bench switch.

## Gates

| Gate | Result |
| --- | --- |
| Round-trip expand vs original maps | YES (exact floats) |
| Shadow retrieve/snapshot | 100% |
| Forget victim / lifecycle A/B | EXACT |
| Two-agent actions compact vs full | EXACT (220 ticks seed 21; 1000+8 ticks seed 575) |
| Old full snapshot load | PASS (in-memory compact) |
| Cognition / PE / PSC / vision semantics | NO change |
| Persistence representation | YES (packed members + `_pe_forgotten_rep`) |

## Memory (seed 575, TwoAgent, R3/RICH/CORRELATED/OCCLUSION, PE ON, RUNTIME_ONLY)

| | FULL | COMPACT |
| --- | --- | --- |
| RSS t0 | 43.3 MB | 43.4 MB |
| RSS t1000 | 750.7 MB | 521.9 MB |
| MB / 1000 (t0–t1000) | 707.4 | 478.5 |
| MB / 1000 (t250–t1000) | 678.6 | 419.1 |
| t/s | 7.02 | 6.82 |
| forgotten / agent / 1000 | 264 / 258 | same |
| sizeof bytes / forgotten class (slot 0) | 49153 | 20115 |

RSS reduction (t0–t1000): **32.3%**. Slope t250–t1000: **38.2%**.

Linear 40k projection from compact t250–t1000 still ~16.8 GB — **not** an executed 40k run. Remaining slope is still too steep for an unattended 40k (class shells, other cognition stores, allocator). Compaction is necessary and lossless; it is **not** sufficient to lift the 40k release blocker.

## Checkpoint

In-memory restore tests pass. A 500-tick `dump_persist` JSON vs *live* next-action comparison failed; the same live-vs-restore mismatch appears with compaction off. JSON restore vs in-memory restore from the same snapshot matched at 120 ticks.

## Stop

No git push. No Beta 3.1 publish. No unattended 40k.
