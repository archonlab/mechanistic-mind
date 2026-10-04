# ACANTHOSTEGA PHYSICAL CONTACT ACOUSTIC EMISSION (Audio B)

Preset `ACANTHOSTEGA_PHASE_B_CONTACT_ACOUSTICS` (UI: "Acanthostega Phase B Contact Acoustics"),
inheriting `ACANTHOSTEGA_PHASE_B_LOCAL_SIGNAL`. Acanthostega-only mechanism
`physical_contact_acoustic_emission`.

Causal chain: relative motion / PUSH → unchanged soft-contact solver (+ unchanged PUSH) → measured,
transferred momentum → bounded acoustic energy → existing Local Physical Signal Transport
(delay, attenuation, radius, threshold) → anonymous `osc_l_*` / `osc_r_*` bands. There is no
`CONTACT` event → sound mapping. A boolean contact flag alone never produces sound.

## 1. Implementation map (established before implementation)

| Concern | Location |
|---|---|
| Body-body contact detection + impulse | `physical_system/body_contact.py::resolve_soft_contact` (unchanged) |
| PUSH through contact | `physical_system/physical_push.py::apply_push_through_contact` (unchanged) |
| Where contact runs | `physical_system/two_agent.py::TwoAgentRuntime._step_once`, span `contact_push` |
| Transport | `physical_system/local_physical_signal_transport.py` (additive entry point only) |
| New mechanism | `physical_system/physical_contact_acoustic_emission.py` |
| Snapshot | `physical_system/runtime.py`, `planet/runtime.py`, `planet/state.py` |
| Preset chain | `model/acanthostega.py`, `model/lines.py`, `physical_system/experiment_canonical.py`, `mechanism_registry.py`, `locomotion_profile.py`, `ui/psy_observer_web/session.py` |
| Privacy | `physical_system/observation.py::FORBIDDEN_TOKENS` |
| Observer | `ui/psy_observer_web/serialize.py` (`world.contact_acoustic_summary`), `web/psy-observer/src/App.tsx`, `observer/modelPreset.ts` |
| Analyzer | `scientific_v3/physical_contact_acoustic_summary.py`, `scientific_v3/capture.py`, `scientific_v3/analyzer_next/pipeline.py` |

## 2. Audit (contact / PUSH)

Call chain (one tick, `TwoAgentRuntime._step_once`, slot tick T → T+1):

```
observations()                                  # cognition input for tick T (before any physics)
for i in order: slots[i].begin_tick()           # cognition + motor intent
step_planet(world)
for i in order: slots[i].finish_tick()          # body integration; slot tick becomes T+1
[contact acoustics] capture_pre_contact(body_refs_for_runtime(self))   # read-only pose/velocity copy
span contact_push:
  for ia < ib (slot index order, each pair exactly once):
     receipt = resolve_soft_contact(a, b, ...)                          # detection + penalty impulse
     push    = apply_push_through_contact(a, b, contact=receipt.contact)  # optional PUSH impulse
     [contact acoustics] collect row (ids, masses, receipts)
  [contact acoustics] process_contact_pairs(world, cfg, rows, emission_tick = T)
manipulators → reconcile_contents → resources
span signals: lps.step_end_of_tick(tick_now = T+1)   # creates queued OSC emissions of tick T,
                                                     # processes wavefront arrivals at T+1
```

Findings:
1. Contact is computed only in `resolve_soft_contact`, called only from `TwoAgentRuntime._step_once`.
   Single-agent `PhysicalSystemRuntime` has no body-body contact.
2. Impulse: yes, a penalty impulse `|J| = 0.25 · overlap`, `overlap = max(0, 1.15 − d) + 0.15 · shared_cells`,
   along the toroidal centre normal. The receipt fields `impulse_a/impulse_b` hold Δv = J/m (before the
   velocity clamp); momentum is recovered as `m · Δv`.
3. Detection and application happen in the same function (no separate detection pass).
4. Each unordered slot pair is visited exactly once per tick (`ia < ib`).
5. PUSH: `0.4 · push_exertion` along the pusher heading, equal and opposite, at most one pusher per pair
   per tick, only if `contact`. PUSH is `OFF` in every Acanthostega preset, including the new one; it is
   handled when a config enables it.
