# ACANTHOSTEGA_FREE_SPACE_Z_DYNAMICS_ARCHITECTURE

**Architecture audit only.** `IMPLEMENTATION_STARTED = NO`.  
Does **not** implement V1A or later. Does **not** restate Beta 4 closure scenarios.

## Freshness

| Field | Value |
|-------|-------|
| cwd | `<repository-root>` |
| branch | `main` |
| HEAD | `5d0f14cd7968b4d5b190796a2494d348a0e10f48` |
| dirty | ~288 paths preserved |
| live Observer | not mutated |
| parent tip (context only) | `ACANTHOSTEGA_BETA4_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION` |
| Beta4 closure | remains PASS (not re-audited here) |

## Pack status (this corrective pass)

| File | Prior | This pass |
|------|-------|-----------|
| This doc + 10 results/* | Existed 2026-09-29 | **Re-verified vs code**; corrected claims on grounded-rest dissipation, landing-fact distinction, first-slice preset identity, PE table |

## Executive verdict (code-grounded)

Phase C `flat_ground_gravity.integrate_vertical_entity` **does** integrate unsupported entities through `z` with semi-implicit Euler against `support_z = h(x,y)` (SES/CSG). Probe: fall from `z=1` lands in 10 ticks; mass-independent `a_z = −g`.

That is **genuine unsupported vertical integration**, but it is **not** Free-Space V1 complete:

| Concern | Current |
|---------|---------|
| Unsupported multi-tick descent | YES (`flat_ground_gravity.py`) |
| Landing contact episode (BEGIN/PERSIST/END) | **NO** — only `landed` flag inside `VERTICAL_PHYSICAL_STEP` / `FLAT_GROUND_SUPPORT` |
| Mass/compliance vertical impulse | **NO** — inelastic clamp, `restitution=0` |
| Vertical impact acoustics | **NO** — `landing_sound=False` hardcoded |
| PE exclusivity formalized | **PARTIAL** — Policy C skips airborne endpoint PE; FGG still applies `g` then clamps **every grounded rest tick**, dissipating artificial `support_dissipated` |
| Free-Space V1 product stage | **NOT IMPLEMENTED** |

```text
CURRENT_GRAVITY_IS_GENUINE_FREE_SPACE = YES
FREE_SPACE_V1_IMPLEMENTED = NO
FREE_SPACE_V1_READY_TO_IMPLEMENT = YES
VOLUMETRIC_TERRAIN_REQUIRED_FOR_V1 = NO
FREE_SPACE_V2_REQUIRED_BEFORE_V1 = NO
SES_REFACTOR_REQUIRED_BEFORE_V1 = NO
BLOCKER = NONE
VERDICT = FREE_SPACE_V1_ARCHITECTURE_READY
```

## Ontology (V1 target)

support absent → gravity → `z`/`vz` evolve → terrain contact fact → vertical response → dissipation → acoustics (later) → support or rebound.  
No semantic FALL/JUMP/CLIMB/FLY/DROP.

## Representation

`support_z = h(x,y)` from procedural columns + sparse deltas; CSG bilinear when ON.  
Entity **base/feet** `z` authoritative; `centre_z = z + vertical_half_extent`. No z wrap; no upper bound; no dense voxels.

## First implementation slice (dependency-correct)

**Must precede landing impulse/acoustics** because grounded-rest currently applies `g` then clamps every tick (`skip_gravity` unused by callers). Without a support-state + PE gate, later impact acoustics would inherit false “landing-like” dissipation on every rest tick.

```text
RECOMMENDED_FIRST_PRESET    = ACANTHOSTEGA_BETA4_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
RECOMMENDED_FIRST_PARENT    = ACANTHOSTEGA_BETA4_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
RECOMMENDED_FIRST_MECHANISM = free_space_state_and_pe_authority_contract
RECOMMENDED_FIRST_PROFILE   = FREE_SPACE_STATE_PE_AUTHORITY_PROFILE_V1
RECOMMENDED_FIRST_RECEIPT   = FREE_SPACE_SUPPORT_STATE_V1
RECOMMENDED_NEXT_SLICE      = FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT_V1
```

**Physics effect (V1A):** explicit SUPPORTED/UNSUPPORTED authority; PE mutual exclusion; **physics-equivalent rest** (no gravity when already at support with `vz≈0`); release grounded vs `support_z`; researcher receipts/snapshot fields. **No** new fall integrator; **no** landing impulse; **no** impact sound.

**Following:** vertical terrain contact/response → vertical impact acoustics → release/excavation hardening.

## Evidence index

`results/acanthostega_free_space_z_dynamics_architecture/`
