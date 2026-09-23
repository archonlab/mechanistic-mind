# PSC COMPOSITE SHADOW EVALUATION

## Method

For each live PSC tick (shadow-only):

1. Mirror LOCO_ONLY prediction per locomotion candidate.
2. Enumerate **unique** motor signatures in SMC store sharing that loco prefix.
3. Query each with existing `smc.query` (contextual matching unchanged).
4. Build O′ via existing `construct_o_prime`.
5. Measure global + family pairwise divergence among composite O′s.
6. Compare LOCO_ONLY O′ to composite set (nearest distance / out-of-manifold).
7. Proxy ranking by support (diagnostic only — not production `compete_scenarios`).

## Synthetic acceptance

| Case | Result |
|------|--------|
| A identical futures | would_refine=False, max_div=0 |
| B neck differs | would_refine=True |
| C oscillator | would_refine=True; field family Δ large |
| D push | would_refine=True |
| E multi side-channels | exactly 2 observed signatures (no Cartesian) |

## Wet-world comparison classes (seed 111)

- SAME_LOCOMOTION_DIFFERENT_COMPOSITE: majority
- DIFFERENT_LOCOMOTION: material minority under **support proxy**
- SAME_LOCOMOTION_SAME_REFINEMENT: rare when divergence low

**Caveat:** DIFFERENT_LOCOMOTION uses support-proxy ranking, not full `compete_scenarios`+history replay.

## Aggregation loss

Production `loco_prefix_aggregate` is **MAX_SUPPORT_UNDER_PREFIX**, not averaging.
Out-of-manifold-from-averaging: **NOT_DEMONSTRATED**.
Loss mode: **select one practiced composite**, discard siblings' differentiated futures.
