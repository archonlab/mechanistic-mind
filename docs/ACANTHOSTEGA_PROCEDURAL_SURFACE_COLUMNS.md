# Acanthostega Phase B — Procedural Surface Columns

Preset: `ACANTHOSTEGA_PHASE_B_PROCEDURAL_COLUMNS` (UI: "Acanthostega Phase B Procedural Columns").
Inherits `ACANTHOSTEGA_PHASE_B_MULTI_CONTENT` + mechanism `procedural_surface_columns` (ON only here).
Module: `mechanistic_mind/physical_system/procedural_surface_columns.py`.
Tests: `tests/test_acanthostega_procedural_surface_columns.py` (51 tests).
Artifacts: `results/acanthostega_procedural_surface_columns/`.

## Architecture question

> Может ли MM детерминированно представить неизменённую землю как дешёвый procedural baseline,
> а изменённую землю — как sparse persistent delta, не материализуя объём мира и пока не меняя физику агента?

**YES.** Baseline = pure function of (world_seed, wrapped cell address, generator version, parameter checksum);
modified cells = sparse persistent deltas committed through a controlled transaction; no W×H×D volume is allocated;
agent observations / body state are bitwise equal to multi-content over 200 ticks.

## Field / authority map (incl. t116 corrections)

| Element | Authority | Physical effect | Agent-accessible |
|---|---|---|---|
| Baseline column (layers, thickness, density, composition) | Authoritative physical world description | none yet | no |
| `surface_elevation` | Authoritative geometry, **no consequence kernel** (`geometry_role=METADATA_ONLY`) | none | no |
| Sparse delta | Authoritative persistent world mutation | none yet | no |
| Column cache (LRU, `cache_limit`) | Derived, non-authoritative, never serialized | — | no |
| Observer column view / cell inspector | Researcher-only view | — | no |
| `surface_optical` tensor | **Not mutated by coating.** Base tensor unchanged; deposit mixed in at sampling. Mutable: deposit optical state + `surface_optical_coating_generation` (unchanged semantics) | unchanged | unchanged |

Flags: `physical_effects_active=false`, `agent_accessible=false`, `geometry_role=METADATA_ONLY`.
Columns are not coupled to locomotion, traction, vision, support or gravity.

## Baseline column schema / invariants

Generator `SURFACE_COLUMN_GENERATOR_V1`; `modelled_depth=4.0`; 3 layers, nominal thickness fractions (0.2, 0.3, 0.5),
nominal densities (1.4, 1.9, 2.5); anonymous components `component_0`, `component_a`, `component_b`.
Invariants: layers contiguous, ordered, half-open `[top, bottom)`, last bottom == modelled_depth; composition sums to quantity;
toroidal address wrap; generator never touches global RNG.

## Seed authority (t117 / t118)

* Seed comes **only** from the canonical experiment/runtime authority (`runtime.seed`), never from `terrain_meta`.
  Bug found by tests and fixed: earlier `world_seed_of` read `terrain_meta` (None in this preset), so every world had seed 0.
* Strictness is scoped to the new mechanism:
  * columns ON: explicit authoritative seed required (`initialize` / `ensure` raise on None);
  * columns OFF: Tiktaalik and previous Acanthostega paths need no seed and do not fail;
  * old snapshot without the mechanism field restores with columns OFF;
  * columns-ON snapshot without `seed_provenance` is rejected;
  * `snapshot world_seed != runtime world_seed` is an explicit error, no fallback;
  * two-agent compares the shared world seed with the **parent runtime** world seed, not per-agent seeds.
* `seed_provenance` (`SURFACE_COLUMN_SEED_PROVENANCE_V1`): `world_seed`, `authority=EXPERIMENT_RUNTIME`,
  `seed_source=EXPERIMENT_RUNTIME_SEED`, `seed_namespace`, `generator_version`, `parameter_checksum`,
  `namespace_key_checksum`, `terrain_meta_used=false`, `terrain_seed_used=false`, `global_rng_used=false`.
  Restore re-derives and verifies it (`restore_verification.seed_provenance_verified`).
* Test 45: missing `terrain_meta` does not change column identity (geology fully decoupled from legacy terrain metadata).

## Sparse delta / transaction / conservation

Setup delta moves one layer boundary of one cell via a controlled transaction (revision chain, stable ids,
stale revision rejected without mutation, invalid layer/quantity rejected). Receipts use the WMT public schema field
`schema_version`, are not agent actions. Mass, quantity and per-component totals conserved; neighbours and baseline untouched.

## Snapshot / restore / compatibility

Schema `PROCEDURAL_SURFACE_COLUMNS_SNAPSHOT_V1`: config, seed provenance, deltas, bounded history (16), manifest; no cache,
no dense volume. Restore verifies generator version, parameter checksum, deltas checksum, seed provenance; tampered or
unknown-version snapshots are rejected. Tiktaalik and multi-content snapshot keys unchanged.

## Measurements (32×32, 3 layers)

* Cold generation ≈117 µs/column (≈0.12 s for all 1024).
* Cache bounded at 256 after full sweeps.
* `surface_columns` JSON: 0 deltas 1696 B; 1 → 8545; 4 → 28927; 16 → 70440; 64 → 156428; 256 → 499504 (≈1.8 KB/delta + bounded history).
* Determinism: reversed query order 1024/1024 equal; seed 17 vs 18 differ 1024/1024; manifest checksum seed 17 `4ffb07a6abd58029`.
* Equivalence vs multi-content: 0 diffs in observations/body over 200 ticks; optical tensor and spatial index checksum equal.
* Restore: VERIFIED, 0 diffs over 50 ticks after restore.
* Honest note: at 32×32×3 a JSON delta is not smaller than a dense per-cell record; the benefit is O(modified cells) scaling
  and never materializing W×H×D.

## Test fixture corrections (not weakened checks)

1. Cache test: the original query pattern `(i%32, (i//7)%32)` over 296 queries hit only ~224 unique cells (wrap collisions),
   below `cache_limit=256`, so no eviction occurred. Limit now derived from real size (`cells//4`), every cell swept,
   exact assertion `evictions == cells - limit`.
2. Receipt test: public field is `schema_version` (same as WORLD_MATERIAL_TRANSACTION_V1). `transaction_schema` was a wrong
   name in the test; the test now also asserts `transaction_schema` is absent.

## Limitations

* No agent physics, sensing, excavation, piles, gravity, support contact, recipes, lifecycle.
* `surface_elevation` is metadata only.
* Pre-existing unrelated failure: `tests/test_observer_terrain.py::test_baseline_presets_have_no_terrain_unless_configured`
  (reproduces with columns force-disabled; `BASELINE_CLIMATE_DEFAULT` ecology enables terrain).
