# PSC MOTOR RESOLUTION AUDIT

## Production query path (verified)

1. `cognition.run_cognition_before_action` builds `select_actions = locomotion_options(actions)` when `composite_motor` ON.
2. Calls `smc.query_candidates(store, observation, loco_candidates=select_actions)`.
3. For each loco, builds motor `{locomotion: L, neck: NONE, oscillator: {}, push: False}`.
4. `smc.query` looks up exact signature `L:{L}|N:NONE|E:0|F:0|A:0|P:0` with context match / L1 similarity.
5. If UNKNOWN: **loco_prefix_aggregate** = pick the **single highest-support** record whose `motor_signature` starts with `L:{L}|` (NOT a mean across composites).
6. Surviving info: one composite's mean_delta (often the most practiced side-channel combo).
7. Discarded: other empirically supported composites under the same loco; forced NONE/empty may miss exact match even when composites exist.
8. Matching is context-sensitive via `_find_row` (exact key then same-motor L1 ≤ SIM_THRESHOLD).
9. Predictions attach to PSC as locomotion-keyed MATCH evidence; O′ history bridge also consumes these loco-level preds.
10. Side channels (neck/osc/push) are selected **after** loco competition (`COMPOSITE_FACTORIZED`).

## Learning vs PSC

| Path | Motor identity |
|------|----------------|
| SMC `update` | Full `L|N|E|F|A|P` |
| PSC `query_candidates` | Loco-only defaults + max-support prefix fallback |

## Shadow architectures (analysis only)

- **LOCO_ONLY** — mirrors production
- **OBSERVED_COMPOSITE** — unique empirically supported signatures under each loco (no Cartesian)
- **ADAPTIVE_REFINEMENT** — refine when within-loco pairwise O′ divergence ≥ threshold

Production selection was **not** changed. Shadow uses store snapshots so query counters do not mutate live cognition.

## Key wet-world findings (seed 111 shadow, 150+100 ticks)

- EXACT_MATCH with/without shadow: **TRUE**
- High within-loco divergence (≥0.02): common after experience
- Out-of-manifold aggregate: **0** (NOT_DEMONSTRATED)
- Unique-signature candidates/tick after dedupe: ~p50 **9**
- Neck → optical/proprio largest ablation effects; osc_emit → bilateral

Artifacts: `results/psc_motor_resolution/`
