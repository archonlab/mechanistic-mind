# Acanthostega Phase B — Local Physical Signal Transport

Preset `ACANTHOSTEGA_PHASE_B_LOCAL_SIGNAL` (UI label **Acanthostega Phase B Local Physical Signal**)
inherits `ACANTHOSTEGA_PHASE_B_COLUMN_TRANSFER` and adds mechanism `local_physical_signal_transport`
(ON only in this preset). Implementation: `mechanistic_mind/physical_system/local_physical_signal_transport.py`.

Target causality: OSC_EMIT (physical motor) → emission record at body pose → finite propagation delay →
distance attenuation → bounded range → reception threshold → anonymous `osc_l_k` / `osc_r_k` band energies →
ordinary cognition. **One emitter ≠ every agent receives immediately.** Not acoustics: no impact/locomotion/material
sounds, no walls/occlusion/reflection, no atmosphere/wind/water, no language/semantics/music.

## 1. Pre-audit of the existing signaling path (written before implementation)

Traced path (legacy, Tiktaalik and earlier Acanthostega presets):
motor selection (`composite_motor.py: apply_osc_motor_action`, legacy `runtime.apply_physical_action`) →
`body.osc_emit_remaining` → `oscillatory_signaling.step_oscillatory_signaling` (deposit at `body.cell()` into
`world.OSC_BANDS`, 3×3 kernel) → `_propagate_bands` (decay/diffusion) → receiver
`oscillatory_signaling.cognition_osc_fragments` (sample field at L/R head receptors) → `osc_l_*`/`osc_r_*` fragments →
cognition. Trace script/output: `results/acanthostega_local_signal/audit_trace.py`, `audit_trace_d{1,4,16}.json`.

| # | Question | Answer (legacy path) |
|---|---|---|
| 1 | Motor commands creating signal | `OSC_EMIT` (composite `oscillator.emit_trigger` → `composite_motor.apply_osc_motor_action`; legacy single-slot `runtime.apply_physical_action`); parameter motors `OSC_FREQ_UP/DOWN`, `OSC_AMP_UP/DOWN` shape it. Also researcher paths: `experimenter_control`, `oscillatory_signaling.set_undercover_osc_params`. Emission lasts `osc_emit_remaining` ticks (base 8, range 1..48). |
| 2 | Where source position is stored | Nowhere. `step_oscillatory_signaling` reads `body.cell()` every tick while emitting. |
| 3 | Stable emission identity | None (GT only: `osc-{tick}-{i}-{rem}`, not persisted). |
| 4 | Band / frequency / amplitude used | Yes: frequency → 6 Gaussian bands (`band_response`, width 0.22) × amplitude `osc_amp_u`. |
| 5 | `OSC_BANDS` dynamic field or cache | Dynamic physical field, shape (6,H,W), serialized in snapshots. |
| 6 | Update equation | `_propagate_bands`: ×(1−0.30) decay, 4-neighbour spread 0.18, clip `field_cap`=2.0, floor 1e-4; deposit 3×3 kernel (1, 0.45, 0.2)·amp·bands. |
| 7 | Finite propagation speed | No (`finite_propagation="NOT_IMPLEMENTED"`); diffusion ≤1 cell per call, no wavefront law. |
| 8 | Distance attenuation | Only emergent from decay+diffusion; no explicit law. |
| 9 | Reception threshold / range | None (only numerical floor 1e-4). Measured: d=1 receives Σ≈0.22, d=4 and d=16 receive 0. |
| 10 | Same-tick reception | No: deposit in `finish_tick` of T, sampling at T+1. |
| 11 | Same payload for all agents | Every agent samples the same shared field at its own L/R receptors (±0.55 of heading). |
| 12 | Source ID / position / distance in cognition | No; only `osc_l_0..5`, `osc_r_0..5` = clip(field/2, 0, 1). |
| 13 | Direct path outside world physics | None found. `multi_agent` v047 unused; `FIELD_A/FIELD_B` is a motion/contact field with no agent signal action. |
| 14 | Snapshot of active signal | `OSC_BANDS` array in world + body `osc_*` fields. |
| 15 | Two-agent `process_order` | Legacy quirk: each slot `finish_tick` and the container both run OSC propagation → `osc_emit_remaining` decrements ~2×/tick and totals depend on order (order (0,1) OSC total 11.77 vs (1,0) 13.44). `TwoAgentRuntime.restore` resets `process_order`. Pre-existing, kept for frozen presets. |
| 16 | Can anonymous bands be reused | Yes: new transport feeds the same `osc_l_k`/`osc_r_k` channels with the same clip/scale (2.0). |
| 17 | Tiktaalik contracts that must not change | Beta31 fingerprint `1621ef2c154864d1` (seed 17), beta31 mechanism map, `OSC_BANDS` semantics, snapshot schema. |