6. Yes: resting overlap produces a correction impulse every tick (continuous nonzero impulse).
   Therefore "impulse > ε" alone would hum; an onset policy is required (§6).
7. Safe place: after the whole contact/PUSH loop and before the signals span (all impulses are final;
   the transport step of the same tick follows).
8. Relation to the transport: emissions use `emission_tick = T`, the same te that OSC emissions of the
   same tick use; the transport step at `tick_now = T+1` delivers the first shell.

Relative velocity is not used by the solver. The pre-resolution relative velocity (and its normal
component) is available from the read-only pre-contact snapshot and is reported as such. The solver has no
contact point, so the position is derived (§7).

## 3. Emission condition and law

Per canonical pair (sorted body ids `p0|p1`), measured on body `p1`:

```
J_now_vec   = m(p1) · Δv_contact(p1)                  # solver impulse this tick
excess      = max(0, |J_now_vec| − sounded_level)      # new contact impulse in this episode
contact_new = J_now_vec · excess / |J_now_vec|
push_vec    = m(p1) · Δv_push(p1)  (0 if no PUSH)      # same physical PUSH impulse, not a second branch
J_new_vec   = contact_new + push_vec
emit  iff  |J_new_vec| > ε
E_unclamped = 5.0 · |J_new|
E           = clamp(E_unclamped, 0, 2.5)   (0 if |J_new| ≤ ε or not finite)
bands       = UNIFORM_BROADBAND_V1: E/6 in each of the 6 anonymous bands
```

Profile `CONTACT_ACOUSTIC_PROFILE_V1`: `impulse_epsilon = 0.04`, `acoustic_coupling = 5.0`,
`max_acoustic_energy = 2.5`, law `LINEAR_CLAMPED_IMPULSE_TO_ACOUSTIC_ENERGY_V1`.
ε = 0.04 sits just above the smallest solver quantum (1 shared footprint cell at d ≥ 1.15:
J = 0.0375), so grazing single-cell contact is silent. Coupling 5.0 maps a typical head-on overlap
(J ≈ 0.16) to E ≈ 0.81, inside the range of total energies of the existing LPS calibration emissions
(0.055–2.2 in `results/acanthostega_local_signal/calibration.json`). The clamp 2.5 is reached
at J = 0.5 (reached only with PUSH).

Model abstraction: acoustic energy is not withdrawn from mechanical energy
(`mechanical_energy_withdrawn = false`), because there is no shared conservation ledger yet.
The parameters live in the new preset's config only and do not change the solver.

## 4. Onset / resting policy (`CONTACT_EPISODE_SOUNDED_IMPULSE_LEVEL_V1`)

* `sounded_level[pair]` = the largest contact impulse already converted to sound in the current episode.
* Contact continues and J does not exceed the level → silence `RESTING_CONTACT_NO_NEW_IMPULSE`.
* New impulse > 0 but ≤ ε → silence `NEW_IMPULSE_BELOW_EPSILON` (level not raised, so accumulated growth
  can still sound once it exceeds ε).
* Pair no longer in contact → episode ends (entry deleted) → renewed impact sounds again.
* PUSH during contact adds its own measured impulse → can sound once (one emission per pair per tick).

## 5. Position

`TOROIDAL_MIDPOINT_OF_BODY_CENTRES_AT_CONTACT_DETECTION_V1`: the midpoint along the shortest toroidal
displacement between the pre-resolution body centres (`a + Δ/2`, wrapped). There is no arithmetic mean
across the WRAP boundary. Fallback (no pre-contact capture): `..._AFTER_RESOLUTION_V1`.

## 6. Tick order

```
tick T:   observation(T) → cognition → planet → body integration (finish_tick)
          → contact resolution → contact acoustic emission (emission_tick T)
          → transport step tick_now=T+1 (first shell; receivers' auditory for T+1)
tick T+1: observation(T+1) contains the attenuated bands (distance ≤ v·1); farther shells later
```

There is no retroactive delivery: `emit_local_physical_signal` rejects `emission_tick < last_processed_tick`
(`RETROACTIVE_EMISSION`). The global Tiktaalik tick order and the cognition order are unchanged.

## 7. Transport integration

