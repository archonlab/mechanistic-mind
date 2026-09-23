# FULL EMBODIED PREDICTIVE MODEL — AUDIT

## Core question

Does existing SMC model the whole agent-accessible / agent-controllable Tiktaalik?

**Answer:** Sensory observation interface — **yes (after allowlist extension)**.
Composite motor at **learning** — **yes**. Composite motor at **PSC candidate query** — **no (aliased to locomotion)**.

## Observation inventory (production)

39 agent-accessible scalar keys from `accessible_observation` / live TwoAgent:

| Family | Keys | Classification | Receipt | SMC before | SMC after |
|--------|------|----------------|---------|------------|-----------|
| optical | exo_0..2 | PREDICTABLE_PHYSICAL_SENSOR | YES | YES | YES |
| field | local.FIELD_A/B | PREDICTABLE_PHYSICAL_SENSOR | YES | YES | YES |
| bilateral | osc_l_0..5, osc_r_0..5 | PREDICTABLE_PHYSICAL_SENSOR | YES | YES | YES |
| vestibular | vest_0..1 | PREDICTABLE_BODY_SENSOR | YES | YES | YES |
| proprioception | prop_neck_0..1 | PREDICTABLE_BODY_SENSOR | YES | YES | YES |
| local_world | local.T, M0..2, vx, vy | EXOGENOUS_BUT_PREDICTABLE | YES | NO | YES |
| body | body.B0..2, T, mech, vx, vy | PREDICTABLE_BODY_SENSOR | YES | NO | YES |
| internal | internal.c0..4 | PREDICTABLE_BODY_SENSOR | YES | NO | YES |

Vision: cognition sees only `exo_0..2`. Foreign-body optical / body_exposure are Observer GT — OBSERVER_ONLY.

## Motor inventory (COMPOSITE_MOTOR_V1)

| Dimension | Controlled | Physical | Receipt | SMC learning | SMC PSC query |
|-----------|------------|----------|---------|--------------|---------------|
| locomotion | YES | YES | YES | YES | YES |
| neck | YES | YES | YES | YES | ALIASED (forced NONE) |
| oscillator emit/freq/amp | YES | YES | YES | YES | ALIASED (forced empty) |
| push | YES | YES | YES | YES | ALIASED (forced False) |
| TAKE/RELEASE/CONTACT | — | — | — | N/A | N/A |
| separate body rotation | — | — | — | N/A | N/A |

Learning signature: `L:{loco}|N:{neck}|E:{emit}|F:{fd}|A:{ad}|P:{push}` — distinct for neck/osc/push.

PSC path: `query_candidates` builds `{loco, neck:NONE, osc:{}, push:False}` then `loco_prefix_aggregate`.

**COMPOSITE_MOTOR_INFORMATION_LOSS_DETECTED** at PSC query path (intentional factorization; not silent legacy MOVE:N-only at learn time).

## Temporal alignment

`smc.update(observation_t=previous, motor=last_motor_output, observation_t1=current)` — OK.

## Privileged information

No Observer GT / bearing / source id in SMC channels.

## Gap map BEFORE → AFTER

See `results/full_embodied_predictive_model/GAP_MAP_*.json`.

BEFORE: 18 accessible sensory keys omitted from SMC; PSC query aliasing.
AFTER: 0 sensory omissions on default allowlist; PSC query aliasing **unchanged** (design decision).

## Auto-repair performed

- Extended allowlist with local_world / body / internal families
- Family WITHHELD controls: visual, field, vestibular, proprioceptive, bilateral, local_world, body, internal
- bilateral WITHHELD preserved

## Auto-repair NOT performed

- PSC `query_candidates` Cartesian / full-composite candidate evaluation (combinatorial / architecture change)
