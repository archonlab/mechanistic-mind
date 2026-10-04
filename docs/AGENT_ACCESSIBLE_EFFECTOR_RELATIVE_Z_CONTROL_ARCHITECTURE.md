# AGENT_ACCESSIBLE_EFFECTOR_RELATIVE_Z_CONTROL_ARCHITECTURE

Architecture audit only. **No production implementation in this task.**

Authority: current repository code at HEAD `5d0f14cd`, plus established reachability/Analyzer results.

---

## 1. Primary question (verdict)

**Smallest scientifically valid control:** independent **ternary vertical actuator factors per hand**, modeled after OSC frequency/amplitude:

| Factor | Domain | Semantics (physical only) |
|--------|--------|---------------------------|
| `effector_z_left` | `{-1, 0, +1}` | DOWN / NONE / UP body-local relative_z rate step |
| `effector_z_right` | `{-1, 0, +1}` | DOWN / NONE / UP |

Realization each tick (when nonzero):

```
requested_delta_z = factor × max_delta_z_per_tick   # ±0.1075 under current defaults
→ request_actuated_relative_displacement(... EBAE ...)
→ existing MRWA clip/reach
→ tip_z = centre_z + relative_z
→ existing ETC / VW5 / SETMR
```

**Not** DIG/TOUCH_GROUND/target-Z/auto-contact. Context-free actuator command only.

**Reuse:** existing EBAE bounded actuator is the correct primitive; only **agent motor wiring** is missing.

---

## PART A — Current motor pipeline

```
observation (accessible)
  → run_cognition_before_action          [cognition.py]
  → PSC compete on actions=list(available_actions())  # BUG/DEBT: 5 loco only
  → selected locomotion string
  → _factorized_composite_from_cognition  [runtime.py]
       → select_factorized_side_channels    [composite_motor.py]  # neck/OSC/push/grasp/pair
  → CompositeMotorOutput (COMPOSITE_MOTOR_V1)
  → begin_tick: realize_discrete_action (loco) + apply_composite_motor (neck/OSC/push)
  → finish_tick: body integrate → resolve_shared_world_manipulators (GRASP/pair)
                 → detect_effector_terrain_contacts (ETC)
  → SMC update / prospection on last_motor_output (signature L|N|E|F|A|P only)
```

| Stage | Module | Persist / capture |
|-------|--------|-------------------|
| Available actions (runtime) | `_sync_embodiment_dofs` → `cognition["available_actions"]` | cognition state |
| PSC candidates | `cognition.py:282` bare `available_actions()` | **ignores** synced repertoire |
| Factor picks | `select_factorized_side_channels` | `CompositeMotorOutput` |
| Motor receipt | `scientific_v3/receipts.build_motor_receipt` | `m:{run}:{tick}:{agent}` |
| relative_z | MRWA offsets | snapshot `manipulator_relative_world_actuation_state` |
| Actuation | EBAE (researcher only today) | snapshot `effector_bounded_actuator_effort_state` |

**Factor style today:** independently sampled side channels; sparse NONE-preferring (`explore_rate≈0.08`); OSC uses discrete `{-1,0,+1}`; locomotion is categorical 5-way via PSC; **not** jointly enumerated in production.

---

## PART B — Existing manipulator factors (agent-selectable)

| Control | Agent selectable? | How |
|---------|-------------------|-----|
| MOVE / WAIT | YES (PSC primary) | locomotion factor |
| NECK_LEFT/RIGHT/HOLD | YES (side-channel) | if articulated_head |
| OSC_FREQ/AMP UP/DOWN, EMIT | YES (side-channel) | ternary deltas |
| PUSH | YES (side-channel) | boolean |
| LEFT_GRASP / LEFT_RELEASE | YES (side-channel; or PSC if repertoire fixed) | independent of RIGHT |
| RIGHT_GRASP / RIGHT_RELEASE | YES | independent |
| BRING_TOGETHER / SEPARATE | YES (pair factor) | aperture |
| COMBINE / APPLY_TO_SURFACE | YES when mechanisms ON | |
| **Vertical effector (relative_z)** | **NO** | researcher/EBAE only |
| Force without movement | PUSH (body contact), not tip force | |
| Held-object vertical | follows `body.z + relative_z` when held | no independent held motor |