New generic entry point `emit_local_physical_signal(world, emission_tick, x, y, band_energies, provenance)`
creates the emission immediately through the existing `_create_emission` (stable
`signal-emission-{te:09d}-{seq:04d}` id, the same speed, attenuation, radius, threshold, spatial index and
snapshot). OSC_EMIT and researcher emissions keep their path. Additive details:
* provenance `PHYSICAL_CONTACT_IMPULSE`; lazy counter `physical_contact_emissions`;
* the emission receipt carries `cause_receipt_ref` and `source_body_pair` only for contact provenance;
* the graph key uses `CONTACT:p0|p1` when there is no single source body;
* `source_body_id = None` → pair members count as foreign receptions (no self-reception flag).
Within one te, contact emissions receive their sequence numbers before OSC emissions (they are
created earlier in the tick).

## 8. Dedup / order independence

Canonical sorted pair key; duplicate rows for the same pair are suppressed; at most one emission per pair
per tick; the pass is idempotent per tick (`last_processed_tick`). Results do not depend on slot order,
row order, a/b orientation, or body id names (tests 10, 13, 20).

## 9. Privacy

Agents receive only the existing anonymous `osc_l_*` / `osc_r_*` bands. Forbidden tokens added:
`physical_contact_acoustic`, `PHYSICAL_CONTACT`, `contact-impulse-`, `canonical_body_pair`,
`CONTACT_ACOUSTIC`, `impulse_magnitude`. Researcher receipts: `PHYSICAL_CONTACT_IMPULSE_MEASUREMENT`
(every contact tick) and `PHYSICAL_CONTACT_ACOUSTIC_EMISSION` (emission id, tick, pair, position,
derivation, contact_receipt_ref, impulse vectors/magnitudes, pre-contact relative velocity,
coupling, unclamped/emitted energy, band vector, mechanism, preset, `semantic_label=false`,
`agent_accessible=false`). Reception receipts link through `emission_id` (researcher-only).

## 10. Snapshot / restore

`world.contact_acoustic_state` (schema `PHYSICAL_CONTACT_ACOUSTIC_STATE_V1`: config, `sounded_level`,
measurement sequence, counters, histories, `last_processed_tick`) is serialized only when present. The config
key appears only when ON. Pending wavefronts are in the existing LPS state. Old snapshots without the
state load with the mechanism OFF and create no retroactive sound.

## 11. Observer / Analyzer

Observer: the mechanism row appears only for Acanthostega. The existing LPS overlay gains the
`contact-acoustic-overlay` counters row, and emission rows show a tooltip with the contact-impulse cause, |J|,
energy and position derivation. There are no sound names and no extra Apply button; the renderer is not a source.
Analyzer: section `PHYSICAL CONTACT ACOUSTIC EVENTS` (payload key `physical_contact_acoustic_events`)
covers counts, silent below-ε / resting, emissions, impulse and energy ranges, monotonicity, linked receptions, delays,
attenuation by distance, resting re-emissions, duplicates, causal links, provenance quality, and explicit
`IMPACT_UNDERSTANDING` / `COMMUNICATION` = `NOT_ESTABLISHED`.

## 12. Limitations

* The solver is a penalty solver: its impulse is overlap-based (position penetration), not velocity-based, and is
  quantised by footprint cells, so identical centre distances can give different J depending on grid
  alignment.
* PUSH is OFF in the preset (unchanged scope); PUSH acoustics are exercised only with test configs.
* No mechanical energy withdrawal (documented abstraction).
* Pair members count as foreign receivers of their own contact sound (no single source body).
* Body-body contact exists only in two-agent (or experimenter-host) runs.
* The LPS summary's generic static NOT_IMPLEMENTED list still names `impact_or_locomotion_sounds`;
  the contact section reports the Audio-B status.
* The analyzer payload key is always present (status `NOT_AVAILABLE` when there are no events).
* Not implemented: object/held-object collisions, footsteps, materials, resonance, reflection, occlusion,
  reverberation, Doppler, media, semantics, rewards.

## 13. Bug fixed during this stage

The Observer experimenter slot (`experimenter_control.spawn_experimenter_body`) was not marked
`_lps_parent_managed`. It therefore ran its own LPS end-of-tick step, advancing the shared transport clock
before the container's contact and signal pass. This rejected contact emissions as retroactive and, in the
LOCAL preset, suppressed all agent receptions while an experimenter body existed. It is now marked like
every other slot, and exactly as `TwoAgentRuntime.restore` already did.
