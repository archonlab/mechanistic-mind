# Beta 3.1 Phase 4 — Spatial vision design (forensic, before implementation)

**Not a 3D world. Not explicit depth.** WORLD remains 2D (`x, y`). Cognition must
not receive `z`, `depth`, `distance`, `range`, `slope`, `height`, object
coordinates, or terrain geometry.

This document traces the **current** canonical sampler, then specifies which
spatial cues can be added as **optical consequences of 2D geometry**.

```
GIT_PUSH = NO
WORLD_PHYSICS_DIMENSION = 2D
EXPLICIT_DEPTH_CHANNEL_PROPOSED = NO
```

---

## A. Current canonical sampler (`sample_near_field`)

File: `mechanistic_mind/physical_system/near_field_exteroception.py`

### Candidate generation

- Body cell: `floor(x) % W`, `floor(y) % H`.
- Neighbors: WRAP_PERIODIC Moore disk radius `R ∈ {1,2,3}` excluding own cell.
- R=1: 8 cells, same order as `MOORE_OFFSETS` (EXACT_MATCH).
- Theoretical max: `(2R+1)² − 1` → 8 / 24 / 48.

### Bearing

- Sensor axis: `head_world_heading` if articulated head enabled on the body,
  else `body.theta`.
- Neighbor bearing: `atan2(dy, dx)` with toroidal Δ from **body center** to
  **neighbor cell center**.
- Relative angle: `wrap_angle(direction − theta)` in `(-π, π]`.

### Angular sectoring (cognition)

- FOV default **120°** (`±60°`).
- Continuous weight: raised cosine `cos(π/2 · |rel|/half)^angular_power`.
- **Three bins** via `fov_sector_index`: `rel ∈ [−half, +half] → u ∈ [0,1) →
  floor(u·3)` → `exo_0` LEFT, `exo_1` FORWARD, `exo_2` RIGHT.
- Outside FOV: angular weight 0, **no contribution**.

### Distance attenuation (sensor pipeline only)

- Euclidean toroidal hypot `dist`.
- `dist_f = 1 / (1 + k·max(0, dist−1))`, `k=0.85`.
- `dist` and `dist_f` exist on Observer neighbor rows / FPV receipts.
- **Not** copied into `accessible_observation`.

### Illumination

- Global scalar cycle (period 240) or frozen value if cycle OFF.
- Multiplies composed optical intensity.

### Detectability

- `pre = gain · composed · illum · dist_f · ang [+ optional hash noise]`
- Clip to `[0, saturation]`; contribute iff `sat ≥ threshold` (0.04) **and**
  inside FOV.

### Surface optics

- Intensity field `surface_response` composed with foreign-body occupancy
  (`1−(1−surf)(1−body_opt)`).
- Optional WORLD GT tensor `surface_optical` (3,H,W). LOW/RICH accumulate
  `opt[c] * final` into `surface_c{c}_{bin}` for bins 0..2.

### Foreign-body optics

- Max `optical_response` over foreign footprint cells. Anonymous occupancy.

### Accumulation / clipping

- Sum into 3 exo bins and optional surface bins; clip each key to `[0,1]`.

### FPV receipts

- `compact_fpv_receipts`: researcher-only 2D sensor-frame `(fwd, left)` of the
  **same** neighbor rows. Not a camera. Status:
  `outside_fov` / `below_threshold` / `accepted` / `own_cell_excluded`.
- Sector labels LEFT/FORWARD/RIGHT. `dist_f` inspector-only.

### Caching

- Tick-scoped `_SNF_CACHE` keyed by world/body ids, pose, head, radius, FOV,
  illumination, threshold, discrimination, surface checksum, foreign bodies.
- `diagnostic=True` attaches FPV without resampling.

### Observation keys (cognition)

From `accessible_observation` via `cognition_exo_fragments` /
`cognition_surface_fragments` only:

- Vision ON: `exo_0, exo_1, exo_2` (zeros allowed).
- Discrimination LOW: `surface_c0_{0,1,2}`.
- RICH: `surface_c0|c1|c2 × {0,1,2}` (9 keys).
- No `distance`, `depth`, `range`, terrain mechanics.

### Scientific V3

- `compact_accessible_observation` copies **all finite scalar** accessible
  keys. New spatial floats would be captured automatically.
- Analyzer currently lists `exo_` / `surface_c` prefixes; `spatial_` should be
  added as a **neutral prefix**, not as DEPTH events.

### Absent today

Occlusion, depth image, range bins, optical flow, terrain height/slope in
cognition, object identity, 3D camera.

---

## B. Cues that can be added **without** explicit depth

| Cue | How | Cognition sees |
|---|---|---|
| Richer **angular** bins | Split the same 120° FOV into N>3 equal angle bins | extra `spatial_*` floats |
| **Occlusion** | 2D nearest-in-bearing competition inside FOV+R | zeros vs nonzeros on those bins |
| **Motion parallax** | Self-MOVE changes bearings; near/far `dist_f` already differs | **sequence** of spatial bins |
| **Head-motion parallax** | Neck changes sensor θ; body pose fixed | sequence of spatial bins |
| **Disocclusion** | After MOVE/neck, a previously losing sample becomes nearest in its bin | changed optical state |

