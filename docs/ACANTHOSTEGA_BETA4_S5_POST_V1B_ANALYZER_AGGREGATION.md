# Acanthostega Beta 4 — S5 Post-V1B Analyzer Aggregation

Schema: `BETA4_S5_POST_V1B_ANALYZER_AGGREGATION_V1`  
Authority: `ACCEPTED_GEN_POST_V1B_VERTICAL_SUPPORT_ESCAPE_REPAIR`  
Generation: `GEN_POST_V1B_VERTICAL_SUPPORT_ESCAPE_REPAIR`

## Scope

Read-only aggregation over the **accepted** post-V1B repaired-physics primary packages
(`results/acanthostega_beta4_repaired_physics_primary_revalidation/`).  
`TOTAL_SIMULATED_TICKS = 0`. Historical pre-repair S5/S6 are **not** overwritten and do **not**
enter the confirmatory pool.

## Inclusion

- 40/40 primary packages  
- 80,000 primary ticks (evidence already simulated; this seam executes **zero** new ticks)  
- Pilot / pre-repair / C8 excluded  

## Provisional H1–H10

| H | Status |
|---|--------|
| H1 | `PASS` |
| H2 | `PASS` |
| H3 | `INCONCLUSIVE_MISSING_EVIDENCE` |
| H4 | `PASS` |
| H5 | `PASS` |
| H6 | `PASS` |
| H7 | `PASS` |
| H8 | `INCONCLUSIVE_CAPABILITY_NOT_EXERCISED` |
| H9 | `FAIL` |
| H10 | `INCONCLUSIVE_UNDERPOWERED` |

## Next seam

`S6_POST_V1B_SCIENTIFIC_BEHAVIORAL_CLOSURE` — **not** started by this stage.

## Artifacts

See `results/acanthostega_beta4_s5_post_v1b_analyzer_aggregation/`.
