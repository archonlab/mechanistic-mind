# Beta 3.1 Phase 4 — Spatial vision results

**BETA31_SPATIAL_VISION_PHASE4 = PASS**

2D world. No explicit depth/distance/terrain geometry in cognition. LEGACY
observation contract preserved. GIT_PUSH = NO.

Design: `docs/BETA31_SPATIAL_VISION_PHASE4_DESIGN.md`  
Harness: `experiments/run_beta31_spatial_vision_phase4.py`  
Tests: `tests/test_spatial_vision_phase4.py`  
Artifacts: `results/beta31_spatial_vision_phase4/`

---

## A. Existing sensor audit

Canonical `sample_near_field` remains 2D Moore-R × 120° FOV × `dist_f` ×
illumination × surface/body composition → 3 `exo_*` bins (+ optional
`surface_c*`). Distance exists only in the sensor pipeline / FPV inspector.
No occlusion before this phase. See design doc §A.

---

## B–C. Selected angular representation

Compared N ∈ {3, 5, 7} at R=3 RICH over several headings.

| N | mean nonzero `spatial_exo` bins |
|---|---|
| 3 | 3.0 |
| 5 | 4.4 |
| 7 | 5.8 |

**Selected N = 5** (`a0…a4`). Smallest N>3 that actually splits the FOV at
R≤3. N=7 fills more bins but multiplies RICH surface keys (7×3 extra C
channels) for modest occupancy gain.

Legacy `exo_0..2` / `surface_c*_{0,1,2}` are **kept**. Spatial keys are
additive: `spatial_exo_a{k}`, `spatial_surface_c{c}_a{k}`.

---

## D. Occlusion

Deterministic **nearest-in-spatial-sector** rule (toroidal distance, then
enumeration). Farther co-bearing samples: `visibility=OCCLUDED`, contribution
0, FPV `occluded_by` = nearer cell (**SENSOR PIPELINE DEBUG**).

LEGACY: both near and far still add (`n_occluded=0`).  
OCCLUSION: `n_occluded≥1` in the aligned near/far fixture; `exo_1` 1.0 vs 0.95.

---

## E–G. Motion / head / disocclusion

Self-MOVE changes the 5-bin spatial pattern (**YES**).  
Head rotation with body pose fixed changes it (**YES**).  
Head turn after aligned occluders changes accessible spatial bins without a
`disocclusion` key (**YES**).

Range still implicit: same bearing, different distance → different
**magnitude** (`dist_f`) in the same angular bin, not a range field.

---

## H. Accessible observation contract

LEGACY: no `spatial_*` keys.  
Non-LEGACY RICH: +20 spatial keys (5 exo + 15 surface).  
Audit: no `depth` / `distance` / `range` / `slope` / `height` / terrain
geometry keys.

---

## I. FPV / Sensor Space

FPV still agent-centered 2D receipts (no perspective). Status includes
`occluded`. Inspector shows occluder cell as pipeline debug. Sensor Space
adds A0…A4 hover-link to accepted samples in that spatial bin.

---

## J. Legacy compatibility

Same seed/pose: LEGACY vs ANGULAR **identical** `exo_*` and `surface_c*`
(`legacy_angular_exo_equal = true`). ANGULAR only adds spatial keys.
OCCLUSION may change exo magnitudes (visibility), by design.

---

## K. SMC dimensionality

| | |
|---|---|
| LEGACY default allowlist | **48** (`spatial_visual` OFF) |
| Spatial family ON | **68** (+20) |
| `SIM_THRESHOLD` | **0.22 unchanged** |
| max spatial-only mean L1 | 20×0.8/68 ≈ **0.235** |
| max optical+spatial | 29×0.8/68 ≈ **0.341** |

Unlike 9 optical channels (max 0.15 < 0.22), a **full** spatial-family
extreme **can** exceed SMC similarity. LEGACY runs are unaffected because the
family is default OFF.

---

## L. MATCH_TOL

Unchanged at 0.12. On 68 channels, one full-travel spatial key is only
~0.012; **≥11** full-travel spatial channels are needed to exceed MATCH_TOL
by spatial keys alone. PSC fixtures therefore still use large non-spatial
consequence basins plus spatial O′ carry (same architecture as the optical
counterexample).

---

## M. Predictive spatial trace

Two 5-bin patterns + same action `MOVE:E` → distinct transition keys, both
`MATCH`. Compression/PE were not modified. Spatial keys enter observation
and therefore `_sig` / `_q`.

---

## N. PSC spatial counterexample