Decision: `OSC_BANDS` is a dense diffusion field with no finite speed, no range, no threshold and order-dependent
decrement, so it cannot provide the required law. In the new preset it is **not created**; bounded event-based
emissions replace it as the authoritative signal state. Reused: motor vocabulary, band profile (`band_response`),
body `osc_*` parameters, receptor geometry (`receptor_world_positions`), the `osc_l/r` sensor names and clip,
toroidal geometry, the multi-content spatial index. New: the emission records + reception seam.

## 2. Direct-delivery audit

No agent-to-agent path bypassing world state existed. In the new preset the only signal source for cognition is
`cognition_osc_fragments` → `local_physical_signal_transport.auditory_fragments`, which reads
`state.auditory[body_id]` written only by physical reception in `step_end_of_tick`. Legacy
`step_oscillatory_signaling` returns early (`runtime._step_oscillatory_signaling`) and OSC_BANDS is absent
(endogenous smoke: 0 legacy transport calls). Researcher intervention (`queue_researcher_emission`,
`POST /api/research/local-signal-emission`) only queues a physical emission (`INTERVENTION_SETUP`); it cannot
write auditory state. Test 27 monkeypatches `oscillatory_signaling.step_oscillatory_signaling` to raise, runs
the two-agent preset, and verifies it is never called, OSC_BANDS is None, and a far body gets zero osc energy.

## 3. Emission schema and medium

`PhysicalSignalEmission` (`PHYSICAL_SIGNAL_EMISSION_V1`): emission_id `signal-emission-{tick:09d}-{seq:04d}`,
schema_version, emission_tick, source_x/y (continuous body pose at emission), anonymous band_energies (6),
total_emitted_energy, propagation_speed, attenuation_version, attenuation_coefficient, maximum_range,
reception_threshold, expiry_tick, provenance (source body id researcher-side, motor command, frequency,
amplitude, ENDOGENOUS_MOTOR / INTERVENTION_EXPERIMENTER_BODY / INTERVENTION_SETUP), plus evaluated_by /
received_by dedup sets. Allocator (`alloc_tick`, `alloc_next`) is saved; IDs are never reused.

`UNIFORM_SIGNAL_MEDIUM_V1` (`UniformSignalMediumConfig`): propagation_speed v = 2.0 cells/tick,
attenuation_coefficient k = 0.08, maximum_range R = 8.0 cells, reception_threshold = 0.03 (total received energy),
noise_floor = 0, sensor_scale = 2.0 (existing osc clip), max_active_emissions = 256, history_limit = 32.
Same for all bands. Not "air", no humidity/temperature/wind. Unknown versions are rejected on restore.

## 4. Propagation law (`WAVEFRONT_CROSSING_CEIL_DISTANCE_OVER_SPEED_V1`, `INVERSE_QUADRATIC_ATTENUATION_V1`)

- d = shortest toroidal distance (world stays WRAP_PERIODIC 32×32).
- arrival_delay = max(1, ceil(d / v)); arrival_tick = emission_tick + arrival_delay; max delay = ceil(R/v) = 4;
  expiry_tick = emission_tick + 4.
