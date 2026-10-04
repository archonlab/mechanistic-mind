# Acanthostega Phase B — Conservative Surface Column Transfer

Preset `ACANTHOSTEGA_PHASE_B_COLUMN_TRANSFER` (UI: *Acanthostega Phase B Column Transfer*) inherits
`ACANTHOSTEGA_PHASE_B_PROCEDURAL_COLUMNS` and adds mechanism `conservative_surface_column_transfer`
(ON only in this preset; forced ON for Tiktaalik stays OFF; missing snapshot field means OFF).

The stage adds one researcher-only world-mutation primitive: `TRANSFER_SURFACE_COLUMN_SLICE`. The source column
loses one contiguous top slice and the destination gains exactly that slice. Both results persist as sparse
deltas and are committed in one atomic world-material transaction.
It is **not** DIG/MINE, a resource spawn, a reward, an agent action, a tool use, piles, gravity, support or collision.
The correct name for the result is a *persistent authoritative geometry scar with physical effects inactive*.

## 1. Semantics audit (existing, before this stage)
All references are to `mechanistic_mind/physical_system/procedural_surface_columns.py` (psc).

| Quantity | Existing definition |
|---|---|
| `surface_elevation` | `generate_baseline_v1`: `elevation_amplitude*(2*noise-1)`, amplitude 0.5. Independent of the layers. Authoritative geometry metadata; no consequence kernel reads it. |
| `modelled_depth` | `cfg.modelled_depth = 4.0`. Baseline layers tile `[0, 4.0)` exactly (the last bottom is forced equal to the depth). |
| interval | `BOUNDARY_POLICY = HALF_OPEN_TOP_INCLUSIVE_BOTTOM_EXCLUSIVE`. `[top_depth, bottom_depth)`, depth measured down from the local surface (`material_at_depth`). |
| density | Per-layer constant, from generator parameters (1.4/1.9/2.5 ± noise). |
| quantity | `SurfaceMaterialLayer.quantity_per_area = thickness` (volume per unit area). |
| mass per area | `SurfaceMaterialLayer.mass_per_area = thickness*density`. |
| composition | Sorted tuple `(component_id, amount)` in quantity units. `validate_layers` checks that `sum(amounts) == thickness` to 1e-9 and that the layers are contiguous to `TOLERANCE = 1e-12`. |
| sparse delta | `SurfaceColumnDelta` replaces the resolved column wholesale (`resolved_column_at`). The id is stable per cell (`delta_id_for` gives `surface-column-delta-x{X}-y{Y}`). |
| baseline checksum | `_column_checksum(cell, elevation hex, exact layers, version)` (sha, 16 hex characters). |
| column revision | 0 without a delta; +1 per committed delta write. |

Mass is not equal to quantity (mass = quantity × density). Passive properties are derived state and are not conserved stock.

## 2. Datum / depth policy
The existing schema has elevation independent of `modelled_depth` (fixed 4.0). A transfer must change
elevation without creating or destroying material, so an explicit datum invariant is introduced:

```
fixed_lower_datum        = baseline_surface_elevation - baseline_modelled_depth      (per cell, constant)
resolved_modelled_depth  = resolved_surface_elevation - fixed_lower_datum
                         = modelled_depth + (elevation - baseline_elevation)       (psc.resolved_modelled_depth_for)
```
For a transfer of thickness `t`:
- source elevation −= t, and source resolved depth −= t;
- destination elevation += t, and destination resolved depth += t.

No material is added below the source, and the bottom layer is never regenerated.
Limits: `minimum_resolved_depth = 0.5` (source preflight reject `INSUFFICIENT_SOURCE_DEPTH`),
`maximum_resolved_depth = 64` (destination reject `DESTINATION_DEPTH_LIMIT`).
For untouched columns `resolved_column_at(...)["modelled_depth"]` is bit-identical to before (elevation delta 0).

## 3. Slice extraction and destination placement
- Only a contiguous top slice is moved: `0 < t <= T0` (thickness of the source top layer). `t > T0` gives `CROSSES_LAYER_BOUNDARY`.
- Slice (`split_top_slice`): density = source top density; component amounts `a_i * t / T0`; `volume = quantity = t`;
  `mass = t*density`. If `t == T0` (within 1e-12) the whole top layer is removed.
- Destination (`place_slice_on_top`): the slice becomes a new top layer `[0, t)`, and the old layers shift by +t.
- **Canonical adjacent merge** (`layers_mergeable`): the slice merges with the destination's top layer only if the
  derivation/generator version is equal, the density is equal within relative tolerance `merge_tolerance = 1e-12`,
  and the component set and proportions are equal within the same tolerance.
  There are no component-id special cases. Merging adds the amounts exactly, so no material is lost.
- `max_layers_per_column = 8`; exceeding it gives `LAYER_LIMIT_EXCEEDED` before commit.

