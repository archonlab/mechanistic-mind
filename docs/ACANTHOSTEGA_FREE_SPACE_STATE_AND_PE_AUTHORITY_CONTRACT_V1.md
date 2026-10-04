# ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT_V1

## Identity

| Field | Value |
|-------|-------|
| Public preset | `ACANTHOSTEGA_BETA4_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT` |
| Parent | `ACANTHOSTEGA_BETA4_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION` |
| Mechanism | `free_space_state_and_pe_authority_contract` |
| Profile | `FREE_SPACE_STATE_PE_AUTHORITY_PROFILE_V1` |
| Receipt | `FREE_SPACE_SUPPORT_STATE_V1` |
| Architecture stage | `FREE_SPACE_V1A_STATE_AND_PE_AUTHORITY_CONTRACT` |
| Model line | `ACANTHOSTEGA` |

## Purpose

Formalize existing body/free-object vertical support state and mutually exclusive PE authority on top of Phase C FGG. Do **not** replace the FGG semi-implicit integrator. Do **not** implement landing contact fact, compliance impulse, restitution/rebound, or vertical impact acoustics.

## State values (repository enum)

| Contract state | Meaning |
|----------------|---------|
| `SUPPORTED` | Geometrically on support; rest gate eligible |
| `UNSUPPORTED` | Above / off support; FGG owns vertical PE↔KE |
| `TERRAIN_INTERSECT` | Existing inelastic clamp episode this tick |
| `REBOUND` | Reserved / inactive under current inelastic clamp |
| `CONSTRAINED_HELD_NOT_INDEPENDENT` | HELD objects (researcher-only) |
| `NOT_APPLICABLE` | Initial / excluded |

## Supported-rest gravity gate

When V1A is ON and an entity begins its vertical step at authoritative supported rest (`grounded`, `|z−support_z|≤ε`, `|vz|≤ε`):

- skip downward gravity impulse
- preserve `z = support_z`, `vz = 0`
- record `GRAVITY_SKIPPED_VALID_SUPPORT`
- no artificial dissipated landing energy
- no contact / impulse / sound

Gate does **not** suppress gravity when support is lost, entity is above support, `vz` indicates motion, terrain was lowered, release above support, newborn unsupported eligibility, or support geometry is invalid.

## PE authority (mutually exclusive)

| Path | Authority |
|------|-----------|
| Supported terrain | `PE_AUTHORITY_SUPPORTED_TERRAIN` (SES / continuous support-height) |
| Unsupported free-space | `PE_AUTHORITY_UNSUPPORTED_FREE_SPACE` (FGG vertical PE↔KE) |
| HELD | `PE_AUTHORITY_HELD_NO_INDEPENDENT` |
| Clamp dissipation class | `CURRENT_INELASTIC_CLAMP_DISSIPATION` (classification only) |

Invariant: `double_pe_authority = false`, `active_pe_authority_count ≤ 1` for one entity/tick.

## Ground-force eligibility

Shared predicate: `ground_forces_eligible(entity) ≡ entity.grounded`. When UNSUPPORTED, `grounded=False` immediately after support loss → body/object static traction, kinetic ground friction, surface-affinity ground reaction, and Gentle grounded damping do not act as ground contact.

## Support loss / excavation / release / newborn

- Support loss: no z snap, no free lift; ground forces off; FGG starts next ordinary eligible vertical step.
- Terrain mutation: `SUPPORT_LOST_TERRAIN_MUTATION` + `SAME_TICK_FLAG__VERTICAL_NEXT_ELIGIBLE_STEP` (no second integration).
- RELEASE: record HELD→FREE; preserve released z; inherit holder `vz`; T+1 vertical eligibility; classify support after release.
- Newborn: preserve `dynamics_eligible_tick = creation_tick + 1` (DTIP authority); no same-tick landing/impulse/sound.

## Tick order (final)

1. Material / excavation transactions (existing) → may note support loss
2. Body horizontal / SES locomotion (existing)
3. Body vertical FGG (`integrate_body_vertical`) → contract receipt
4. Shared FREE object FGG (`integrate_free_objects_vertical`) once per world tick → contract receipt
5. HELD objects: constrained follow / no independent gravity
6. Body↔object / object↔object contact chains (unchanged order)
7. LPS advance exactly once
8. Observer serialize reads (no mutation)

## Spatial index

Remains 2D broad-phase. No 3D index in this slice.

## Snapshot / restore

Persists contract state (last_state_by_entity, bounded history, counters, config). Restore does not replay gravity, clamp dissipation, or transition receipts. Tiktaalik / mechanism OFF: no new fields injected.

## Explicit non-goals

Landing contact fact · compliance vertical impulse · rebound · vertical impact sound · new fall integrator · 3D index · FPV · Analyzer progress bar · semantic FALL/JUMP · global energy conservation claim.

## Next seam

`VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE_V1`  
(separate from `VERTICAL_IMPACT_ACOUSTIC_EMISSION_V1` and `RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION_V1`)