- received[b] = emitted[b] / (1 + k·d²).
- Accepted iff d ≤ R and Σ received ≥ threshold, evaluated at the arrival tick with the receiver's pose then.

Calibrated values (amplitude 0.8, total emitted 2.1953; `results/acanthostega_local_signal/calibration.json`):

| d | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9+ |
|---|---|---|---|---|---|---|---|---|---|---|
| arrival delay | 1 | 1 | 1 | 2 | 2 | 3 | 3 | 4 | 4 | — |
| received total | 2.195 | 2.033 | 1.663 | 1.276 | 0.963 | 0.732 | 0.566 | 0.446 | 0.359 | none |

A single emission lives ≤ 5 ticks and touches at most a radius-8 disc (~201 of 1024 cells).

## 5. Temporal causality

observation(T) → cognition/motor(T) → emission(T) recorded at end of tick T (`step_end_of_tick` runs after
`tick += 1`, te = tick−1) → shell n=1 evaluated for arrival tick T+1 → observation(T+1). Minimum delay 1,
no same-tick reception (tests 11, 12). Self-reception also arrives at T+1.

## 6. Receiver-position policy (`POSE_AT_ARRIVAL_WAVEFRONT_CROSSING_V1`)

Delivery is not bound to a receiver at emission. At each arrival step n the analytic front sweeps the annulus
((n−1)v, nv]. A body receives from an emission exactly once, at the first step where its **current** pose lies
inside the swept annulus: d_prev > (n−1)v (≥ for n=1) and d_now ≤ nv, where d_prev is the distance of its pose
at the previous tick. Consequences (all tested, 32–35): the pose at arrival is used; a body that moves outward
ahead of the front is never crossed; a body that moves into the front's path at the arrival tick receives; exact
continuous distance is used (same cell, different sub-cell positions → different arrival ticks: 12.45 → tick 1,
12.55 → tick 2). Bodies are assumed to move ≤ 1 cell/tick (`MAX_RECEIVER_STEP`); faster teleports may be missed.

## 7. Agent payload

Cognition sees only `osc_l_0..osc_l_5`, `osc_r_0..osc_r_5` (unchanged names): sum over all emissions arriving
this tick of band energy attenuated to each existing head receptor (L/R at ±0.55 of heading;
`receptor_world_positions`), then clip(raw/2.0, 0, 1). The percept lasts the arrival tick only; otherwise zeros.
Not exposed: emission id, source id, source coordinates, exact distance, bearing, event type, command name,
formula, researcher label, semantic category, number of sources. The small L/R difference is the pre-existing
physically grounded receptor geometry (allowed by spec); no source_direction/source_distance was added.
`observation.FORBIDDEN_TOKENS` extended with transport tokens; audits run in tests 22–26 and endogenous smoke.

## 8. Self-reception and overlap

Emitter is not special-cased: same law, d≈0 (receptors ±0.55), next-tick arrival. Researcher counters split
self/foreign; cognition gets no self flag. Overlap: contributions summed per band then clipped by the sensor
(`SUM_THEN_EXISTING_OSC_SENSOR_CLIP_V1`); no per-source array. Receipts can hold bounded source refs.

## 9. Spatial locality / performance

`WAVEFRONT_SHELL_CELLS_X_MULTI_CONTENT_BODY_REFS_V1`: per active emission and step n, only cells of the annulus
[(n−1)v − 1 − 1.5, min(nv, R+v) + 1.5] (precomputed wrapped offsets, `offset_table`/`shell_cells`) are visited
and BODY refs are read from the multi-content spatial index (fallback: transient body bucket, counted).
Cost ∝ active emissions × shell cells + local candidates. No full-world tensor, no world clone, no history
scan. `results/acanthostega_local_signal/perf.json`: 256 bodies × 4 emissions/tick → 7.4 ms/step,
12 212 candidate checks vs 98 304 all-pairs; 64 bodies × 1 → 0.9 ms, 758 vs 6 144; index fallbacks 0.