**Not added:** `depth`, `distance`, `range_bin`, `optical_flow`,
`parallax_score`, terrain geometry keys, 3D physics.

Internal geometry (`dist`, bearing) stays SENSOR PIPELINE / FPV DEBUG.

---

## C. Modes

| Mode | Angular | Occlusion | Temporal derivative channels |
|---|---|---|---|
| **LEGACY** | 3 bins only; **no new keys** | none (current) | no |
| **ANGULAR** | + N spatial bins | none | no |
| **OCCLUSION** | + N spatial bins | 2D nearest-in-sector | no |
| **TEMPORAL_SPATIAL** | same as OCCLUSION | same | **no** (history = obs_t, a, obs_{t+1}) |

`TEMPORAL_SPATIAL` exists as the full experimental stack without engineering
flow channels. Sensor math equals OCCLUSION in Phase 4.

LEGACY must EXACT_MATCH current Beta 3.1 fragments, neighbor finals, FPV
(modulo new **optional** diagnostic fields that default unused).

---

## D. Angular resolution choice (to be confirmed empirically)

FOV 120°, R≤3, Moore cells.

At **R=1** a cardinal heading typically admits **3** FOV cells (forward + two
forward diagonals). **7** bins mostly empty. **5** bins still sparse but can
split LEFT vs LEFT-FORWARD vs FORWARD at R≥2.

Candidates: N ∈ {3, 5, 7}.

**Design default: N = 5**, pending occupancy/cost audit:

- Smallest N>3 that can show **differential angular shift** under MOVE/neck
  at R=3.
- Avoid 7×(exo+C0+C1+C2) unless occupancy justifies it.

Spatial bins are **angular**, named `a0 .. a{N-1}` (not near/far).

Legacy 3-bin `exo_*` / `surface_c*` **remain** in all modes with the same
index mapping. Spatial keys are **additive** when mode ≠ LEGACY.

---

## E. Occlusion rule (2D, deterministic)

For samples with `final_contribution > 0` (inside FOV, above threshold):

1. Assign `spatial_sector = fov_sector_index(rel, fov, N)`.
2. Within each spatial sector, sort by toroidal `distance` (then enumeration).
3. **Nearest** keeps `visible_contribution = final`.
4. Farther samples in that sector: `visibility=OCCLUDED`, contribution 0,
   diagnostic `occluded_by = nearer.cell`.

Properties: periodic, head-aware, bounded to R, no object IDs, no 3D rays.

LEGACY: skip this; both near and far still add (current behavior).

---

## F. Accessible contract

**LEGACY:** existing keys only.

**Non-LEGACY:** plus

- `spatial_exo_a{k}` for k=0..N−1
- if LOW: `spatial_surface_c0_a{k}`
- if RICH: `spatial_surface_c{0,1,2}_a{k}`

Forbidden in accessible observation: `depth`, `distance`, `range`, `z`,
`slope`, `height`, `terrain_*`, `occluded_by`, `behind`, `near`, `far`.

Diagnostic occlusion relations: FPV / neighbor rows only, marked
`SENSOR PIPELINE DEBUG`.

---

## G. SMC / MATCH_TOL (do not retune)

Current: 48 equal-weight channels; 9 `surface_c*`; max optical-only L1 0.15;
`SIM_THRESHOLD=0.22`; `MATCH_TOL=0.12`.

Spatial keys must **not** be on the default SMC allowlist (missing→0 would
**shrink** LEGACY mean L1 by increasing the denominator).

Plan: new family `spatial_visual`, **default OFF**. Enabled only when
`spatial_vision ≠ LEGACY`. Thresholds unchanged; report new max L1.

---

## H. FPV / Sensor Space

- Still agent-centered 2D grid (no perspective).
- Overlay: spatial sector index, accepted / occluded / occluder, threshold
  dropout.
- Sensor Space: LEGACY 3 columns; spatial mode extra A0..A{N-1} row.
- Cross-highlight: bin ↔ contributing samples; occluded samples contribute
  nothing.

---

## I. Implementation order

1. This design (done).
2. Sampler + keys + occlusion; LEGACY golden tests.
3. Occupancy benchmark N=3/5/7; freeze N.
4. FPV/Eye UI.
5. SMC family + dimensionality audit.
6. Controlled geometry tests (range, occlusion, disocclusion, MOVE, neck).
7. Predictive / PSC / aliasing fixtures.
8. CORRELATED/SHUFFLED + performance + save/restore.
9. Results document.

---

## J. What would **not** count as success

- Rendering a fake 3D camera.
- Injecting depth into cognition.
- Claiming “Tiktaalik sees in 3D” from angular/occlusion optics.
