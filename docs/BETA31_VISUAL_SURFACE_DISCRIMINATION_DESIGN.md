# Beta 3.1 — Visual Surface Discrimination (Phase 1)

**Status:** Phase 1 design + implementation  
**Control organism:** MM 1.0 Tiktaalik Public Beta 3 (`v1.0.0-tiktaalik-public-beta-3`)  
**GIT_PUSH:** NO  

This document traces the frozen Beta 3 vision pipeline, then specifies how
**visual surface discrimination** is added without collapsing world / human
render / agent perception, and without semantic terrain labels.

Beta 3 already has physical vision. Phase 1 does **not** “add vision”.
It adds **neutral optical surface channels** sampled through the existing FOV.

---

## 0. Architecture trace (Beta 3, forensic)

```
physical world (PlanetState grids + terrain + surface_response)
        ↓
terrain/site representation (terrain_potential, terrain_drag, grads, resources)
        ↓
existing physical vision / FOV sampling (sample_near_field)
        ↓
agent observation (accessible_observation → exo_0/1/2 + other fragments)
        ↓
observation representation (dict[str, float]; sensory signatures)
        ↓
predictive compression / equivalence / relevance / SMC
        ↓
prospection / PSC
        ↓
Scientific V3 ObservationReceipt (accessible + signature hash)
        ↓
Analyzer Next / TickStory (VISION_EXPOSURE, exo_* components)
```

### 0.1 Physical world

| Item | Location |
|------|----------|
| Grids T, M, vx, vy, optional FIELD/OSC | `mechanistic_mind/planet/state.py` `PlanetState` |
| Terrain mechanics | `planet/terrain.py` → `terrain_potential`, `terrain_drag`, `terrain_grad_*` |
| Resources / suitability | `resource_geo_suit_*`, `R_A`/`R_B` (Observer GT; forbidden in cognition) |
| Scalar optical **world** field | `PlanetState.surface_response` (H×W, [0,1]) |
| Install | `near_field_exteroception.install_surface_on_planet` from `PhysicalSystemRuntime.reset` |

`generate_surface_response` is already namespaced
(`deterministic_namespace_seed(experiment_seed, "surface_observable")`),
static after install, and supports **INDEPENDENT / CORRELATED / SHUFFLED**.
It is **WORLD GT**, not a cognition key (`FORBIDDEN_TOKENS` includes
`surface_response`, `surface_meta`, terrain mechanics names).

### 0.2 Terrain / site vs appearance

Terrain class labels (hill, obstacle, …) are **not** agent-accessible.
Human Observer map colors (`web/psy-observer/src/components/WorldMap.tsx`)
are a **separate palette** over T / potential / drag / resources.
Those RGB values are **not** in `accessible_observation`.

### 0.3 Physical vision / FOV sampling

**File:** `mechanistic_mind/physical_system/near_field_exteroception.py`

| Function | Role |
|----------|------|
| `moore_neighbor_cells` | WRAP_PERIODIC Moore candidates, radius R∈{1,2,3}; own cell excluded |
| `angular_sensitivity` | Raised-cosine FOV; **exactly 0** outside half-FOV |
| `illumination_intensity` | Global scalar cycle (or frozen); not DAY/NIGHT |
| `body_optical_occupancy` | Anonymous max foreign-body `optical_response` per cell |
| `compose_surface_and_body_optical` | `1-(1-surf)*(1-body_opt)` |
| `sample_near_field` | Full evaluation + Observer neighbor rows |
| `cognition_exo_fragments` | Cognition-only `exo_0..exo_2` |

**Sensor axis:** `head_world_heading` if articulated head enabled, else `body.theta`
(`ACTIVE_SENSOR_ORIENTATION`).

**Per candidate cell:**

1. Toroidal Δx, Δy from body center to cell center  
2. Distance attenuation + angular FOV factor  
3. `composed = surface_response[cell] ⟂ body_optical`  
4. `raw = composed * illumination`  
5. Gain, optional hash noise, saturation, threshold  
6. If inside FOV **and** above threshold: add `final` into one of **three angular bins**

**Cognition output today:** three anonymous intensities `exo_0`, `exo_1`, `exo_2`
(left / forward / right **within FOV**). Not per-cell images. Not RGB.

**Observer-only in the same sample:** neighbor rows (surface_response,
body_optical, composed, angles, detectability), illumination phase GT,
surface_meta, FOV geometry.

### 0.4 Agent observation

**File:** `mechanistic_mind/physical_system/observation.py`  
`accessible_observation(...)` builds `dict[str, float]`:

- local body / climate / flow at occupied cells  
- optional `local.FIELD_*`  
- internal medium means  
- `exo_*` iff `near_field_cfg.vision_contributes`  
- vestibular / neck / oscillatory fragments when those sensors are ON  

Leak guard: `FORBIDDEN_TOKENS` (terrain mechanics, surface_meta, agent ids, …).

Callers: `PhysicalSystemRuntime.agent_observation`,
`two_agent.py` per-slot observations with `foreign_bodies`.

### 0.5 Observation signatures / prediction

