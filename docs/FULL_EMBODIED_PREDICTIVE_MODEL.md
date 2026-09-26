# FULL EMBODIED PREDICTIVE MODEL

## Summary

Default SMC allowlist now covers all 39 audited agent-accessible observation
scalars (families ON). Learning uses full COMPOSITE_MOTOR_V1 signatures.
PSC candidate SMC queries remain locomotion-factorized.

## Channel families

See `FAMILY_CHANNELS` in `sensorimotor_consequence.py`.

WITHHELD: `empty_store(families={...})` / `set_families` / CognitionConfig
`sensorimotor_consequence_families`.

## Acceptance

- COMPOSITE_MOTOR_PREDICTION_DEMONSTRATED (learning/query with full motor)
- COMPOSITE_MOTOR_ALIASING_DEMONSTRATED (PSC query_candidates)
- ONE_ACTION_MULTIMODAL_FUTURE_DEMONSTRATED
- Sensory coverage 39/39 allowlist vs live observation

## Wet-world

`psyweb-20260921T112403.271716Z-d68cde67` seed 111, 200+150 ticks.
Status: PARTIALLY_REPRESENTED (PSC aliasing).
Artifacts: `results/full_embodied_predictive_model/`

## Next design decision

Whether PSC should evaluate full composite motor candidates, factorized
side-channel SMC queries, or keep loco-only competition with post-hoc side
channels (current).
