# Beta 3.1 visual depth / spatial geometry forensic

**BETA31_VISUAL_DEPTH_FORENSIC = PASS**

Read-only audit of what spatial/depth structure actually reaches Tiktaalik cognition.
No vision, cognition, runtime, or Scientific V3 semantics were changed.

```
CODE_CHANGED = NO                    (production / vision / cognition / V3)
SCIENTIFIC_SEMANTICS_CHANGED = NO
RUNTIME_SEMANTICS_CHANGED = NO
BETA3_REFERENCE_MODIFIED = NO
GIT_PUSH = NO
```

Diagnostic-only artefacts (not production):

- `experiments/run_beta31_visual_depth_forensic.py`
- `results/beta31_visual_depth_forensic/diagnostics.json`
- `results/beta31_visual_depth_forensic/summary.json`
- `results/beta31_visual_depth_forensic/classifications.json`

Harness trials bump `world.tick` between placements so `sample_near_field` cache
(keyed on pose + `sum(surface_response)`, not cell identity) cannot reuse a
previous FOV sample. That cache is production behaviour; the bump is measurement
hygiene only. Illumination was frozen at 1.0 so tick does not change optics.

Harness used **vision radius R=3** (maximum LIVE radius). Factory default remains
**R=1**. Cells at Chebyshev 2–3 are invisible unless radius is raised.

---

## 1. Primary question (split)

### A. Other-body depth

**MIXED.** Foreign occupancy is composed into the same anonymous `exo_*` (and
`surface_c*` when enabled) path as terrain optics. No identity, no `dx/dy`, no
distance key. Euclidean distance **is used internally** as
`dist_f = 1/(1+k·max(0,d−1))` and therefore **can** change accessible magnitude.
It does **not** survive as an explicit depth variable.

Controlled bodies at x=17.5 / 18.5 / 19.5 (observer 16.5, θ=0):

| label | exo_0 | exo_1 | exo_2 | 5-bin sensory_signature |
|---|---|---|---|---|
| d1 | 0.070 | **1.0** (sat) | 0.070 | `ce7c5a04d6ec81f2` |
| d2 | 0.187 | **1.0** (sat) | 0.187 | `ce7c5a04d6ec81f2` |
| d3 | 0.0 | 0.952 | 0.0 | `ce7c5a04d6ec81f2` |

Floats differ. Predictive-equivalence signatures **do not**, because `exo_1` stays
in the top 5-bin and the rest of observation is identical. Footprints occupy
several Moore cells, so left/right bins can light even on-axis.

### B. Surface / terrain depth

**No explicit surface depth.** `surface_c{k}_{bin}` uses the **same three angular
FOV bins** as `exo_*`. Distance enters only as a scale on `final`. Terrain
**potential / height / slope / drag / gradient are forbidden** in
`accessible_observation` (`observation.py` `FORBIDDEN_TOKENS`).

RICH vision is **optical appearance in angular bins**, not a heightmap.

### C. General visual depth

**MIXED (magnitude-entangled, not a depth image).** Same optical cell at the same
bearing, unsaturated:

| d | dist_f | exo_1 (OFF/LOW/RICH) |
|---|---|---|
| 1 | 1.000 | 0.550 |
| 2 | 0.541 | 0.297 |
| 3 | 0.370 | 0.204 |

A **single** accessible observation can distinguish those three **if** appearance,
illumination, gain, and saturation are held and the agent uses **raw floats**.
There is still **no** distance / bin-of-range channel. Brightness×distance,
saturation, FOV aggregation, and 5-bin signatures all alias scenes.

### D. Temporally derivable depth

**PARTIAL.** Approaching an on-axis far cell **increases** `exo_1` (distance
factor), without changing FOV bin. That is intensity-range coupling, not
classical motion parallax (no angular slip). Occupying the target cell **zeros**
the contribution (own cell excluded from Moore) — occupancy dropout, not
parallax. Rotation would move energy across `exo_0/1/2`. No optical-flow field.

---

## 2. Visual pipeline (current code)

