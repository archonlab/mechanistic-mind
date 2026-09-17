# Experience-Gated Cognitive Depth — Acceptance Report

Date: 2026-09-10
Full `pytest -q`: PASS after Update 2.

## Audit summary (Update 1 → 2)

Update 1 gate was global (ticks + structure). Update 2 keeps global metrics/ceiling and adds local maturity from bounded current-cue evidence; effective depth can fall in novel contexts after early ceiling rises.

## Acceptance 1–30

1. PASS — one continuous PSYCHE-SENSORIMOTOR-V05
2. PASS — no adult system replacement
3. PASS — memory continuous across depths
4. PASS — newborn low depth from insufficient evidence (local + early ceiling)
5. PASS — depth increases with relevant local evidence (unit + A)
6. PASS — not tick-only (`test_maturity_not_tick_only`, local gates)
7. PASS — not memory-size (`test_depth_not_memory_size_alone`)
8. PASS — local evidence affects depth
9. PASS — contradictory evidence limits maturity
10. PASS — mature depth available when supported
11. PASS — mature novel context reduces depth (`test_mature_novel_context_reduces_depth_without_global_reset`, B)
12. PASS — no global psyche reset on novelty
13. PASS — memories preserved after local reduction (B keys preserved)
14. PASS — new evidence can raise local depth (architecture + late B)
15. PASS — related-bucket transfer weighted; weak analogies do not equal rich evidence
16. PASS — weak/empty local cannot receive mature authority
17–21. PASS — no curiosity/novelty/forced exploration/semantic/privileged world paths added
22. PASS — body signals untouched
23. PASS — low-depth experience remains ordinary contingencies
24. PASS — observer fields on memory.developmental / telemetry
25–26. PASS — bounded retrieval budget 12; compression constraints intact
27. PASS — ADULT_FROM_TICK_0 available
28. PASS — legacy developmental experiment still importable/runnable
29. PASS — full regression green
30. PASS — DISABLED disables gating

## Experimental smoke (seed 17, phase_a=30, phase_b=20)

See experiments/experience_gated_depth_v02_result.json. Short horizons; no superiority claim.

## Limitations

- Cue similarity for transfer is conservative (visible-token overlap).
- Novelty swap replaces world state via alternate ecology seed; not a packaged curriculum.
- Amnesia control C is prepared/smoke only.
- Production tick defaults remain 3k/5k/10k.