Full observation dict enters cognition. Predictive compression / equivalence
hash **quantized** sensory signatures (`research/background_context.py`
`sensory_signature`). SMC allowlist
(`sensorimotor_consequence.py` `FAMILY_VISUAL = exo_0/1/2`) learns ΔS on
those keys only — **not** auto-ingest of entire ObservationReceipt.

PSC / prospective composition consume the same observation fragment and
SMC/O′ stores. No special visual policy.

### 0.6 Scientific V3

`scientific_v3/receipts.py` `compact_accessible_observation` copies finite
floats; `build_observation_receipt` hashes `accessible` → `signature`.  
`capture.py` marks vision PARTIAL if any `exo_` / `vision` / `opt_` keys exist.

Decision / Motor / Consequence receipts are **not** vision-specific.

### 0.7 Analyzer Next

| Piece | Behavior |
|-------|----------|
| `tick_stories._parse_observation_components` | prefixes `exo_`, FIELD, body, vest, osc, … |
| `joins.py` | `VISION_EXPOSURE` from Observer optical + accessible `exo_*` |
| `sensorimotor.py` | visual_exposure, exo_delta, optical totals (GT tagged) |
| `contrasts.py` | visual_exposure vs none |

No “recognized color / avoided hill” language.

### 0.8 Save / restore

- Config: `near_field_exteroception` in physical-system snapshot  
- World: `surface_response` + `surface_meta` in `serialize_planet_state`  
- No per-tick RGB frame  

### 0.9 Human-only rendering

WorldMap heat colors, FOV wedge overlays, Sensor Inspector neighbor tables,
vision forensics. **Not** cognition.

### 0.10 What Beta 3 does **not** give the agent

- Per-cell appearance independent of the single scalar `surface_response`  
- Multiple independent optical channels (chromatic discrimination)  
- Terrain class or difficulty labels  
- Human RGB palette  

Current `exo_*` already encode **angularly binned optical intensity** of that
scalar field (plus foreign-body optics and illumination). Phase 1 adds
**additional independent optical channels** sampled on the **same** visible
cells, without replacing or semantically tagging `exo_*`.

---

## 1. Three layers (must not collapse)

| Layer | Content | Enters cognition? |
|-------|---------|-------------------|
| **PHYSICAL WORLD** | potential, drag, gradient, resources, `surface_response`, new `surface_optical` tensors | No (except via sensors) |
| **HUMAN RENDER** | Observer palettes / FOV overlays | No |
| **TIKTAALIK PERCEPTUAL** | `exo_*` + (Phase 1) `surface_c{k}_{bin}` | Yes, FOV-gated |

Human RGB ≠ agent RGB. Observer palette must not become cognition input.

---

## 2. Mechanism / config

Existing abstraction: `NearFieldExteroceptionConfig` (package
`physical_near_field_vision`). Phase 1 adds a **mode on that package**, not a
new physics engine:

```
visual_surface_discrimination: OFF | LOW | RICH   # default OFF
optical_mapping: INDEPENDENT | CORRELATED | SHUFFLED | UNIFORM
optical_correlation: float in [0,1]   # used when CORRELATED
```

**OFF** is the Beta 3 control: no `surface_c*` keys, no extra world tensor,
`exo_*` path bitwise-equivalent given the same seed/config.

UI: Experiment → Vision — Surface discrimination OFF / LOW / RICH.

---

## 3. Surface optical field (WORLD GT)

New optional `PlanetState.surface_optical`: shape `(3, H, W)`, float64 in [0,1],
static after install.

**Generator** `surface_optical_v1`:

- Channel `k` seed: `deterministic_namespace_seed(experiment_seed, f"surface_optical_c{k}")`  
- Smooth independent field (same 4-neighbor blur as `surface_response`)  
- **INDEPENDENT:** that field only  
- **CORRELATED:** mix with (c0←potential, c1←drag, c2←|grad|); mix weight
  `optical_correlation`; **not** a class label — imperfect analog mix  
- **SHUFFLED:** correlated mix then spatial permutation (same histogram, broken
  geography)  
- **UNIFORM:** constant 0.5 (distinctions collapse)  

Installed **only** when discrimination is LOW or RICH (OFF snapshots stay
Beta-3-sized). LIVE OFF→RICH installs once; RICH→OFF stops sampling but may
leave the tensor (toggle-back identity). Regenerated from seed+config if
missing after restore.

No per-frame stochastic color. Periodic geometry is the planet torus.

Cognition never receives `terrain_type`, `difficulty`, or channel names red /
green / blue.

---

## 4. Correlation control (ablation architecture)

| Mapping | Physics | Optics |
|---------|---------|--------|
| INDEPENDENT | unchanged | independent appearance |
| CORRELATED | unchanged | appearance statistically related to mechanics |
| SHUFFLED | unchanged | appearance present, geography broken |
| UNIFORM | unchanged | appearance collapsed |

Phase 1 UI exposes discrimination **depth** (OFF/LOW/RICH), not all mapping
modes (defaults INDEPENDENT). Mapping remains a config field so later
experiments can hold physics fixed and change optics, or the reverse.

---

## 5. FOV-only sampling

