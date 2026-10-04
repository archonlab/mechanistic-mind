# ACANTHOSTEGA_RELEASE_EXCAVATION_SUPPORT_LOSS_INTEGRATION_ARCHITECTURE

## Status

**Implemented** as Free-Space V1D tip:
`ACANTHOSTEGA_BETA4_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION`

See `docs/ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION_V1.md`
and `results/acanthostega_release_excavation_support_loss_integration_v1/FINAL_REPORT.md`.

Architecture audit only was the prior task; runtime physics for the selected
combined slice is now closed.

## Parent tip (verified)

| Field | Value |
|-------|-------|
| Public preset | `ACANTHOSTEGA_BETA4_VERTICAL_IMPACT_ACOUSTIC_EMISSION` |
| Model line | `ACANTHOSTEGA` |
| V1A | ON (inherited) |
| V1B | ON (inherited) |
| V1C | ON |
| LPS | ON, once per scientific tick |

## Problem

V1A/V1B/V1C implement unsupported descent → landing → sound, but the two major **entry** paths into that shared chain are incomplete or inconsistently stamped:

1. **RELEASE** (HELD → FREE at authoritative pose/velocity)
2. **Excavation support loss** (terrain lowers under grounded entity)

## Code vs docs (material)

| Claim | Doc | Code |
|-------|-----|------|
| V1A tick order: excavation before FGG | V1A doc lists excavation first | Runtime typically runs FGG verticals, then manipulator/excavation |
| `SAME_TICK_FLAG__VERTICAL_NEXT_ELIGIBLE_STEP` | Documented on terrain mutation | Not emitted as a receipt token |
| `occupied_entities_at_cell` includes bodies | Docstring says bodies + FREE | **Loops only `resource_objects`** |
| CSG generation bump on mutation | Implied by CSG cache design | `note_authoritative_surface_mutation` **never called** from commit paths |
| Release stamps `dynamics_eligible_tick` | Parallel to newborn T+1 | **Not stamped** on RELEASE; T+1 emerges from tick order only |

## Verdict

**A — combined integration slice**

`RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION_V1`

Safe as one child of V1C tip. Internally stage:

1. Excavation affected-entity / support-refresh completeness
2. Release eligibility + provenance parity with newborns
3. Shared handoff into existing V1B/V1C (no private landing/sound paths)

No pose/velocity redesign required for release. No V1B/V1C redesign.

## Recommended identity (next implementation)

| Field | Value |
|-------|-------|
| Preset | `ACANTHOSTEGA_BETA4_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION` |
| Parent | `ACANTHOSTEGA_BETA4_VERTICAL_IMPACT_ACOUSTIC_EMISSION` |
| Mechanism | `release_and_excavation_support_loss_integration` |
| Profile | `RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION_V1` |
| Receipt | `RELEASE_EXCAVATION_SUPPORT_LOSS_V1` |

## Following visualization (after implementation)

`OBSERVER_ELEVATION_EXCAVATION_FREE_SPACE_VISUALIZATION`

Only after this integration is implemented and validated.

## Prospective

`PROSPECTIVE_RELEASE_EXCAVATION_FREE_SPACE_SUPPORT = NOT_ESTABLISHED`