```
PlanetState (T, M, surface_response, surface_optical, optional FIELD_*)
    ↓  WORLD GT
near_field_exteroception.sample_near_field
    Moore R∈{1,2,3}, exclude own cell
    FOV 120° about head_world_heading if articulated else body.theta
    compose = 1-(1-surf)*(1-body_opt)
    dist_f, angular_sensitivity, illumination, threshold, saturate
    ↓  WORLD GT + OBSERVER rows in sample["neighbors"]
cognition_exo_fragments / cognition_surface_fragments
    ↓  AGENT: fragments only
observation.accessible_observation
    merge exo_* + surface_c* + body.* + local.* + optional vest/osc
    audit_cognition_payload (FORBIDDEN_TOKENS)
    ↓  AGENT
cognition (runtime.step) consumes that dict
    sensory_signature: 5-bin SHA over full fragment  (PE / compression)
    SMC FAMILY_VISUAL = exo_* + surface_c*
    prediction / PSC / prospective composition: same floats, no extra geometry
    ↓
scientific_v3.receipts.compact_accessible_observation
    round(float, 8) of the same keys — no neighbor table
```

| Stage | File / function | Class |
|---|---|---|
| World maps | `planet/state.py` `PlanetState` | WORLD |
| Surface / optical generate | `near_field_exteroception.generate_surface_response`, `generate_surface_optical` | WORLD |
| FOV sample + neighbor diagnostics | `sample_near_field` | WORLD + OBSERVER (`neighbors`, `illumination_phase_gt`, `body_xy`, …) |
| Agent vision | `cognition_exo_fragments`, `cognition_surface_fragments` | AGENT DIRECT |
| Agent observation | `observation.accessible_observation` | AGENT DIRECT |
| Observer pair | `observation.observation_bundle` | OBSERVER + AGENT (separated) |
| Sensory hash | `research/background_context.sensory_signature` | AGENT INDIRECT (lossy) |
| SMC | `sensorimotor_consequence.FAMILY_VISUAL` | AGENT DIRECT (same keys) |
| V3 receipt | `scientific_v3/receipts.build_observation_receipt` | OBSERVER of AGENT floats |
| Analyzer optical family | `scientific_v3/analyzer_next/full_embodied_predictive_model.py` | OBSERVER of same keys |
| WorldMap / UI | `ui/psy_observer_web` | OBSERVER ONLY — not perception |

**Do not infer agent perception from WorldMap.** `sample["neighbors"]` (dx, dy,
distance, relative_angle, distance_factor) is **observer/world**, not cognition.

---

## 3. Spatial inventory

Legend: **W** world only · **O** observer (incl. `sample_near_field` extras) ·
**AD** agent direct in `accessible_observation` · **AI** derivable from
agent history · **ABS** absent.

| Quantity | Class | Notes |
|---|---|---|
| absolute x/y | W / O | `body.x/y` world; not in observation |
| relative dx/dy | O | neighbor rows only |
| Euclidean distance | O internal | used for `dist_f`; not a key |
| Manhattan / Chebyshev | ABS as percept | Moore uses Chebyshev radius as **candidate set** only |
| normalized distance | ABS | |
| distance bin | ABS | bins are **angular**, not range |
| bearing (world) | O | `relative_angle_*` in neighbors |
| angular offset | AD coarse | which of `exo_0/1/2` is lit (40° sectors of 120° FOV) |
| head-relative angle | O / AD coarse | heading selects FOV axis; `prop_neck_*` if neck ON — not visual angle of target |
| body-relative angle | O | if head off, same as FOV axis |
| FOV sector/bin | AD | 3 bins |
| apparent size | ABS | no solid angle / pixel extent |
| intensity vs distance | AD entangled | `final ∝ dist_f` |
| optical vs distance | AD entangled | `surface_c ∝ optical × final` |
| illumination attenuation | AD entangled | global `illum(tick)`, not per-ray |
| depth ordering | ABS | |
| occlusion | ABS | additive FOV sum |
| foreground/background | ABS | |
| local surface orientation | ABS | |
| terrain height / potential / gradient / slope / drag / resistance | W; **forbidden** in cognition | contact: `local.*`, `body.mech` when occupying |
| resource position | W | |
| foreign-body position | W / O | occupancy → optical, anonymous |
| foreign-body distance | O internal | same `dist_f` |
| foreign-body bearing | AD coarse | FOV bins |
| relative velocity (other) | ABS | own `body.vx/vy` only |
| optical flow / motion parallax field | ABS | |
| temporal Δ optical | AI | SMC ΔS on visual family |

