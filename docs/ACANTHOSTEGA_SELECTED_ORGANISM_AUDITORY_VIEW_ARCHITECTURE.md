# SELECTED ORGANISM AUDITORY VIEW — Architecture Audit

**Status:** Architecture / privacy / scientific-semantics only.  
**IMPLEMENTATION_STARTED = NO** · **TOTAL_SIMULATED_TICKS = 0**

## Purpose

Second listening/inspection mode: inspect (and later optionally sonify) the auditory values **actually available** to one selected organism through its phenotype — stopping **before** cognition.

Not: raw probe field · ORIGINAL · mind reading · memory/prediction · semantic labels.

## Authoritative pre-cognition boundary (V1 terminal)

**Layer A5 — agent-accessible auditory sensor values**  
Concrete fields: `osc_l_0…5`, `osc_r_0…5` as delivered in `accessible_observation` / `last_agent_observation`.

These are:
- post-phenotype (receptor geometry + `sensor_scale` + clip `[0,1]`);
- pre-cognition (inputs *to* `run_cognition_before_action`, not outputs);
- agent-accessible;
- anonymous (no source id/bearing/distance).

Prefer **decision-tick** `last_agent_observation` / ObservationReceipt over live recompute for SAV identity.

## Distinct from C1

| Mode | Input | Nature |
|------|-------|--------|
| C1 Canonical physical-field sonification | Passive probe mono energies | Pre-phenotype researcher field |
| Selected organism auditory view | Selected body `osc_l/r` | Post-phenotype sensory boundary |

## Gate

**READY_WITH_CONSTRAINTS** — boundary exists; recommend SAV1 visual + lightweight same-tick receipt (clip/phenotype stamp) before sonification.

## Evidence

`results/acanthostega_selected_organism_auditory_view_architecture/`