## 4. Preflight (`plan_surface_column_transfer`, no mutation)
Checks run in this order:
1. mechanism active, `selection_provenance == INTERVENTION_SETUP`, `agent_action == false`;
2. generator version known (checked before the seed, because the namespace key depends on the generator);
3. authoritative world seed equals the runtime seed;
4. coordinates finite, then WRAP, then distinct;
5. expected revisions valid;
6. thickness finite/non-zero/positive;
7. baseline checksums;
8. stale revisions;
9. top layer exists; slice within the top layer; minimum/maximum depth;
10. layer limit; interval validation of both candidates; conservation closes; both deltas serialize;
11. delta capacity (`MAX_DELTAS = 4096`).

Rejection codes: MECHANISM_INACTIVE, INVALID_SELECTION_PROVENANCE, AGENT_ACTION_FORBIDDEN, SEED_AUTHORITY_INVALID,
UNKNOWN_GENERATOR_VERSION, NON_FINITE_COORDINATE, SAME_WRAPPED_CELL, INVALID_EXPECTED_REVISION, NON_FINITE_THICKNESS,
ZERO_THICKNESS, NEGATIVE_THICKNESS, SOURCE/DESTINATION_BASELINE_CHECKSUM_MISMATCH, STALE_SOURCE/DESTINATION_REVISION,
NO_SOURCE_TOP_LAYER, CROSSES_LAYER_BOUNDARY, INSUFFICIENT_SOURCE_DEPTH, DESTINATION_DEPTH_LIMIT, LAYER_LIMIT_EXCEEDED,
INTERVAL_VALIDATION_FAILED, CONSERVATION_FAILED, DELTA_NOT_SERIALIZABLE, DELTA_CAPACITY_EXCEEDED,
CANDIDATE_CONSTRUCTION_FAILED, ALREADY_COMMITTED, COLUMN_STATE_CHANGED_SINCE_PLAN, COMMIT_EXCEPTION.

## 5. Atomic pair commit
The commit goes through the existing WMT contract: `commit_material_transaction` handles ALREADY_COMMITTED, plan-rejected and `_stale`
(new additive `column:` key branch), then a dispatch branch `TRANSFER_SURFACE_COLUMN_SLICE`, then `commit_planned_transfer`:
1. re-check checksums and duplicate transfer id;
2. copy the delta map (`new = dict(deltas)`) and write the source and then the destination delta into the copy;
3. publish with a **single assignment** `world.surface_column_deltas = new`;
4. write one WMT ledger record and one causal event (`SURFACE_COLUMN_TRANSFER`).

An exception at any point before publish leaves both columns unchanged; the WMT try/except turns it into a rejection.
No state exists where only one column changed (tests 28–31).

## 6. Revisions, conflicts, identity, provenance
- Each committed transfer advances both column revisions by 1.
- Same-tick proposals go through `resolve_transfer_proposals`: order `PROPOSER_ID_THEN_CANONICAL_ADDRESS_V1`, plan all, then commit
  in order. The first valid commit advances the revision; later stale proposals reject (`STALE_*_REVISION`).
  All 6 permutations of 3 conflicting proposals give 1 distinct outcome.
- Each column keeps its own stable delta id. Both deltas carry the same `transaction_id` (`material-tx-TTTTTTTTT-SSSS`)
  and `transfer_id` (`surface-column-transfer-TTTTTTTTT-SSSS`).
- Delta provenance holds bounded refs: `last_transfer_id`, `transfer_role` (SOURCE/DESTINATION), `opposite_cell`,
  `previous_delta_revision`, `baseline_checksum`, `transfer_refs` (last 4), and a signed per-column `net_exchange`
  (quantity/mass/components) used for restore verification. The full opposite column is never stored.

## 7. Conservation
- Per transaction, `pair_conservation` checks mass, quantity (volume), every component and total elevation. Each
  must hold to 1e-9, and the transfer is rejected otherwise.
- Measured over 399 random commits, the maximum residuals were: mass 3.55e-15, quantity 1.78e-15, components 4.44e-16, elevation 2.22e-16.
- Closed world (491 deltas): residual 1.43e-15, VERIFIED.

## 8. Boundaries
- **Deposits:** `SurfaceMaterialDeposit` stays at its horizontal address and is neither consumed nor moved. A deposit does not
  change column mass. Deposits have no z, so an elevation change does not move them vertically (explicit limitation).
  Coating and columns are not unified.
- **Multi-content:** columns and slices are never RESOURCE_OBJECTs. The spatial index checksum is unchanged, no contents ref is added,
  and column state is queried separately.
- **Terrain fields:** potential, drag, gradients, ambient force, surface response, base optical tensor, traction,
  climate and resources are all unchanged. `physical_effects_active=false`, `geometry_role=METADATA_ONLY`, and elevation has no body effect.