---

## 4. `exo_0` / `exo_1` / `exo_2`

**Angular FOV bins**, not distance bins, not distinct optical components.

Implementation (`sample_near_field`):

```
rel = wrap(atan2(dy,dx) - sensor_theta)
ang = cos(π/2 · |rel| / half_fov)^angular_power     # 0 outside ±60°
dist_f = 1 / (1 + 0.85 · max(0, hypot(dx,dy) - 1))
composed = 1 - (1-surf)·(1-body_opt)
final = clip(gain · composed · illum · dist_f · ang)  if FOV and ≥ threshold else 0
u = (rel + half_fov) / (2·half_fov)
bin_i = floor(u · 3) clamped to {0,1,2}
exo[bin_i] += final
exo_i = clip(exo[i], 0, 1)   # sum of all cells in that sector
```

- Multiple visible cells **add** in the same bin, then clip to 1.
- Distance **scales magnitude**, does not choose the bin (unless a cell leaves FOV).
- Bearing **does** choose the bin.
- Foreign-body optics: `body_opt` max occupancy per cell, then **same** compose/bin path. No separate body channel.
- Two scenes at different depths **can** match: same bin sums after saturate, or different `(surf, d)` with equal `surf·dist_f·ang`, or 5-bin PE collapse.
- Same bearing, different distance: distinguished in **unsaturated floats** in this audit; **not** in OFF 5-bin signatures for d=2 vs d=3 (`0.297` and `0.204` share a bin).

---

## 5. `surface_c*` depth content

LOW: `surface_c0_{0,1,2}`. RICH: `surface_c{0,1,2}_{0,1,2}`.

```
surface_c{k}[bin_i] += optical[k, cell] * final
clip to [0,1]
```

Bins are **angle only**. Distance is **the same scale as `exo_*`**, times the
cell’s optical component. Not a range image.

**CASE A vs B** (same optics, same bearing, d=1 vs d=3, no motion):

- RICH floats: **distinguishable** (`exo_1` 0.55 vs 0.204; `surface_c0_1` 0.44 vs 0.163, etc.).
- Mechanism: `dist_f`, not a depth key.
- After translate: intensity follows `dist_f(d)`; occupying the cell drops to 0.
- After rotate: energy can move between bins (bearing), still no range bin.

---

## 6. Terrain depth (before contact)

| Property | Direct visual geometry | Optical correlate | Contact |
|---|---|---|---|
| potential / height / slope / grad / drag | no keys | optional `surface_mode=CORRELATED` mixes potential/drag into **scalar** `surface_response` (WORLD), then into `exo_*` | `local.T/M/vx/vy`, mechanical work on the occupied cell |

RICH does **not** mean “Tiktaalik sees the hill.”

It means: **Tiktaalik sees an optical surface pattern in three FOV sectors that
may historically correlate with what happens when the body occupies that
region**, if the world generator used `CORRELATED` mapping. Independent /
shuffled mappings break that correlation on purpose.

---

## 7. Other-agent depth

| Item | Access |
|---|---|
| presence | anonymous optical occupancy in `exo_*` (if above threshold) |
| bearing | coarse FOV bin |
| distance | not a key; magnitude via `dist_f` |
| relative position | no |
| apparent magnitude | yes, entangled |
| relative motion | only as Δexo over ticks (no `dv`) |
| contact | `body.mech` / local fields when overlapping — not visual depth |
| signal direction | `osc_l_*` / `osc_r_*` if osc ON — **not** vision; no source id |
| signal strength / attenuation | osc deposit locality, not FOV depth |

Distance to the other body is **not DIRECTLY PROVIDED**. It is **potentially
inferable** from unsaturated magnitude / temporal Δ, and is **easy to alias**
(saturation, PE bins, multi-cell footprints). Approaching another Tiktaalik is
**not** general terrain depth perception.

---

## 8. Static depth experiment

Fixed observer (16.5, 16.5), θ=0, identical surface 0.55 / optical (0.8,0.4,0.2),
targets on +x at cells 17, 18, 19.

