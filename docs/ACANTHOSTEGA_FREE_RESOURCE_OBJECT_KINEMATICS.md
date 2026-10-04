# ACANTHOSTEGA FREE RESOURCE OBJECT KINEMATICS

Preset `ACANTHOSTEGA_PHASE_B_FREE_OBJECT_KINEMATICS` · mechanism `free_resource_object_kinematics` ·
module `mechanistic_mind/physical_system/free_resource_object_kinematics.py` · profile
`FREE_OBJECT_KINEMATICS_PROFILE_V1`.

This layer sits between the existing bilateral manipulation and the later collision / gravity /
contact-consequence / impact-acoustics stages. It covers translational kinematics of a released
ResourceObject only.

```text
held object moves with physical effector → RELEASE → object inherits measured effector world velocity
→ free object continues deterministic motion → passive damping → exact rest
```

## 1. Implementation map (established before implementation)

| # | Question | Answer in the actual runtime |
|---|---|---|
| 1 | Where does a held object get its body-relative pose? | `physical_manipulator.update_held_kinematics` snaps a HELD object to `effector_world_xy(body)` = body xy + 0.55·heading ± lateral (0.42, or aperture/2 during BRING_TOGETHER). The pose is recomputed, never stored as an offset. |
| 2 | When in the tick does RELEASE run? | `resolve_shared_world_manipulators(runtimes, world, tick)`. Order: sanitize → held snap → per-holder GRASP/RELEASE (sorted body_id, RELEASE before GRASP) + pair actuation → held snap → contact/COMBINE → deposition → `reconcile_contents(reason="manipulator")`. |
| 3 | Is the effector's physical pose from the previous tick available? | **No, not before this stage.** The new world state stores `effector_poses["body|LEFT/RIGHT"] = [x, y, tick]` at the end of every world step. |
| 4 | Can effector velocity be an observed pose difference? | Yes. The effector has **no independent kinematics**: its pose is a deterministic function of body x, y, θ and aperture, so the world-pose difference over one scientific tick is a physical measurement. |
| 5 | Toroidal displacement? | The world is always `WRAP_PERIODIC`. The delta uses the shortest toroidal path `((d + L/2) mod L) − L/2` per axis. |
| 6 | When is the spatial index updated? | `reconcile_contents` at the end of the world step (objects, `include_bodies=False`) and in `finish_tick` (bodies). Near-field optical occupancy reads index cells. |
| 7 | Where is it safe to integrate free objects once per scientific tick? | Inside the single world step, after the tick-start held snap and **before** this tick's GRASP/RELEASE. |
| 8 | How does TwoAgentRuntime avoid double integration of the shared world? | Every slot has `_defer_manipulator_world=True`, and `TwoAgentRuntime._step_once` calls the world step **once** with `tick = slots[0].tick − 1`. A `last_integrated_tick` guard also makes integration idempotent per tick. |
| 9 | Which object states were already serialized? | `ResourceObject.to_dict/from_dict` already carried `vx`, `vy` (always 0, never integrated), `physical_state` (FREE_STATIC/HELD), holder and manipulator. Missing values become 0 / FREE_STATIC. `mass` exists but has no role in dynamics. |
| 10 | Which operations assume a free object is stationary? | GRASP candidates must be FREE_STATIC. Contact/COMBINE uses held objects only. Deposition uses held objects. Vision reads position/index only. None of these was changed. |

### Call chain / tick seam (fixed)

```text
PhysicalSystemRuntime (1 agent):   begin_tick (observation → cognition → motor)
                                    finish_tick: body integration (Gentle Locomotion) → planet → oscillatory
                                                 → resolve_shared_world_manipulators([self], tick=T)
                                                 → reconcile bodies → tick += 1 → local signal transport
TwoAgentRuntime (shared planet):    begin_tick(slot i in process order) → step_planet ONCE
                                    → finish_tick(slot i, manipulators deferred) → pair contact (+ Audio B)
                                    → resolve_shared_world_manipulators(slots, tick=T) ONCE → signal transport

resolve_shared_world_manipulators(tick T):
    sanitize → update_held_kinematics
    [A] integrate_free_objects(T)         FREE_MOVING only; guard last_integrated_tick; damp → rest check → drift+wrap
    GRASP/RELEASE loop (unchanged)        + pair actuation (unchanged)
    [B] apply_release_transfer(T)         objects released at T: v = clamp(transfer · measured effector velocity)
    update_held_kinematics → contact/COMBINE → deposition (unchanged)
    [C] record_effector_poses(T); finish_step(T)   pose history for T+1, world.last_free_object_step
    reconcile_contents(reason="manipulator")        index now sees the new object cell
```

