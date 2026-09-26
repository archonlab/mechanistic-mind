# PSC ADAPTIVE REFINEMENT STUDY

## Rule (empirical only)

Refine a locomotion candidate iff ≥2 unique motor signatures with predictions AND max pairwise O′ divergence ≥ threshold.

## Threshold frontier (synthetic CASE B, max_div≈0.044)

| threshold | would_refine | n_candidates |
|-----------|--------------|--------------|
| 0.001–0.02 | YES | 2 |
| ≥0.05 | NO | 1 |

## Cost / information (wet)

| Architecture | Candidates/tick | Notes |
|--------------|-----------------|-------|
| LOCO_ONLY | locomotion set | loses within-loco composite Δ |
| OBSERVED_COMPOSITE | ~9 unique sigs | no Cartesian |
| ADAPTIVE @0.02 | refine when Δ high | threshold-sensitive |

No automatic winner. Do not promote to production in this task.