- **Agent/researcher:** the operation is reachable only via the controlled test/internal transaction interface and the
  researcher endpoint `POST /api/research/surface-column-transfer`
  (`ObserverSession.researcher_surface_column_transfer`, INTERVENTION_SETUP, agent_action=false, not wired to any
  agent control). It is absent from the motor vocabulary, cognition candidates, PSC candidates, Observer agent controls and Undercover
  actions. The FORBIDDEN_TOKENS list gained 17 transfer/geometry tokens, and agent observations equal the previous preset.

## 9. Receipt `SURFACE_COLUMN_TRANSFER`
The receipt holds:
- transaction/transfer id and tick;
- wrapped cells; requested/committed thickness;
- revisions before/after; elevations before/after; fixed lower datum; resolved depth before/after;
- slice density; transferred volume/mass/quantity per area; component amounts;
- checksums before/after and baseline checksums;
- conservation (before/after/residual/verified); interval validation; layer merge status;
- provenance refs; selection provenance; atomic_pair;
- flags `researcher_only=true`, `agent_action=false`, `physical_effects_active=false`, `resource_spawned=false`,
  `recipe_match=false`, `semantic_effect=false`.

The full receipt is kept in the bounded transfer history (16). The WMT ledger and the surface-column event stream
keep a compact form (`compact_event`) so snapshot size stays bounded.

## 10. Snapshot / restore
- `surface_columns.column_transfer` (schema `SURFACE_COLUMN_TRANSFER_STATE_V1`) holds the mechanism config, counters, committed transfer ids,
  bounded history, `seed_provenance_checksum` and generator version. Deltas (with provenance) live in the existing sparse map,
  and baselines are never serialized.
- Restore reproduces exact checksums, does not repeat transfers, reuse ids or create deltas, and verifies net exchange per column
  plus the closed-world sum.
- Restore rejects generator or seed mismatch. Old snapshots restore with the mechanism OFF.
- The runtime snapshot writes the transfer config key only when the mechanism is active (so the Tiktaalik snapshot is unchanged).

## 11. Scientific V3 / Analyzer Next
- `scientific_v3/capture.py` emits `kind: surface_column_transfer` refs.
- `scientific_v3/surface_column_transfer_summary.py` produces the section
  **CONSERVATIVE SURFACE COLUMN TRANSFER**: planned/committed/rejected, cells, thickness, elevation and depth changes,
  revisions, sparse delta count, residual maxima, merges, stale conflicts, atomic-pair, persistence/restore, agent
  leakage audit and physical-effect status.
- Statuses are OBSERVED / VERIFIED / REJECTED / NOT_IMPLEMENTED. The section states explicitly that agent excavation, gravity, support and
  explicit carried material are not implemented. There is no progress bar.

## 12. Observer
- The preset is in the common selector, with the single APPLY EXPERIMENT button.
- The OBSERVE → Environment → cell inspector adds
  `data-testid="surface-column-transfer-inspector"`: surface elevation, baseline elevation, elevation delta, resolved
  depth, column revision, last transfer id, role. Labels: researcher-only · not agent-accessible · authoritative world
  geometry · physical body effects inactive · not an excavation action.
- There is no 3D pit or pile drawing.

## 13. Performance (results/acanthostega_column_transfer/measurements.json)
- 400 random transfers: 399 committed, 1 rejected.
- Plan: median 522 µs, p95 812 µs. Commit: median 44 µs, p95 81 µs.
- 2 columns touched per commit; at most 12 layer operations.
- No world scan, no neighbour materialization, no ResourceObject, no world clone.
- Snapshot growth: about 19.9 KB of `surface_columns` JSON after 1 transfer (2.5 KB with none). History saturates at 16 (transfer state about 132 KB).
  After saturation the marginal cost is about 2.67 KB per sparse delta.
- Restore of 491 deltas takes 0.19 s.

## 14. Limitations
- Elevation is authoritative geometry with physical effects inactive: no body z, support, gravity, slope, collision or falling.
- Agent excavation, carried material, piles, detached terrain objects, erosion and hydrology are not implemented.
- Deposits have no z and stay at their horizontal address.
- Only single-layer top slices; no multi-layer excavation.
- Merges require exact (1e-12) physical equality, so procedural layers from different cells almost never merge
  (47 of 399 random commits merged; merges occur when a slice lands on material of identical density/proportions, e.g. a
  previously transferred slice from the same source layer).
- Field names carry `_per_area` (per unit horizontal area), e.g. `transferred_mass_per_area`.
- Pre-existing unrelated failures (not changed by this stage):
  - `test_observer_terrain.py::test_baseline_presets_have_no_terrain_unless_configured`;
  - `test_resource_ecology_authority_beta2.py` E11/E14/E15 (these also fail on a clean `git HEAD` archive);
  - `test_mechanism_control_ui_coverage.py::test_frontend_vision_control_sources_exist` (caused by an earlier uncommitted App.tsx vision-draft refactor).
