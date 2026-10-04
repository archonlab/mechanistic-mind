# ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION_V1 — Architecture

**Document type:** ARCHITECTURE AUDIT → IMPLEMENTATION GATE  
**Live forensic:** `results/live_observer_translation_block_forensics_20260929/FINAL_REPORT.md`  
**Parent locomotion tip:** `ACANTHOSTEGA_BETA4_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION`  
**Grandparent:** `ACANTHOSTEGA_BETA4_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR`  
**Crowding next parent:** this ALTVSF tip (after lineage convergence repair)

---

## Gate decision

**READY_TO_IMPLEMENT** — physical semantics are uniquely established.

| Item | Status |
|------|--------|
| Architecture decision | **DECIDED** |
| Implementation | **IMPLEMENTED** |
| Tiktaalik / Phase C / prior Beta 4 presets | **UNCHANGED** (mechanism OFF) |
| Global μ_k weaken / MOVE inflate / magic floor | **FORBIDDEN** |

---

## Forensic remainder (after BNLT Option C)

BNLT repair correctly sets `drive_accel = |J_lim|/(m_eff·dt)` so kinetic no longer zeros MOVE when `speed_trial ≤ μ_k g dt`. Live counters: `blocked_insufficient_ticks=0`, `translation_ticks>0`.

Practical speed remains a **micro-slide** because Option C still applies full kinetic Coulomb to trial velocity that **includes** the same-tick traction-transmitted Δv, then restores only:

```text
v_residual ≈ (μ_s − μ_k) · g · dt = (static_ratio − 1) · μ_k · g · dt
           ≈ 0.25 · μ_k · g · dt ≈ 0.008   (live μ_s/μ_k = 1.25)
```

Static capacity already limited transmission (`|J|≤μ_s N dt`). Debiting that same thrust again with μ_k is a **double charge** of one contact interaction.

---

## Unique physical roles (established)

| Channel | Role | Law |
|--------|------|-----|
| **Static traction capacity** | Begin-tick **transmission** limiter for intentional MOVE | `|J_act| ≤ μ_s · N · dt` — not dissipative |
| **Kinetic sliding friction** | Dissipates **slip** (passive / uncontrolled relative tangential motion) | Coulomb on slip velocity |
| **Active locomotion traction** | Same-tick capacity-limited MOVE impulse is **propulsive static friction** | Must not be treated as slip to dissipate |

**Invariant (V1):** On a grounded active MOVE tick, the co-directed component of trial velocity up to `|J_act|/m_eff` is **traction-protected**. Kinetic Coulomb applies only to the **slip residual** (trial minus protected). WAIT / static hold / true breakaway / airborne / FREE objects unchanged. μ_k map unchanged. Nominal MOVE impulse_scale unchanged. No minimum displacement floor.

This is **not** Option A (“suppress all MOVE-tick kinetic”). Kinetic still brakes env excess and opposing slip during MOVE. It is the minimal form of the long-term “single contact budget” distinction rejected as too large for BNLT Option C.

---

## Equations (mechanism ON)

```text
J_act     = capacity-limited MOVE impulse (already stamped by BNLT parent)
Δv_drive  = J_act / m_eff
û         = Δv_drive / |Δv_drive|
along     = v_trial · û
protected = min(max(along, 0), |Δv_drive|) · û     # co-directed, ≤ drive
v_slip    = v_trial − protected
v_slip'   = coulomb_kinetic_step(v_slip; μ_k, …)   # slope drive_accel may remain
v_out     = v_slip' + protected
```

When `v_trial ≈ Δv_drive` (MOVE from near rest), `v_slip≈0` → kinetic no-op on drive → practical speed ≈ traction-limited Δv (minus prior env/drag), not `(μ_s−μ_k)g`.

---

## Isolation

| Preset | Behavior |
|--------|----------|
| Tiktaalik | unchanged |
| Phase C / G2A without this child | unchanged (mechanism OFF) |
| Parent BNLT repair | unchanged (mechanism OFF) |
| Sibling RCSS | unchanged as parent (ALTVSF now **child of RCSS**) |
| **Cumulative tip** | RCSS world + ALTVSF locomotion ON |

**Preset:** `ACANTHOSTEGA_BETA4_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION`  
**Mechanism:** `active_locomotion_traction_vs_sliding_friction`  
**Profile:** `ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION_V1`  
**Parent:** `ACANTHOSTEGA_BETA4_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION`

Future crowding / EVENT_DRIVEN retry must **child this preset**:

```text
PARENT_PRESET = ACANTHOSTEGA_BETA4_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
```

See also: `docs/ACTIVE_LOCOMOTION_RCSS_LINEAGE_CONVERGENCE_REPAIR.md`

---

## Out of scope

Gait, legs, feet, jump, climb, volumetric free-space, weakening μ_k, magic floors, arbitrary MOVE gain, Tiktaalik, Phase C, mutating prior Beta 4 presets, live-run control, terrain/crowding roadmap continuation.
