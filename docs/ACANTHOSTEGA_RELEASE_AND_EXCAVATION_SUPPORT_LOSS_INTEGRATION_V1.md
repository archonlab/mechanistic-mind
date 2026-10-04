# ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION_V1

## Status

**Implemented.** Free-Space V1D closes RELEASE and excavation entry into the shared
V1A → FGG → V1B → V1C chain. No private landing or acoustic path.

## Identity

| Field | Value |
|-------|-------|
| Preset | `ACANTHOSTEGA_BETA4_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION` |
| Parent | `ACANTHOSTEGA_BETA4_VERTICAL_IMPACT_ACOUSTIC_EMISSION` |
| Mechanism | `release_and_excavation_support_loss_integration` |
| Profile | `RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION_V1` |
| Receipt | `RELEASE_EXCAVATION_SUPPORT_LOSS_V1` |
| Stage | `FREE_SPACE_V1D_RELEASE_EXCAVATION_INTEGRATION` |
| Model line | `ACANTHOSTEGA` |

## Cumulative inheritance

Parent V1C tip plus exactly-once: Beta 4 physical/material line, V1A, V1B, V1C, FGG,
continuous surface geometry, radius-aware support, conservative excavation, LPS.

## Part A — RELEASE

### Pose authority

Uses authoritative held object state at RELEASE:

- `x/y/z` from held object (base/feet)
- `centre_z = z + vertical_half_extent`
- no glyph, teleport, or placement-candidate search

### Velocity authority

| Component | Source |
|-----------|--------|
| `vx/vy` | Existing FOK effector finite-difference (`measure_effector_velocity` → `apply_release_transfer`) |
| `vz` | Holder body `vz` at `apply_release_vertical` |

No throwing impulse. Non-finite velocity → anomaly token, zeroed deterministically.

### Eligibility

On release tick `T`:

- HELD → FREE
- `release_tick = T`
- `dynamics_eligible_tick = max(existing, T+1)`
- V1A support classification recorded
- **no** independent FOK/FGG integration on `T`
- **no** V1B / V1C on `T`

On `T+1`: ordinary shared FREE path once.

### Support classification at release

1. At support + rest-compatible → `SUPPORTED` (no impact/sound)
2. Above support → `UNSUPPORTED` (gravity eligible T+1)
3. Below support → `RELEASE_START_PENETRATION` anomaly; no snap/sound; bounded correction deferred to first eligible V1B
4. Geometry unavailable → explicit anomaly; no NaN fallback

## Part B — Excavation support-loss

### Trigger

Only after successful committed terrain mutation (SETMR → WMT → CSMS/CSCT sparse delta).
Rejected placement / rollback / Observer reads do **not** refresh.

### Affected-entity selection

Policy: `BOUNDED_DYNAMIC_ENTITY_SCAN_BILINEAR_RASP_VERIFY_V1`

- Bodies (incl. TwoAgent + experimenter via `detached_placement_body_refs` / host runtime)
- FREE ResourceObjects
- Exclude HELD / deposits / terrain components
- Bilinear: CSG cell-centre lattice four-corner dependency (`floor(x-0.5)` indexing)
- Radius-aware: centre + 8-ring sample poses when RASP ON (physical/collision radius; never optical)
- Verify each candidate by resampling authoritative support after mutation
- Scaling seam: full dynamic-entity scan for V1 completeness (documented; not false-negative index-only)

### Refresh dedup

Per-entity/tick ledger: max one authoritative `SUPPORT_LOST` reclassification.
Subsequent mutations same tick → `REFRESH_DEDUPLICATED`.
Ordering: kind then stable ID ascending.

### Support-loss commit

- Preserve `x/y/z/vx/vy/vz`
- `grounded = false`; traction/friction ineligible
- No downward snap; no free lift; no second FGG this tick
- End active terrain episode once (`SUPPORT_LOSS_TERRAIN_MUTATION`)
- Gravity begins next ordinary eligible vertical step → shared V1B → shared V1C

Also wires `note_authoritative_surface_mutation` on V1D-active commits (parent left CSG bump unwired).

## Shared pipeline

Both paths converge on:

```
V1A UNSUPPORTED → existing FGG → existing V1B → existing V1C
```

`SPECIAL_CASE_LANDING_PATH = NO` · `SPECIAL_CASE_SOUND_PATH = NO`

## Tick order (preserved)

**RELEASE:** free-object integration → manipulator/RELEASE → pose/velocity/state →
episode termination → support classify → spatial reconcile once → no free integration until T+1 →
later FGG/V1B/V1C → LPS once

**EXCAVATION:** actuation → SETMR/WMT commit → sparse delta + CSG bump →
deduplicated support refresh → support-loss/episode END → no second FGG →
next tick FGG → later V1B/V1C → LPS once

Note: runtime still runs FGG before excavation within a tick (architecture audit delta);
V1D does not reorder the pipeline — descent starts next eligible step.

## Snapshot / restore

Persists refresh ledger, pending changed cells, event seq, history, counters.
Restore does not replay RELEASE, terrain transaction, support loss, landing, or sound.

## Cognition privacy

Forbidden tokens include `RELEASE_EXCAVATION_SUPPORT_LOSS_V1`,
`RELEASE_VERTICAL_ELIGIBILITY`, `SUPPORT_LOST_TERRAIN_MUTATION`,
`AFFECTED_ENTITY_SELECTION`, `CHANGED_REGION`, `REFRESH_DEDUP`,
`TERRAIN_TRANSACTION_ID`, `RELEASE_START_PENETRATION`, …

## Observer / Analyzer

- One selector entry; cumulative parentage; single Apply; selected≠active
- Banner: FREE-SPACE ENTRY INTEGRATION · RELEASE + EXCAVATION SUPPORT LOSS · …
- Analyzer section: `RELEASE / EXCAVATION FREE-SPACE ENTRY`

## Explicit non-goals (unchanged)

No new fall/landing/sound integrators; no DROP/PIT semantics; no visible elevation
rendering; no 3D index; no human playback; no global energy conservation claim.

## Next stage

`OBSERVER_ELEVATION_EXCAVATION_FREE_SPACE_VISUALIZATION`
