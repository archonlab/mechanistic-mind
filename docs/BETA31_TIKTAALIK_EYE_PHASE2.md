# Beta 3.1 Phase 2 — Tiktaalik Eye / Agent Sensor Preview

**BETA31_TIKTAALIK_EYE_PHASE2 = PASS**

Diagnostic Observer phase. Does not add depth, cameras, occlusion, or terrain
geometry vision. Does not feed cognition.

```
BETA3_REFERENCE_MODIFIED = NO
SCIENTIFIC_SEMANTICS_CHANGED = NO
RUNTIME_SEMANTICS_CHANGED = NO
EYE_FEEDS_BACK_INTO_COGNITION = NO
WORLDMAP_RGB_USED_FOR_EYE = NO
GIT_PUSH = NO
```

Forensic classifications (unchanged):

| | |
|---|---|
| GENERAL_VISUAL_DEPTH | MIXED |
| SURFACE_DEPTH | MIXED |
| TERRAIN_GEOMETRY_VISION | OPTICAL_CORRELATE |
| OTHER_BODY_DEPTH | MIXED |
| OCCLUSION | ABSENT |
| MOTION_PARALLAX_INFORMATION | PARTIAL |
| V3_DEPTH_OBSERVABILITY | PARTIAL |

---

## WHAT EYE SHOWS

Agent-accessible optical **accumulators** already in `accessible_observation`:

- `exo_0` / `exo_1` / `exo_2` → LEFT / FORWARD / RIGHT
- LOW: `surface_c0_*`
- RICH: `surface_c0..c2_*`
- OFF: surface channels **ABSENT** (not invented zeros)
- raw float, saturation flag, PE 5-bin (`background_context._quantize`)
- Δ from previous Eye sample (TEMPORAL CHANGE)
- sensor **configuration** metadata (R, FOV, heading source, SURFACE, MAPPING)

Sources: `last_agent_observation` + NFE config. No extra `sample_near_field`
when preview is OFF.

## WHAT EYE DOES NOT SHOW

- a camera / perspective / retinal image
- metres, explicit distance, depth map
- terrain height / slope / potential / gradient / drag
- neighbor dx/dy/identity
- WorldMap RGB
- V3 depth reconstruction (observability remains PARTIAL)

## WHY IT IS NOT A CAMERA

FOV sampling sums **all** in-sector, in-radius, above-threshold cells into three
scalars. There is no image plane, no rays, no occlusion.

## WHY MAGNITUDE IS NOT DISTANCE

`final ∝ dist_f` with `dist_f = 1/(1+0.85·max(0,d−1))`, entangled with
appearance, illumination, angular weight, multi-cell sums, and saturation.

## WHY SURFACE COLOR IS NOT TERRAIN GEOMETRY

`surface_c*` are anonymous optical components. Physical geometry is forbidden
in cognition. Mapping may **correlate** appearance with mechanics (CORRELATED)
without exposing the mechanic.

## WHY OCCLUSION IS ABSENT

Moore FOV collects every qualifying cell. Near and far both contribute.

## WHY WORLD VIEW ≠ AGENT PERCEPTION

WorldMap paints Observer GT fields. Eye paints only accessible floats.

---

## Architecture

```
PHYSICAL WORLD
    → SENSOR SAMPLING (unchanged)
    → AGENT-ACCESSIBLE OBSERVATION (unchanged)
    → COGNITION (unchanged)

PHYSICAL WORLD → HUMAN WORLD RENDER (unchanged)

AGENT-ACCESSIBLE OBSERVATION → TIKTAALIK EYE DIAGNOSTIC RENDER
```

Eye is attached in `ObserverSession._attach_tiktaalik_eye_locked` **after**
scientific timeline compact events, onto the Observer frame only.

Rates: OFF | SNAPSHOT | 2 FPS | 5 FPS | PER TICK. Latest-wins; one payload.
HEADLESS and OFF skip the builder (`update_count` stays 0).

Optional WORLD sector overlay uses neighbor rows **already** on full frames.
Compact RUNNING often has `contributors: SKIPPED` / `NOT_AVAILABLE`.

Optical mapping UI regenerates WORLD `surface_optical` from deterministic seed
namespaces. Tick/history/cognition **not** reset. Accessible `surface_c*` follow
the new WORLD field.

PSC OFF TICKS is Experiment/Predictive, not inside Eye.

---

## Performance (this machine)

`experiments/run_beta31_tiktaalik_eye.py` → `results/beta31_tiktaalik_eye/performance.json`

| | ms/tick | Eye updates | payload |
|---|---|---|---|
| OFF | 24.79 | 0 | 0 |
| SNAPSHOT (stepped PAUSED) | 24.03 | 81 / 80 ticks | ~3 kB |
| 5 FPS | 25.14 | 10 / 80 ticks | ~3 kB |

Payload-only build ≈ 0.4 ms; live rebuild ≈ 0.13 ms. OFF vs 5 FPS **+0.35 ms/tick**
(noise-level vs ~25 ms tick). RSS in the script is cumulative process peak, not
an Eye leak.

SNAPSHOT on a **stepped PAUSED** session rebuilds each capture (status ≠ RUNNING).
During LIVE RUNNING, SNAPSHOT holds the last forced sample.

---

## Tests

- `tests/test_tiktaalik_eye_phase2.py`
- `tests/test_visual_surface_discrimination.py`
- Observer demand-driven / serialization / PSC motor UI
- Frontend `tiktaalikEyeModel.test.ts` (228 npm tests)

---

## Known limitations

- Contributor inspector requires neighbor rows (full/PAUSE selected agent).
- Compact peer agents still omit neighbor lists (existing compact policy).
- PE bins use per-channel quantize, not the full-fragment SHA (raw floats remain).
- V3 schema not expanded (PARTIAL depth observability stands).
- Default R remains **1**; Eye metadata warns. Forensic R=3 is not the factory default.