Controlled production `select_observed_composite_motor`: extreme spatial
profiles X vs Y, optically/spatially conditioned SMC+prospection, identical
RNG. Winner MOVE:E vs MOVE:W. **LEVEL 5**. Not “3D seeing”.

---

## O. Perceptual aliasing

World A: forward structure only. World B: same forward + **rear** structure
outside 120° FOV. Current spatial observation **equal**. After head rotation
π: sequences **diverge**. Alias resolved by sensorimotor history, not a
depth variable.

---

## P. CORRELATED / SHUFFLED

12-tick R=3 RICH two-agent, Eye/FPV off. Observation width 30 (LEGACY) vs 50
(spatial). ~9.5 vs ~10.9 ms/tick. No semantic interpretation. SMC records 0
in this short default-cognition window (model not the bottleneck here).

---

## Q. V3 / Analyzer

`compact_accessible_observation` already stores all finite scalars → spatial
keys captured. Analyzer prefixes include `spatial_`. No
`DEPTH_PERCEPTION` / `OBJECT_PERMANENCE` events.

---

## R. Performance

Spatial mode ~15% slower on the 12-tick probe; FPV payload grows by occlusion
fields only when diagnostic=True. HEADLESS uses `diagnostic=False`.

---

## S. Save/restore

`spatial_vision` / `spatial_sectors` in NFE config snapshot. Restored
OCCLUSION run: fragments EXACT_MATCH next sample.

---

## T. Known limitations

- N=5 still coarse; same-bearing near/far stay in one bin (magnitude only).
- Occlusion is sector-nearest, not a continuous 2D shadow.
- TEMPORAL_SPATIAL sensor math = OCCLUSION (no derivative channels).
- FPV 5 FPS not separately timed vs OFF in this bounded probe.
- Full spatial-family ON **changes** SMC geometry (0.235 can beat 0.22).

---

## U. Scientific interpretation

A 2D world can emit **angular + occlusion + self/head-motion** optical
sequences that existing prediction/PSC can use, **without** an explicit depth
channel. That is richer sensorimotor evidence, not 3D perception, not a
cognitive map.

---

## V. Recommended next phase

Do **not** start a Tiktaalik world model / SLAM / depth decoder. Forensic
options: (1) whether naturalistic CORRELATED runs grow distinct spatial
transition classes; (2) FPV 5 FPS cost at two-agent; (3) whether sector
occlusion should use a slightly finer internal bearing bucket than N=5
without adding cognition keys.

---

## Classifications

```
WORLD_PHYSICS_DIMENSION = 2D
EXPLICIT_DEPTH_CHANNEL_ADDED = NO
EXPLICIT_DISTANCE_CHANNEL_ADDED = NO
TERRAIN_GEOMETRY_CHANNEL_ADDED = NO
SPATIAL_ANGULAR_STRUCTURE_ADDED = YES
OCCLUSION_ADDED = YES
TEMPORAL_DERIVATIVE_CHANNELS_ADDED = NO
SELF_MOTION_PRODUCES_RANGE_DEPENDENT_OPTICAL_TRANSFORMATION = YES
HEAD_MOTION_PRODUCES_SPATIAL_OPTICAL_TRANSFORMATION = YES
DISOCCLUSION_PRODUCES_ACCESSIBLE_OPTICAL_CHANGE = YES
SPATIAL_HISTORY_REACHES_PREDICTION = YES
SPATIAL_HISTORY_REACHES_PROSPECTIVE_COMPOSITION = YES
SPATIAL_HISTORY_CAN_CHANGE_PSC_COMPETITION = YES
SPATIAL_HISTORY_CAN_CHANGE_FINAL_ACTION = YES
SPATIAL_PSC_SENSITIVITY_MAX_LEVEL = 5
CURRENT_OBSERVATION_ALIAS_CAN_BE_RESOLVED_BY_SELF_MOTION_HISTORY = YES
```

```
BETA3_REFERENCE_MODIFIED = NO
SCIENTIFIC_SEMANTICS_CHANGED = NO
RUNTIME_SEMANTICS_CHANGED = NO
PSC_SEMANTICS_CHANGED = NO
SMC_THRESHOLD_CHANGED = NO
MATCH_TOL_CHANGED = NO
PE_SEMANTICS_CHANGED = NO
EXPLICIT_DEPTH_ADDED = NO
EXPLICIT_DISTANCE_ADDED = NO
TERRAIN_GEOMETRY_LEAKED = NO
SEMANTIC_SPATIAL_LABELS_ADDED = NO
GIT_PUSH = NO
```
