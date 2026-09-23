# OBSERVED_COMPOSITE PSC PRODUCTION MODE

**EXPERIMENTAL.** Default remains `LOCO_FACTORIZED`. ADAPTIVE_REFINEMENT is not a production mode.

## Config

```
CognitionConfig.psc_motor_resolution: "LOCO_FACTORIZED" | "OBSERVED_COMPOSITE"
```

- Missing / legacy configs → `LOCO_FACTORIZED` via `observed_composite_psc.normalize_mode`
- Observer: `POST /api/config/psc-motor-resolution` `{ "mode": "..." }`
- Hot-toggle records config history; **no** history/SMC/body/cognition reset

## Semantics (OBSERVED_COMPOSITE)

When PSC competition is active, SMC + HSS are on, and mode is OBSERVED_COMPOSITE:

1. Retrieve empirically supported composite signatures (no Cartesian product)
2. Full composite `smc.query`
3. `construct_o_prime` → `query_history_on_o_prime` → `build_psc_scenario`
4. `compete_scenarios` over composite keys
5. Winning **full** `COMPOSITE_MOTOR_V1` proceeds to physical realization
6. **No** legacy `select_factorized_side_channels` overwrite after a full winner

If insufficient composite scenarios: fall back to LOCO_FACTORIZED for that tick (receipt notes `FALLBACK_LOCO`).

## Functions reused

Same as shadow replay validation:

- `sensorimotor_consequence.query`
- `o_prime_history_bridge.construct_o_prime`
- `o_prime_history_bridge.query_history_on_o_prime`
- `o_prime_history_bridge.build_psc_scenario`
- `scenario_competition.compete_scenarios`

Module: `mechanistic_mind/physical_system/observed_composite_psc.py`

## Acceptance

| Gate | Result |
|------|--------|
| LOCO_FACTORIZED_EXACT_MATCH | PASS (pytest) |
| OBSERVED_COMPOSITE_PRODUCTION_PATH_DEMONSTRATED | PASS (synthetic) |
| NO_CARTESIAN_INVENTION | PASS |
| FULL_COMPOSITE_WINNER_REACHES_PHYSICAL_MOTOR | PASS (selection_source=OBSERVED_COMPOSITE_PSC; domain_sources not COMPOSITE_FACTORIZED) |
| CONFIG_HISTORY_RECORDS_MOTOR_RESOLUTION | PASS |

## DecisionReceipt

Additive fields:

- `psc_motor_resolution`
- `observed_composite_selection` (compact candidate evidence)

## STOP

Do not make OBSERVED_COMPOSITE the default. Do not promote ADAPTIVE. No git push.