| Mode | d1 vs d3 raw floats | d1 vs d3 5-bin signature | d2 vs d3 5-bin |
|---|---|---|---|
| OFF | yes | yes (0.55 vs 0.20) | **no** (same hash `b0c0d1b79969b23c`) |
| LOW | yes | yes | (surface_c0 also scales) |
| RICH | yes | yes | yes (more channels) |

Saturation: `sat_d1` clips `exo_1=1.0`; `sat_d3` remains 0.37 — **not** aliased
at gain=1. Inverse brightness (`near 0.40` vs `far surf=1.0` capped) still
slightly different (0.40 vs 0.37). A true `surf ∝ 1/dist_f` pair **would** alias.

**Answer:** distance **can** be distinguished from one static observation **only
as entangled magnitude**, not as depth. PE compression may erase it.

---

## 9. Bearing × distance matrix

FOV 120°, θ=0: ±60°; +y (90°) and −x (180°) **outside**. Diagonal 45° is inside
but `ang` is small; at d≈2.83, `final` fell **below threshold** → all zeros
(RICH `diag_d2` aliases with empty FOV).

**Preserves:** coarse bearing (which bin) **and** magnitude-entangled distance
when above threshold.

**Does not preserve:** metric range, unique scene identity.

**Aliasing examples (measured):**

1. OFF `plus_x_d2` ≡ `plus_x_d3` under `sensory_signature` (distinct floats).
2. RICH `diag_d1` (weak right-bin 0.060) ≡ `diag_d2` / `plus_y_*` / `minus_x_d1`
   under 5-bin hash (`718788caca6d1a05`) — threshold/quantize collapse to “dark”.
3. Bright-near vs dim-far (constructed) can match `exo_*` without matching depth.
4. Many cells summing into one bin → one large `exo_i`, indistinguishable from
   one bright near cell (until saturation).

---

## 10. Temporal / motion parallax

On-axis step +0.5 cells:

- **Near cell (17,16):** t0 `exo_1=0.70`; t1 observer_x=17.0 → **own-cell exclusion → 0**. Δ=0.70. Not parallax.
- **Far cell (19,16):** `exo_1`: 0.259 → 0.308 → 0.378 → 0.491 as distance shrinks. Same bin. Δ first step ≈ 0.048.

**Structure that could become predictive:** intensity vs self-motion (SMC already
learns ΔS on `FAMILY_VISUAL`). **Not present:** angular slip of a stationary
feature, occlusion edges, flow field.

`CURRENT_TIKTAALIK_MOTION_PARALLAX_INFORMATION = PARTIAL`

---

## 11. Occlusion

Moore disc **collects every** in-FOV, in-radius, above-threshold cell. No ray
test.

RICH: near-only `exo_1=0.9`; far-only `exo_1=0.333` (different optical channel
weighting); **both** `exo_1=1.0` (sum then clip) and **both** `surface_c0_1` and
`surface_c1_1` stay lit. Far still contributes when near is present.

**CURRENT_TIKTAALIK_OCCLUSION = ABSENT** (`NO_OCCLUSION`)

FOV is **not** a depth image.

---

## 12–13. Direct vs derivable; cognitive access

**DIRECT DEPTH** would require a single observation that **explicitly**
distinguishes distance (range key, disparity, ordered layers). **Not present.**
Internal `dist` in `sample_near_field` is discarded before cognition except as
it scales `final`.

**DERIVABLE:** temporal intensity vs self-motion; coarse bearing from bin
identity.

**What survives into cognition**

| Layer | Depth-related? |
|---|---|
| `accessible_observation` | magnitude + 3 angular bins (+ surface_c*) |
| observation / PE signature | **lossy** 5-bin; can hide d=2 vs d=3 |
| SMC | Δ of those floats |
| predictive compression / PE | signatures, not metres |
| prediction / PSC | predicted fragments, same keys |
| discarded | neighbor `distance`, `dx`, `dy`, `relative_angle`, `distance_factor` |

---

## 14. Scientific V3 / Analyzer

Receipts store **compact accessible floats** (8 decimal places), so Analyzer
**can** see `exo_*` / `surface_c*` time series if capture is on.