An object released at T is **not** integrated at T. Its receipt says `integrated_in_release_tick=false`,
`first_integration_tick=T+1`. A HELD object never enters [A]. Cognition order, the Tiktaalik tick
order and the unchanged manipulation code are not reordered; the hooks are no-ops unless
`world.free_object_kinematics_state` exists, and it exists only under the new preset.

## 2. Preset parent choice

Parent = `ACANTHOSTEGA_PHASE_B_COLUMN_TRANSFER` (the last material/manipulation preset). The chain
after Column Transfer forks into Audio A (`LOCAL_SIGNAL`) → Audio B (`CONTACT_ACOUSTICS`). Free-object
kinematics depends only on objects, bilateral grasp/release, the multi-content index and the
material chain. It does **not** depend on signal transport or body-body contact acoustics. So the new
preset inherits the whole material/manipulation chain and none of Audio A/B, and the new mechanism is
absent from Audio A and Audio B. The future `OBJECT IMPACT ACOUSTIC EMISSION` node is where the two
branches must merge; that is a separate stage.

## 3. Authoritative vs derived state

Authoritative (world, serialized): `x, y, vx, vy, physical_state ∈ {HELD, FREE_MOVING, FREE_STATIC}`,
holder/manipulator, mass, composition, material properties. Kinematics world state:
`effector_poses`, `last_integrated_tick`, id sequences, open episodes, counters, bounded histories.
`FREE_STATIC` (the existing enum value) is the free-rest state. The one new physical state is
`FREE_MOVING`. No semantic states were added.

Derived: speed, `motion_status` (MOVING / FREE_REST / HELD), UI trail/arrow, the spatial index. The
renderer never writes position or velocity.

## 4. Formulas

Effector velocity (scientific ticks, dt = 1):

```text
delta = shortest_toroidal(current_effector_world_pose − previous_effector_world_pose)
v_eff = delta / dt       only if previous pose was recorded at tick T−1 and |delta| ≤ 1.0 cell
```

Outcomes: `MEASURED_TOROIDAL_POSE_DIFFERENCE`; `NO_PREVIOUS_TICK_POSE` (first tick after
apply/restore/grasp-less history gives v = 0); `EFFECTOR_POSE_DISCONTINUITY` (teleport/reset/researcher
placement gives v = 0, counted); `NON_FINITE_EFFECTOR_POSE` (v = 0, counted). The body velocity is never
used (`body_velocity_used=false`). Rotation and aperture changes move the effector and are measured.

RELEASE transfer (after the unchanged RELEASE succeeded):

```text
position = current effector world pose (unchanged RELEASE already leaves it there)
v_raw    = release_transfer · v_eff                   release_transfer = 1.0 (profile coefficient)
v        = v_raw · min(1, max_free_object_speed / |v_raw|)   direction preserved; max = 0.75 cells/tick
state    = FREE_STATIC with v = (0,0)  if |v| < rest_threshold (0.01)   else FREE_MOVING
```

Free integration, one step per scientific tick (exponential damping, then drift):

```text
v' = clamp(v) · exp(−k·dt)              k = damping_rate = 0.25 /tick (common, material-independent)
if |v'| < rest_threshold:  v' = (0,0), state = FREE_STATIC, position unchanged
else:                       x' = wrap(x + v'x·dt), y' = wrap(y + v'y·dt)
```

Closed form: `|v_n| = |v_0|·e^(−kn)`, `ticks_to_rest = ceil(ln(|v_0|/0.01)/0.25)`,
path ≤ `|v_0|·e^(−k)/(1−e^(−k))` (≈ 3.52·|v_0|, truncated at rest). Example: v0 = 0.3 gives 14 ticks and path 1.0153.
Non-finite velocities become (0,0) (counted, receipt flag).

Material properties are not used (`material_property_input = NOT_USED`). `surface_affinity` already
means traction/adhesion with the surface, and reusing it for free-object drag would change or
overload its semantics. Material-dependent resistance is deferred.

## 5. Spatial index

After [A] and [B] the world step calls `reconcile_contents`: old refs are removed, the new cell ref is
added, each object appears exactly once, several objects may share a cell, and WRAP creates no
duplicates. Movement lives in the object pose, never only in the index.

## 6. Receipts (researcher-only, `agent_accessible=false`)

* `RESOURCE_OBJECT_RELEASE_KINEMATICS`. Fields: tick, release_id, object ID, releasing body, effector
  side, previous/current effector pose (+ previous pose tick), toroidal delta, measurement outcome,
  measured effector velocity, `body_velocity_used`, release transfer, inherited velocity before clamp,
  velocity/speed after clamp, `speed_clamped`, initial free state, position, source action receipt
  (hand receipt event/tick), `integrated_in_release_tick=false`, `first_integration_tick`.
