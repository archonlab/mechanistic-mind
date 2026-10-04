# G2B Radius-Aware Support Points — Thresholds Addendum

**Date:** 2026-09-28 (Europe/Oslo, UTC+2)  
**Status:** BINDING before Hybrid C⋆ implementation  
**Parent architecture:** `docs/ACANTHOSTEGA_RADIUS_AWARE_SUPPORT_POINTS_G2B_ARCHITECTURE.md` §5 / §23  
**Reason:** `SUPPORT_CONTACT_CLASS_V1` predicates used symbolic τ / ε without numeric values.  
**Policy:** fixed from existing physical scales — **not** tuned for pretty behaviour.

```text
ADDENDUM_AUTHORITY = YES
CENTRE_Z_AUTHORITY = YES
RING_CLASSIFICATION_ONLY = YES
ONE_PE_AUTHORITY = SES_DDA
NORMAL_PHYSICAL_EFFECTS_ACTIVE = NO
PROFILE_VERSION = RADIUS_AWARE_SUPPORT_POINTS_V1
  (= RECOMMENDED_NEXT_SLICE / Hybrid C⋆ / RADIUS_AWARE_SUPPORT_CONSTRAINED_HYBRID_CSTAR_V1)
```

---

## 1. Stencil (deterministic)

| Item | Value |
|---|---|
| Samples | Centre + 8 ring (`N_SAMPLES = 9`) |
| Ring angles | `angle_k = k · π/4` for `k = 0..7` |
| Normalized offsets (fixed table, no dict iteration) | `(1,0), (√½,√½), (0,1), (−√½,√½), (−1,0), (−√½,−√½), (0,−1), (√½,−√½)` |
| `SQRT_HALF` | `math.sqrt(0.5)` constant |
| WRAP | per sample via CSG / `wrap_coord` |
| Heading | **does not** rotate the circle |
| Object orientation | none invented |

Body `R = BODY_CONTACT_RADIUS` (0.575) via `physical_body_resource_object_contact.BODY_CONTACT_RADIUS`.  
Object `R = ensure_object_collision_radius(obj)` — **never** optical 0.45.

---

## 2. Per-sample vertical predicate

Centre-authoritative support plane: horizontal plane through `h_centre = h(centre_x, centre_y)`.

| Receipt | Predicate |
|---|---|
| `NOT_APPLICABLE_AIRBORNE` | entity not grounded (airborne / no support authority this tick) |
| `SUPPORTED` | grounded ∧ `|h_i − h_centre| ≤ ε_support` |
| `GAP_TOO_LARGE` | grounded ∧ `h_i < h_centre − ε_support` |
| `SURFACE_ABOVE_ALLOWED_CONTACT` | grounded ∧ `h_i > h_centre + ε_support` |

```text
ε_support = MICRORELIEF_THRESHOLD = 0.12
  (SES SUBGRID_MICRORELIEF_RAMP_V1 — existing physical height band; NOT BODY_CONTACT_RADIUS)
```

Centre sample is always `SUPPORTED` when grounded (by definition of the plane).  
Airborne: all samples `NOT_APPLICABLE_AIRBORNE`; class = `AIRBORNE_NO_SUPPORT`.

---

## 3. Classification fractions (`SUPPORT_CONTACT_CLASS_V1`)

Let `n_applicable` = count of samples that are not `NOT_APPLICABLE_AIRBORNE` (normally 9 when grounded).  
Let `n_supported` = count with receipt `SUPPORTED`.  
`fraction = n_supported / n_applicable` (0 if n_applicable=0 → airborne path).

```text
τ_full     = 1.0          # FULL requires every applicable sample SUPPORTED
τ_partial  = 5/9 ≈ 0.555… # majority band
τ_los      = 3/9 ≈ 0.333… # below → LOSS candidate
EDGE_SPREAD_THRESHOLD = ε_support = 0.12
  # max(h_i)−min(h_i) over applicable samples
```

| Class | Predicate (raw, before hysteresis) |
|---|---|
| `FULL_SUPPORT` | `fraction ≥ τ_full` |
| `PARTIAL_SUPPORT` | `τ_partial ≤ fraction < τ_full` **and** `spread ≤ EDGE_SPREAD_THRESHOLD` |
| `EDGE_OR_SPARSE_SUPPORT` | (`τ_los ≤ fraction < τ_partial`) **OR** (`τ_partial ≤ fraction < τ_full` **and** `spread > EDGE_SPREAD_THRESHOLD`) |
| `LOSS_OF_SUPPORT` | `fraction < τ_los` |
| `AIRBORNE_NO_SUPPORT` | entity airborne / not grounded |

---

## 4. Hysteresis (LOS only)

Enter LOSS harder than exit (anti-chatter at WRAP / patch edges):

```text
τ_los_enter = τ_los = 3/9     # enter LOSS when fraction < 3/9
τ_los_exit  = τ_partial = 5/9 # leave LOSS only when fraction ≥ 5/9
```

While sticky-in-LOSS (`prev_class == LOSS_OF_SUPPORT`):
- remain `LOSS_OF_SUPPORT` until `fraction ≥ τ_los_exit`
- then re-evaluate raw class with §3 (may become EDGE/PARTIAL/FULL)

Restore: load hysteresis flag/class; **no** transition event on restore.

---

## 5. Physical effects allowed under this addendum

- Class is a Phase C fact (researcher receipt).
- `LOSS_OF_SUPPORT` → clear `grounded` (airborne); no impact / no sound / no impulse.
- Traction eligibility: `grounded ∧ class ∉ {LOSS_OF_SUPPORT, AIRBORNE_NO_SUPPORT}`.
- Landing: centre FGG condition **and** class ≠ `LOSS_OF_SUPPORT` (post-classify revoke if needed).
- `N = m·g` unchanged; no coverage scale.

Forbidden (unchanged from architecture): ring-derived authoritative z, face-sweep, SES rewrite, normal PE, N(n_z), g_tangent, torque, pitch/roll, rolling, new PE, impact from reclass only.

---

## 6. Correspondence

```text
RADIUS_AWARE_SUPPORT_POINTS_V1
  ≡ RECOMMENDED_NEXT_SLICE G2B_RADIUS_AWARE_SUPPORT_POINTS_CONSTRAINED_HYBRID_CSTAR
  ≡ Hybrid C⋆
  ≡ user alias RADIUS_AWARE_SUPPORT_CONSTRAINED_HYBRID_CSTAR_V1 (name correspondence only)
```