LEFT/RIGHT grasp: **independent factors**, same tick allowed. Pair aperture: **one shared factor**. Tuple cardinality: **~9 structured slots** (loco|neck|osc|push|manip|left|right|pair|deposit), not a flat Cartesian product.

---

## PART C — Physical relative_z authority

| Property | Exact |
|----------|-------|
| Field | `offsets["{body_id}\|{LEFT\|RIGHT}"].z` |
| Rest / default | `0.0` |
| Envelope | `±max_relative_z = ±1.075` (`BODY_CONTACT_RADIUS+0.5`) |
| Rate | `max_delta_z_per_tick = 0.1075` |
| Clamp | rate then reach |
| Tip equation | `effector_world_pose`: `ez = centre_z + relative_z` (MRWA ON) |
| Persistence | YES across ticks |
| Passive return | NO (holds until actuated) |
| WAIT | does not change relative_z |
| Body motion | tip follows body centre_z; relative_z is body-local offset |
| Held object | `held_z = body.z + relative_z` (+ offset 0) |
| Contact | ETC uses tip; EBAE can block inward Δz vs terrain |
| Work | EBAE only (MRWA kinematic-only); capacity ≈ `m·g·Δz_rate` |
| Cognition | `cognition_exposed: False` on actuation receipts |
| Restore | MRWA state restored; no auto-actuation |

**Conclusion:** EBAE already provides the bounded actuator primitive. Gap is **only** agent-facing motor wiring into COMPOSITE_MOTOR_V1 apply path.

---

## PART D — Candidate designs (evaluated)

### Option A — Independent ternary per-hand vertical factors ★ RECOMMENDED

```
LEFT_Z  ∈ {UP, NONE, DOWN}   →  Δz = {+rate, 0, −rate}
RIGHT_Z ∈ {UP, NONE, DOWN}
```

| Criterion | Score |
|-----------|-------|
| Fits existing side-channel pattern (OSC) | Excellent |
| Context-free / non-semantic | Yes |
| Reuses EBAE/MRWA | Yes |
| Concurrent LEFT+RIGHT | Natural |
| Learning surface | Extend SMC signature + side-channel predict tokens |
| Forbidden designs avoided | Yes |

**Token naming (recommended):** `LEFT_EFFECTOR_Z_UP` / `LEFT_EFFECTOR_Z_DOWN` / `RIGHT_EFFECTOR_Z_UP` / `RIGHT_EFFECTOR_Z_DOWN` (or `EFFECTOR_Z_*` with hand in factor field). Avoid `DIG`, `GROUND`, `REACH_TARGET`.

### Option B — Shared single vertical factor (both hands)

One factor moves both tips. Rejects for asymmetry (audit showed LEFT/RIGHT XY independent); weaker scientific generality.

### Option C — Absolute target relative_z in cognition

`SET_Z_TO_VALUE` / continuous target. **Reject:** encodes goal pose; invites semantic targeting; not matching OSC ternary pattern; needs new admission rules.

### Option D — PSC-primary discrete actions only

Add tokens to `available_actions` and fix `cognition.py:282` so PSC can select them as primary (force loco=WAIT). Possible but **worse** than side-channel: mutually exclusive with locomotion each tick; less like OSC; still needs apply→EBAE.

### Option E — Researcher action exposed as agent action

Masquerade `request_actuated_*` behind fake cognition. **Reject** (forbidden).

### Option F — Morphology / pitch / crouch instead

**Reject** for this seam: reachability audit showed morphology already sufficient; wrong problem.

### Option G — Semantic DIG / TOUCH_GROUND

**Reject** (forbidden).

---

## PART E — Recommended architecture (Option A detail)

### Motor schema extension (conceptual)

Add to `CompositeMotorOutput`:

```
effector_z_left: int ∈ {-1,0,+1}
effector_z_right: int ∈ {-1,0,+1}
```

Populate in `select_factorized_side_channels` when MRWA+EBAE active, mirroring OSC freq/amp picks from new available tokens.

### Apply seam

In `begin_tick` after composite build (or early `finish_tick` **before** ETC):

```
if effector_z_left != 0:
    request_actuated_relative_displacement(
        ..., effector_id="LEFT",
        requested_delta_z=effector_z_left * max_delta_z_per_tick, ...)
# same for RIGHT
```

Prefer **EBAE** (work + terrain constraint) over bare MRWA for organism actuation so Analyzer CONTACT/WORK chain stays coherent.

### Tick order (proposed)