* `RESOURCE_OBJECT_FREE_MOTION`. Fields: tick, motion_id, object ID, release ref, start/end position,
  start / after-clamp / end velocity, damping law/rate/factor, rest threshold, displacement,
  step length, WRAP, clamp, non-finite normalisation, rest transition, material input (NOT_USED),
  `invariants_conserved`, `contact_detected=false`, `impulse_transferred=false`. The rest-transition
  receipt carries an `episode` (release tick, rest tick, ticks_to_rest, path length, wrap count,
  initial speed). Objects already in FREE_STATIC produce no receipts.
* Counters include releases_moving/at_rest, measurement outcomes, clamps, motion steps, rest
  transitions, wraps, conservation violations, reintegration suppressed, and
  grasp_attempts_with_free_moving_in_reach.
* Scientific capture: event refs of kind `free_resource_object_kinematics`.

## 7. Agent-visible vs researcher-only

There is no new sensor. The agent can notice a moving object only through existing physical channels:
optical sampling/occlusion of the new pose (index-driven near-field occupancy) and physical object
vision. `observation.FORBIDDEN_TOKENS` now also rejects the mechanism id, `FREE_MOVING`, both receipt
names, `object-release-`, `object-motion-`, `release_transfer`, `inherited_velocity` and
`measured_effector_velocity`.

## 8. Snapshot / restore

When the preset is active the snapshot adds `config.free_resource_object_kinematics` (profile) and
`world.free_object_kinematics_state` (effector pose history, guard tick, sequences, episodes, counters,
histories). A mid-motion restore continues the trajectory bitwise. Old snapshots are handled as follows:
* missing `vx`/`vy`/state becomes `(0, 0, FREE_STATIC)`;
* a snapshot without the kinematics state has any FREE_MOVING normalised to rest;
* a new-preset snapshot without pose history gives the first RELEASE `NO_PREVIOUS_TICK_POSE`, so there is no false throw.

Apply/reset creates canonical objects stationary.

## 9. Observer / Analyzer

Observer (researcher overlay in Observe → Environment → overlays): profile; counters; per-object
motion status, position and speed; a velocity-vector toggle (map arrow = 3 ticks × v, display scale;
moving glyph in blue); and the label **"collision physics: not implemented · no gravity · objects pass
through bodies and each other"**. There is no separate Apply, no semantic icon and no predicted path.

Analyzer section **FREE RESOURCE OBJECT KINEMATICS**: release count (moving / at rest), moving
objects, rest transitions, inherited speed distribution, clamp count, displacement/path length, time to
rest, WRAP count, conservation violations, snapshot continuation status and provenance quality.
There is no progress bar.

## 10. Limitations

* The effector has no independent kinematics. Its velocity is the measured difference of a pose derived
  from body pose, heading and aperture.
* Grasping a moving object is **NOT_ESTABLISHED**: the existing GRASP contract accepts only FREE_STATIC.
  A failed attempt keeps the existing `GRASP_FAILED_OUT_OF_REACH` label and is counted in
  `grasp_attempts_with_free_moving_in_reach`.
* `mass` does not participate in dynamics. Damping is common (material-independent).
* Under Gentle Locomotion real effector speeds are small. The measured browser run inherited 0.0898
  cells/tick, travelled 0.273 cells and rested in 9 ticks. The safety clamp at 0.75 sits above the
  physical effector limit (about 0.57 cells/tick) and is a numerical guard only.
* No collision, gravity, z, slope, deposits, sound, damage or impulse (explicitly not implemented).

## 11. Next dependency-safe seam (not implemented)

```text
FREE RESOURCE OBJECT KINEMATICS
    ↓
OBJECT GEOMETRY + BODY/OBJECT CONTACT FACT
    ↓
MASS/COMPLIANCE CONTACT IMPULSE
    ↓
OBJECT IMPACT ACOUSTIC EMISSION        (merge point with Audio A/B branch)
    ↓
MATERIAL-DEPENDENT CONTACT RESPONSE
```

## 12. Artifacts

`results/acanthostega_free_object_kinematics/`: `fok_harness.py`, `calibration.py/.json/.out`,
`calibration_table.txt`, `restore_verification.py/.json`, `audio_presets_isolation.py/.json`,
`preservation_after.json`, `preservation_diff.txt`, `preservation_reruns/` (Audio B + Audio A
calibration reruns, identical to stored results), `frontend_tests.log`, `frontend_build.log`,
`browser/` (Playwright smoke, screenshots, `browser_smoke.json`, real-session probe), `test_logs/`,
`gates.json`. Tests: `tests/test_acanthostega_free_object_kinematics.py`.