| Reconstruct | V3 |
|---|---|
| target bearing | **partial** (which bin; not degrees) |
| target distance | **no** explicit; **partial** from magnitude if appearance known |
| FOV sector | **yes** (bin index) |
| surface exposure | **partial** (`surface_c*` if LOW/RICH) |
| temporal optical transition | **yes** if tick receipts exist |
| neighbor geometry / occlusion | **no** |

**V3_DEPTH_OBSERVABILITY = PARTIAL**

This is an **observability gap** relative to world geometry, not a missing
agent channel: cognition never had `dx` either. PE 5-bin analysis that uses
signatures **without** raw floats understates magnitude-depth coupling.

**Schema unchanged.**

---

## 15. Required classifications

```
CURRENT_TIKTAALIK_GENERAL_VISUAL_DEPTH            = MIXED
CURRENT_TIKTAALIK_SURFACE_DEPTH                   = MIXED
CURRENT_TIKTAALIK_TERRAIN_GEOMETRY_VISION         = OPTICAL_CORRELATE
CURRENT_TIKTAALIK_OTHER_BODY_DEPTH                = MIXED
CURRENT_TIKTAALIK_OCCLUSION                       = ABSENT
CURRENT_TIKTAALIK_MOTION_PARALLAX_INFORMATION     = PARTIAL
V3_DEPTH_OBSERVABILITY                            = PARTIAL
```

`TERRAIN_GEOMETRY_VISION = OPTICAL_CORRELATE`: physical geometry is never a
visual key; appearance **may** correlate when `surface_mode=CORRELATED`.
Contact physics remains **CONTACT_ONLY**. Independent mapping → optical
correlation **ABSENT** for that run.

---

## 16. Scientific scenarios

**“That `surface_c*` pattern is near” vs “the same surface farther away,”
before interaction.**

- **Statically, as explicit depth: NO.**
- **Statically, as unsaturated magnitude of the same appearance: YES** —
  `final ∝ dist_f`. Identified quantity: **distance attenuation inside
  `final`**, visible as smaller `exo_*` and `surface_c*` in the **same**
  angular bin.
- **If brightness, saturation, bin-sum, or 5-bin PE is uncontrolled: NO**
  (aliasing).
- **Temporally:** approaching increases that bin’s magnitude (`dist_f`);
  walking onto the cell zeros it (occupancy). That is **not** a depth map
  but **is** changing structure SMC can learn.

**“Uphill physical slope” vs “visually different flat surface,” before contact.**

- **NO direct mechanism.** No visual slope/height/gradient channel.
- **Only** if WORLD `surface_response` / `surface_optical` was generated
  **correlated** with potential/drag: an optical pattern that **historically**
  co-occurs with later contact mechanics. That is correlation, not seeing
  the hill.
- After contact: local thermal/material/velocity and mechanical cost.

---

## 17. Recommendation (no implementation in this audit)

Do **not** treat Beta 3.1 RICH as Tiktaalik Eye or as depth.

If a later phase needs geometric depth, it is a **new** sensor contract
(explicit range, disparity, or occluding rays). Do not reinterpret `exo_*`
magnitude as metres.

If analysis needs the magnitude-depth coupling, use **raw accessible floats**,
not 5-bin signatures alone.

Default **R=1** cannot see d=2,3 at all.

---

## Return checklist

**A. Geometry:** Moore R∈{1,2,3}, 120° FOV, 3 angular bins, Euclidean
attenuation, no occlusion, own cell excluded.

**B. exo_0/1/2:** left / forward / right **angular** accumulators of `final`.

**C. surface_c*:** same bins × optical components × `final`.

**D. Static:** unsaturated same-appearance **magnitude** distinguishes d=1/2/3;
PE may not.

**E. Matrix:** bearing → bin; distance → scale; many aliases.

**F. Terrain:** optical correlate / contact; not visual geometry.

**G. Other body:** anonymous optics; no distance key; MIXED.

**H. Temporal:** intensity-range coupling PARTIAL; not parallax field.

**I. Occlusion:** ABSENT.

**J. Cognitive access:** only post-bin clipped floats; neighbor geometry dropped.

**K. V3:** PARTIAL (same floats, no geometry).

**L. Aliasing:** listed in §9.

**M. Classifications:** §15.

**N. Recommendation:** §17; no Phase 2 / Eye in this task.
