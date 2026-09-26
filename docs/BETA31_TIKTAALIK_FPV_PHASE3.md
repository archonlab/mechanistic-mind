# Beta 3.1 Phase 3 — FPV SENSOR FIELD / pre-aggregation optical view

**BETA31_TIKTAALIK_FPV_PHASE3 = PASS**

Diagnostic Observer phase. Does not add a camera, retina, depth image, or
cognition input. Does not reimplement Tiktaalik vision.

```
BETA3_REFERENCE_MODIFIED = NO
SCIENTIFIC_SEMANTICS_CHANGED = NO
RUNTIME_SEMANTICS_CHANGED = NO
FPV_FEEDS_BACK_INTO_COGNITION = NO
FPV_USES_CANONICAL_SENSOR_PATH = YES
FPV_IS_LITERAL_RETINAL_IMAGE = NO
WORLDMAP_RGB_USED_FOR_FPV = NO
EXPLICIT_DEPTH_ADDED = NO
OCCLUSION_ADDED = NO
GIT_PUSH = NO
```

---

## FPV IS

A **spatial diagnostic reconstruction** of the cells the existing visual
sensor actually considers, **before** they are collapsed into
LEFT / FORWARD / RIGHT (`exo_0` / `exo_1` / `exo_2`).

## FPV IS NOT

- a literal retinal image
- a camera / perspective projection
- a depth map
- cognition input
- a terrain semantic map
- object identity / friend / enemy

---

## Canonical sampling path (one scientific definition)

All agent-accessible vision still comes from
`sample_near_field` in `near_field_exteroception.py`.

Per Moore candidate cell the canonical loop already computes:

| Quantity | Role |
|---|---|
| `dx`,`dy` / `relative_angle_*` | internal geometry vs sensor heading |
| Moore membership | candidate set for current R ∈ {1,2,3} |
| `inside_fov` / `angular_factor` | 120° raised-cosine FOV |
| `fov_sector_index(rel, fov)` | bin 0..2 ≡ exo_0..2 |
| `distance` / `distance_factor` (`dist_f`) | attenuation; metres are **not** kept as a cognition field |
| `illumination` | global scalar |
| `detectable` / `threshold` | dropout |
| `surface_response` | anonymous exo intensity field (not height) |
| `body_optical` | foreign-body optical occupancy, not identity |
| `composed_optical` | `1-(1-surf)*(1-body_opt)` |
| `surface_optical` C0/C1/C2 | WORLD optical tensor channels |
| `final_contribution` | post gain/dist/ang/noise/sat/threshold/FOV |
| rejection | outside FOV, below threshold, or own cell excluded |

`diagnostic=False` (normal / HEADLESS / FPV hidden): cache and fragments
unchanged; **no extra allocations** beyond the existing neighbor rows.

`diagnostic=True` (FPV visible + Eye rate not OFF): clone the cached sample
and attach compact `fpv_receipts`. **Fragments are identical.**

There is no second FPV sampler.

Chain:

```
WORLD
  → canonical optical sampling (sample_near_field)
  → FPV diagnostic receipts (optional, Observer)
  → LEFT | FORWARD | RIGHT accumulation
  → SENSOR SPACE (accessible exo_* / surface_c*)
  → cognition
```

No stage invents information the sensor pipeline did not compute.

---

## Coordinate system (human diagnostic only)

- `sensor_frame_xy`: **forward = up**, **left = left**, rotates with
  HEAD heading when articulated head is enabled, else `body.theta`.
- This 2D grid is **not** a cognition coordinate.
- LEFT/FORWARD/RIGHT labels follow **exo_0/1/2 bins** (same as SENSOR SPACE),
  not nautical left/right of the heading vector.

`dist_f` in the hover inspector is **SENSOR PIPELINE GEOMETRY**, not an
explicit agent-accessible distance field. OCCLUSION remains ABSENT: near and
far cells in the same sector both remain visible.

---

## False-color projection

RICH: display RGB ← (C0, C1, C2) **for the researcher only**.
LOW: monochrome from C0.
OFF: **SURFACE CHANNELS ABSENT**; intensity from composed/final exo optics.

These are not human RGB labels in Tiktaalik cognition. Channels remain C0/C1/C2.

CORRELATED WORLD mapping may make optical structure *look* like terrain.
FPV still must not be labelled hill / valley / obstacle.

---

## Demand-driven capture

FPV receipts are built only when the FPV tab is visible **and** Eye preview
is not OFF **and** execution is not HEADLESS.

Rates: OFF / SNAPSHOT / 2 FPS / 5 FPS / PER TICK, latest-wins.

Optional temporal cue on receipts: increased / decreased / newly_detected /
no_longer_detected. No optical flow.

---

## Tests

`tests/test_tiktaalik_fpv_phase3.py` plus existing Phase 1 / Eye / Observer /
V3 regressions.

---

## Performance (representative, SEARCH_COMPACT, same process)

`experiments/run_beta31_tiktaalik_fpv.py` → `results/beta31_tiktaalik_fpv/performance.json`

| | ms/tick | payload | samples | build_ms |
|---|---|---|---|---|
| Eye/FPV OFF | ~24.7 | 0 | 0 | 0 |
| SENSOR SPACE 5 FPS | ~24.0 | ~3.0 kB | 0 | ~0.15 |
| FPV 5 FPS (single agent R=3) | ~24.5 | ~19 kB | 49 | ~1.3 |
| Two-agent FPV payload microbench | — | ~37 kB | 98 | ~4.7 |

FPV vs SENSOR SPACE ≈ **+0.5 ms/tick** in this noise-dominated short bench.
HEADLESS: `fpv_included=false`. Peak RSS in the bench is cumulative across three
sessions in one process, not a per-mode leak.

## Live Observer validation

Performed locally on `http://127.0.0.1:8788/` (fresh uvicorn + rebuilt `web_dist`):

- SENSOR SPACE | FPV tabs present; 5FPS controls wrap without space-between overflow
- AGENT 0 FPV heading-up grid, own cell, outside-FOV dimmed, accepted FORWARD/LEFT/RIGHT
- Selecting a FORWARD sample highlights other FORWARD cells (cross-link)
- API `include_fpv` + RICH/R=3 receipts: 49 samples, `feeds_cognition=false`
- Existing 8897/8801 Observer instances were **not** restarted

## Known limitations (faithfully exposed, not repaired)

Three angular bins, R≤3 (factory R=1), 120° FOV, no rays, no occlusion,
distance/intensity entanglement, summed contributors, clipping, threshold
dropout, PE aliasing, no explicit terrain geometry, neighbour distance, or
identity.