## 10. Receipts

`LOCAL_PHYSICAL_SIGNAL_EMISSION` and `LOCAL_PHYSICAL_SIGNAL_RECEPTION` (researcher-only, all fields of the spec;
flags semantic_message / direct_delivery / global_delivery / source_identity_exposed / exact_distance_exposed /
bearing_exposed = false). Rejections recorded only for candidates actually crossed by the front (bounded).

## 11. Snapshot / restore

Serialized only when ON (`serialize_state`/`restore_state`): schema, medium config, active emissions (with dedup
sets), allocator, last_processed_tick, prev poses, pending auditory entry, bounded recent emission/reception
history, counters, graph. Restore continues propagation with the same arrival ticks, does not repeat or skip
receptions, does not reuse IDs; missing field → OFF; Tiktaalik snapshots get no new keys.
Verification: `results/acanthostega_local_signal/restore_verification.json` (single + two-agent VERIFIED).

## 12. Authority map

| Concern | Authority |
|---|---|
| Signal world state | `world.local_signal_transport` (`LocalSignalState`: active emissions) |
| Emission creation | `step_end_of_tick` (endogenous from `osc_emit_remaining`; researcher queue) |
| Propagation / reception | `step_end_of_tick` (single call per tick; in two-agent run by `TwoAgentRuntime` signals span, order-free) |
| Sensor seam | `oscillatory_signaling.cognition_osc_fragments` → `auditory_fragments` |
| Researcher view | receipts, `researcher_summary`, `observer_overlay`, Scientific V3 `local_physical_signal` event refs, Analyzer section `LOCAL PHYSICAL SIGNAL TRANSPORT` (`scientific_v3/local_physical_signal_summary.py`) |
| Frozen presets | legacy `OSC_BANDS` path, untouched |

## 13. Limitations

- Not acoustics: uniform medium, no material/geometry/atmosphere, noise floor 0, no occlusion/reflection.
- Receiver speed assumption ≤ 1 cell/tick for the crossing test (teleports may be missed).
- With v=2, R=8 the front stops at R, so BEYOND_MAXIMUM_RANGE rejections practically never occur (absence
  beyond R is structural; verified by calibration d=9,10,12,16).
- Auditory percept lasts exactly the arrival tick.
- Legacy Tiktaalik double-propagation / process-order quirk kept unchanged (frozen); `TwoAgentRuntime.restore`
  resets `process_order` (pre-existing; the new transport is order-free).
- `FIELD_A/FIELD_B` untouched.
- Bug found during browser smoke and fixed: Observer preflight marked `oscillatory_signaling` as
  CONFIGURATION_MISMATCH because its availability probe required `OSC_BANDS`; `mechanism_configuration._sensor_availability`
  now also accepts the local transport state (only when that state exists → Tiktaalik unaffected). Regression test 43b.
- Observer shows a researcher panel (origin, wavefront radius, range, energy, status, receivers); no WorldMap ring
  glyph and no 3D renderer.
- `results/acanthostega_column_transfer/preservation_probe.py` was edited to skip `LOCAL_SIGNAL` preset names
  when enumerating presets (forward compatibility of column-transfer test 44; no semantic change).
- Pre-existing unrelated failures: `test_observer_terrain::test_baseline_presets_have_no_terrain_unless_configured`,
  `test_resource_ecology_authority_beta2` E11/E14/E15, `test_mechanism_control_ui_coverage::test_frontend_vision_control_sources_exist`,
  `test_beta2_sigint_01_signal_context::test_web_serialization_signal_context_on_frame` (fails on the untouched baseline too).

Statuses: MATERIAL_DEPENDENT_ACOUSTICS = NOT_IMPLEMENTED; GEOMETRY_AWARE_ACOUSTICS = NOT_IMPLEMENTED;
ATMOSPHERIC_ACOUSTICS = NOT_IMPLEMENTED; SEMANTIC_COMMUNICATION = NOT_ESTABLISHED.