`surface_c*` accumulate **only** on the same candidate loop as `exo_*`:

- Moore radius, WRAP_PERIODIC  
- head/body sensor axis  
- FOV angular_sensitivity == 0 → no contribution  
- same distance / illumination / threshold detectability as `exo` `final > 0`  
  (dark / below-threshold cells contribute no appearance, same as intensity)  

No global map. Human overlay visibility is irrelevant.

---

## 6. Compact observation (not an image)

Do **not** render RGB then run CV.

Reuse the existing **three angular bins** so spatial structure is not
collapsed to one scalar:

| Mode | Keys |
|------|------|
| OFF | (none) — Beta 3 observation key set |
| LOW | `surface_c0_0`, `surface_c0_1`, `surface_c0_2` |
| RICH | LOW + `surface_c1_*` + `surface_c2_*` |

Each key is the saturated sum of that optical channel on detectable cells in
that FOV bin, clipped to [0,1] (same saturation as `exo_*`).

`exo_*` remain the intensity pathway (surface_response ⟂ body optics ×
illumination). `surface_c*` are **additional** appearance measurements of
`surface_optical[k]` on those same cells, **not** mixed into `exo_*`.

Diagnostic (Observer / future Eye, not cognition): per-neighbor optical
triplet on `sample_near_field["neighbors"]`.

---

## 7. Cognitive integration

`accessible_observation` merges `cognition_surface_fragments` after `exo_*`.

Allowlists extended (missing keys skipped when OFF):

- `FAMILY_VISUAL` / SMC `optical` family  
- `psc_motor_resolution_shadow.FAMILY_KEYS["optical"]`  
- `full_embodied_predictive_model` optical tuple  

No rule `if surface_c0 > X: avoid`. No reward, curiosity, or terrain heuristic.
Causal route remains observation → history → motor consequence → prediction → PSC.

---

## 8. Scientific V3

ObservationReceipt `accessible` already serializes new floats; signature hash
includes them when present.

`capture.py` vision coverage: also `surface_c`.

No extra world frame per agent. D/M/C receipts unchanged.

Compact Analyzer-facing fact (derived from accessible keys, not GT labels):
mode inferred from which `surface_c*` keys exist.

---

## 9. Analyzer Next

- `tick_stories` interesting prefix `surface_c`  
- Context kinds (neutral): `SURFACE_EXPOSURE`, `OPTICAL_CONTRAST_CHANGE`  
- Operational: `SURFACE_TRANSITION`, `ACTION_UNDER_SURFACE_EXPOSURE`  

Forbidden conclusions: recognized danger, understood red, intended hill
avoidance.

---

## 10. Performance

Expected cheap sampling (same Moore loop). Risk is signature/store growth.

Instrument OFF / LOW / RICH at 1k / 5k / 10k ticks where practical:
ms/tick, ticks/s, cognition, vision sample, prediction, compression, PE, PSC,
RSS, store sizes, scientific bytes/tick, snapshot size.

---

## 11. OFF compatibility gate

Same seed, world, agents, mechanisms, PSC schedule:

Beta 3.1 + `VISUAL_SURFACE_DISCRIMINATION=OFF` vs Beta 3 / OFF self-compare:

observations (no `surface_c*` keys), decisions, motors, consequences, poses,
signals, receipt signatures for non-surface channels.

Any OFF divergence is a blocker.

---

## 12. Save / restore

- Config mode + mapping in `near_field_exteroception`  
- `surface_optical` + `surface_optical_meta` on planet when present  
- Restore: observations match uninterrupted run; next-tick equivalence  
- No RGB frame blob  

---

## 13. First experiment

Identical physics / seeds / positions / PSC schedule (PSC OFF until ~1000,
`OBSERVED_COMPOSITE`, no reset):

**OFF vs RICH** (mapping CORRELATED in the RICH arm only as an explicit
experiment flag — documented; default runtime mapping remains INDEPENDENT).

Descriptive: predictive differentiation, motor distributions, prospective
selection, trajectory/terrain relationships, store growth, performance.

**Not:** “learned colors”.

---

## 14. PSC_OFF_TICKS (secondary)

Optional session/config integer:

- `None` / omitted → MANUAL (Beta 3)  
- `N` → at tick N, enable `prospective_scenario_competition` without reset  

Evidence: `PSC_ACTIVATION` tick, mode, `history_preserved=true`.

Not entangled with optical sampling.

---

## 15. Phase 1 UI

Vision panel: Surface discrimination OFF / LOW / RICH + current state.

No Tiktaalik Eye live view.

---

## 16. Phase 2 hook (not implemented)

`sample_near_field` diagnostic payload is sufficient to later render
WORLD / AGENT 0 EYE / AGENT 1 EYE / SPLIT at bounded FPS from **agent-accessible
channels**, never feeding back into cognition.

---

## 17. Tests

See `tests/test_visual_surface_discrimination.py` plus Beta 3 regressions.

---

## 18. Explicit non-goals

No Beta 3 tag rewrite, Acanthostega, birth/sex/aging, PSC rewrite, rewards,
semantic terrain labels, GitHub push.