```
begin_tick: select factors including effector_z_*
            apply loco + neck/OSC/push
finish_tick: body vertical
             resolve manipulators (grasp/pair)
             **apply effector_z via EBAE**   ← new; before or with held snap
             ETC / HOTC / EORT
```

Must not apply relative_z **after** ETC if contact should see final pose (current ETC already uses final pose when relative_z set earlier).

### Multi-tick nature

Rate 0.1075 ⇒ ~10 ticks to extreme reach. Organism must **persist** UP/DOWN selection across ticks (or re-select). Side-channel NONE-preferring exploration means spontaneous ground contact remains rare until learning—acceptable scientifically.

### Learning / credit (required companion surfaces — design only)

1. Extend `motor_signature_from_composite` with `|ZL:{d}|ZR:{d}` (or similar).
2. Add tokens to `_sidechannel_predict_tokens`.
3. Optional neck-style dual-write `pr.learn_transition` for vertical tokens.
4. Analyzer already has `REQUIRED_CONTROL_NOT_IN_REPERTOIRE` → becomes classifiable as SELECTED/ACTUATED once wired.

### Privacy

Action tokens are motor vocabulary (like `OSC_FREQ_UP`), not observation. Do not put `relative_z` scalar or occupancy into `accessible_observation`. Keep researcher receipts `cognition_exposed: False` for internal EBAE detail if needed; organism only sees consequences through existing sensors.

### Tiktaalik

Mechanism OFF unless MRWA/EBAE present — Beta 3.1 frozen: do not enable.

### TwoAgent

Per-body `body_id|effector_id` keys already isolate offsets.

### Snapshot

Existing MRWA/EBAE serialize/restore sufficient; new motor fields on `last_motor_output` need receipt capture.

---

## PART F — Explicit non-goals

- No DIG/PLACE/BUILD/excavation success.
- No auto-contact / snap.
- No free work / unlimited reach.
- No second integrator or second work ledger.
- No FIRST_HABITABLE in this audit.
- No production code in this task.

---

## PART G — Implementation slice recommendation (future)

**Name:** `AGENT_ACCESSIBLE_EFFECTOR_RELATIVE_Z_CONTROL_V1` (mechanism/wiring only)

**Minimal PR surface (when authorized):**

1. `actions.py` — add 4 tokens when MRWA+EBAE ON  
2. `composite_motor.py` — fields + side-channel picks  
3. `runtime.py` — apply → EBAE once per hand per tick  
4. `sensorimotor_consequence.py` — signature extension  
5. `scientific_v3/receipts.py` / capture — motor components  
6. Tests: repertoire presence; apply Δz; ETC contact under drive; privacy; Tiktaalik off; restore  
7. Analyzer: relative_z outcome leaves REQUIRED_CONTROL_NOT_IN_REPERTOIRE when selected

**Do not** change rate/envelope/morphology in the first wiring slice.

---

## PART H — Decision gate

| Question | Answer |
|----------|--------|
| Morphology change required? | **NO** |
| New physical DOF required? | **NO** |
| Reuse EBAE? | **YES** |
| Recommended design | **Option A** ternary per-hand side-channels |
| Blocker to FIRST_HABITABLE claiming autonomous terrain work? | **YES** until this (or equivalent) is implemented |
| Can FIRST_HABITABLE proceed with honest limits without this? | **YES** if it does not claim agent terrain manipulation |

```
AUDIT_COMPLETE=YES
PRODUCTION_CODE_CHANGED=NO
PHYSICS_CHANGED=NO
COGNITION_CHANGED=NO
PUBLIC_MODEL_CHANGED=NO
RECOMMENDED_DESIGN=OPTION_A_INDEPENDENT_TERNARY_PER_HAND_EFFECTOR_Z
REUSES_EBAE=YES
REUSES_MRWA=YES
SEMANTIC_EXCAVATION_ACTION=NO
MORPHOLOGY_CHANGE_REQUIRED=NO
NEW_PHYSICAL_DOF=NO
CURRENT_AGENT_SELECTABLE=NO
ANALYZER_CLASS_TODAY=REQUIRED_CONTROL_NOT_IN_REPERTOIRE
TOTAL_SIMULATED_TICKS=0
NEXT_SAFE_SEAM=AGENT_ACCESSIBLE_EFFECTOR_RELATIVE_Z_CONTROL_V1_OR_FIRST_HABITABLE_WITH_HONEST_LIMITS
```
