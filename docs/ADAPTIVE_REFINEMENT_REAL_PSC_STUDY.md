# ADAPTIVE REFINEMENT — REAL PSC STUDY

**SHADOW ONLY.** Follows full observed-composite replay through real `compete_scenarios`. No production promotion.

## Method

Refine a coarse locomotion branch only when:

1. ≥ 2 empirically supported composite futures exist, and
2. pairwise predicted O′ divergence ≥ threshold, and
3. composite evidence builds scenarios for competition.

Then run the same O′ → history → `compete_scenarios` path on the refined set (plus coarse keep for non-refined locos).

Thresholds reported (frontier): **0.01, 0.02, 0.05**.

## Frontier (seed 111 wet Phase B)

| threshold | loco agreement vs FULL | composite agreement | class agreement | mean candidates | mean ms | candidate reduction vs FULL (~13) |
|----------:|-----------------------:|--------------------:|----------------:|----------------:|--------:|----------------------------------:|
| 0.01 | 1.00 | 0.95 | 1.00 | 12.65 | ~76* | ~0.35 (~3%) |
| 0.02 | 0.95 | 0.82 | 0.95 | 12.31 | ~47 | ~0.69 (~5%) |
| 0.05 | 0.65 | 0.30 | 0.55 | 7.6 | ~42 | ~5.4 (~42%) |

\*0.01 subsample includes occasional heavy ticks (p95 ~324 ms).

## Critical adaptive question

Can adaptive reproduce most FULL COMPOSITE outcomes with fewer candidates?

**Tradeoff (not a winner):**

- At **0.02**: high locomotion/class agreement (~95%) and solid composite agreement (~82%), but candidate count stays close to full (~12.3 vs 13) — little cost saving.
- At **0.05**: meaningful candidate reduction (~42%) and slightly lower runtime, but locomotion agreement drops to **65%** and composite agreement to **30%** — loses many full-composite outcomes.

So adaptive can approximate full-composite **locomotion** outcomes at low thresholds with almost no candidate savings, or save candidates at higher thresholds by sacrificing agreement. Choose explicitly; do not auto-promote.

## Artifacts

`results/full_composite_psc_shadow/adaptive_frontier.json`, `performance.json`

## STOP

Do not enable ADAPTIVE as production PSC based on this study alone.
