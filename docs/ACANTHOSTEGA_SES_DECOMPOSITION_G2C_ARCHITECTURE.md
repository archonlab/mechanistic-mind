# ACANTHOSTEGA — SES Decomposition G2C Architecture

**Date:** 2026-09-28 (Europe/Oslo, UTC+2)  
**Status:** ARCHITECTURE ONLY — no G2C implementation  
**Parent chain:** G2 arch → G1 CSG → G2A static traction → FOGF static twin → G2B Hybrid C⋆ (closed PASS) → **G2C (this doc)**  
**Prerequisite:** `G2B_CLOSURE = PASS` (`results/acanthostega_g2b_closure/`)  
**Hard constraints this audit:** no G2C code; no analytic-normal activation; no SES energy semantics change; no G2B physics change.

```text
G2C_ARCHITECTURE_COMPLETE = YES
G2C_IMPLEMENTATION_STARTED = NO
ONE_PE_AUTHORITY_CURRENT = SES_DDA
NORMAL_PHYSICAL_EFFECTS_ACTIVE = NO
TANGENT_GRAVITY_IMPLEMENTED = NO
SLOPE_SLIDING_IMPLEMENTED = NO
SCIENTIFIC_VALIDATION_RUN = NO
```

---

## B1. Current SES pipeline (files / symbols)

### Shared geometry / support height
| Role | File | Symbols |
|---|---|---|
| Continuous height + analytic n̂ (inactive forces) | `continuous_surface_geometry.py` | `sample_surface_geometry`, `surface_support_height` path, `note_authoritative_surface_mutation`, `NORMAL_PHYSICAL_EFFECTS_ACTIVE=False` |
| Discrete/continuous support oracle | `surface_elevation_support.py` | `surface_support_height`, `support_height_at_cell`, `support_z_for_entity` |
| Vertical integrate / grounded | `flat_ground_gravity.py` | `integrate_body_vertical`, `integrate_vertical_entity`, `support_z_for_entity` consumer |
| Radius classification (post-vertical) | `radius_aware_support_points.py` | `step_after_body_vertical`, `step_after_free_objects_vertical`, `eligible_for_ground_traction` |

### SES energy / topology gate (sole height-transition PE)
| Role | Symbols |
|---|---|
| Module | `mechanistic_mind/physical_system/surface_elevation_support.py` |
| Mechanism / profile | `MECHANISM_ID=surface_elevation_support`, `PROFILE_VERSION=SUBGRID_MICRORELIEF_RAMP_V1` |
| Path DDA | `centre_path_boundary_crossings`, `evaluate_path_transitions`, `classify_elevation_transition` |
| PE | `climb_work(mass,g,Δh) = m·g·Δh` debit from `mechanical_work_reservoir` on accept |
| Body gate | `commit_body_elevation_gate` |
| FREE object gate | `commit_free_object_elevation_gate` |
| Events | `MICRO_UPHILL`, `LARGE_UPHILL_BLOCKED`, `MICRO_DOWNHILL_INELASTIC`, `LARGE_DOWNHILL_SUPPORT_LOST` |
| Face sweep | `ENTITY_RADIUS_FACE_SWEEP = NOT_IMPLEMENTED` (centre-path only) |
| Mutation / occupants | `preflight_occupied_support_rise`, `apply_ground_lowered_to_occupants`, `occupied_entities_at_cell` |

### Entity paths
| Entity | SES role | Notes |
|---|---|---|
| **Body (single)** | `runtime` horizontal CoM proposal → `commit_body_elevation_gate` → later `integrate_body_vertical` → G2B classify | Reservoir debit on MICRO_UPHILL accept |
| **Experimenter body** | Same physics gates as ordinary body when spawned; cognition OFF | No separate SES fork |
| **FREE_STATIC / FREE_MOVING** | `commit_free_object_elevation_gate` on xy proposal; FGG vertical; FOGF/FOST; G2B object classify | Object PE: block/dissipate/LOS; no body reservoir |
| **HELD** | No independent SES gate / G2B classify (`skip` while held) | Follows holder; EHL mass coupling elsewhere |
| **Single-agent** | Above body path in `PhysicalSystemRuntime` | |
| **TwoAgent** | Per-slot body gates + shared world SES/FGG/G2B; entity_id keyed; order-independent | Same SES module; no `id()` |

### Tick order (preserved)
```text
horizontal CoM (+ BNLT/static traction + SES elevation gate)
  → vertical FGG (centre support_z)
  → G2B radius classify (class / LOSS→airborne; no PE)
  → contacts / acoustics
```

---

## B2. Energy ledger table

| Channel | Quantity | Authority today | Debit / effect | Double-count risk if G2C careless |
|---|---|---|---|---|
| SES MICRO_UPHILL | `W = m·g·Δh` | **SES_DDA** | Debit `mechanical_work_reservoir` or BLOCK | Dual continuous PE |
| SES LARGE_UPHILL | topology block | SES_DDA | Revert pose | — |
| SES MICRO_DOWNHILL | inelastic dissipate | SES_DDA | Land on new support | Overlap with future g_t friction work |
| SES LARGE_DOWNHILL | LOS → airborne | SES_DDA | Clear grounded; no snap | Overlap with G2B LOSS (both PE-safe) |
| FGG vertical clamp | kill penetrating vz | FGG | Inelastic support | Not PE climb |
| BNLT / FOGF kinetic | friction work | BNLT/FOGF | Horizontal | Independent of height PE |
| G2A / FOST static | impulse limit | static traction | Blocks MOVE creep | Force-side only |
| G2B class / LOSS | none | classification | Airborne + traction gate | **Must stay PE-free** |
| Action/motor work | ΔKE / effector | `action_work` | Reservoir | Orthogonal |
| Analytic normal / g_tangent | — | **OFF** | — | Forbidden until PE split |

**ONE_PE_AUTHORITY_CURRENT = SES_DDA.**

---

## B3. Smooth slope vs bilinear reality (10 questions)

| # | Question | Answer |
|---|---|---|
| Q1 | Does bilinear `h(x,y)` equal a smooth manifold? | **No.** C⁰ height; ∇h discontinuous at cell edges. |
| Q2 | Can centre-path Δh represent continuous slope work? | **Only approximately** along cell-centre DDA; misses face-crossing under radius. |
| Q3 | Is SES MICRO_UPHILL isomorphic to ∫ m g · dr along slope? | **No.** Discrete cell-boundary Δh charges, not path integral on n̂. |
| Q4 | Does inactive analytic n̂ already define slope PE? | **No.** Geometry only; `NORMAL_PHYSICAL_EFFECTS_ACTIVE=NO`. |
| Q5 | Would enabling g_tangent without SES split double-count? | **Yes** if SES MICRO_UPHILL kept. |
| Q6 | Would removing SES PE before continuous PE open free lift/climb? | **Yes.** |
| Q7 | Does G2B ring class change PE? | **No** (by contract). |
| Q8 | Can aggregate support_z (max/mean) coexist with centre SES Δh? | **No** without PE rewrite — free lift / mismatch. |
| Q9 | Is face-sweep required for faithful radius transitions? | **Yes** for PE-accurate multi-cell crossing; still NOT_IMPLEMENTED. |
| Q10 | Is bilinear enough for first continuous-PE slice after split? | **Yes with clamps** (n_z floor, cliff class, radius samples) — not for full gait/pitch. |

---

## B4. Transition taxonomy (names not forced)

Design classes for a future split (labels illustrative):

| Class | Intent | Likely owner after G2C |
|---|---|---|
| `SMOOTH_PATCH_TRAVERSAL` | Intra-patch / gentle ∇h motion | Continuous PE / later g_t (not today) |
| `MICRORELIEF_STEP` | ‖Δh‖ ≤ microrelief threshold across cell boundary | SES KEEP (or migrate PE later) |
| `LEDGE_BLOCK` | Large uphill discontinuity | SES KEEP (topology gate) |
| `SUPPORT_DROP_LOS` | Large downhill / withdrawn support | SES KEEP + G2B LOSS alignment |
| `OCCUPANT_SUPPORT_RISE` | Experimenter/mutation raises floor under grounded | SES `preflight_occupied_support_rise` KEEP |
| `RADIUS_PARTIAL_CONTACT` | Ring fraction diagnostics | G2B KEEP (non-PE) |
| `CLIFF_NZ_CUTOFF` | Future steep n_z | Post-G2D |

Taxonomy is a **classifier contract**, not an implementation mandate. Selected umbrella for docs:

```text
TRANSITION_TAXONOMY_SELECTED = SES_TOPOLOGY_VS_CONTINUOUS_PE_SPLIT_V1
```

---

## B5. Alternatives A–D (+ better)

| ID | Idea | Pros | Cons | Fit |
|---|---|---|---|---|
| **A** | Keep SES full PE forever; never continuous slope PE | Safest PE | Cannot answer G2 central slope question | Interim only |
| **B** | Replace SES PE with continuous PE in one cut | Clean end-state | High preset/regression risk | **Reject as first slice** |
| **C** | Hybrid: SES keeps steps/ledges/LOS/mutation; continuous PE owns smooth traversal later | Matches G2 arch “D then C” | Needs stable classifier | **Strategic endgame** |
| **D** | Delay g_tangent; decompose SES contract first; keep PE=SES until continuous owner ready | Minimal proveable-compat | No slope sliding yet | **SELECTED first G2C slice** |
| **E+** (better minimal) | **G2C_CONTRACT_ONLY**: documentation + receipt flags + frozen tests naming KEEP/MOVE/DEPRECATE **without** changing runtime PE | Zero physics drift; unblocks G2D planning | No new behaviour | **RECOMMENDED NEXT** |

**Prefer minimal proveable-compat slice = E+ / D-contract (architecture + test hooks), not B.**

---

## B6. Responsibility KEEP / MOVE / DEPRECATE map

| Responsibility | Verdict | Notes |
|---|---|---|
| Centre-path DDA topology crossings | **KEEP** | Until face-sweep designed |
| MICRO_UPHILL m·g·Δh debit | **KEEP** (until continuous PE owns smooth class) | Still ONE_PE |
| LARGE_UPHILL block | **KEEP** | Topology |
| MICRO_DOWNHILL inelastic | **KEEP** | May later MOVE dissipate share to friction |
| LARGE_DOWNHILL → airborne | **KEEP** | Align with G2B LOSS |
| `preflight_occupied_support_rise` | **KEEP** | Mutation free-PE reject |
| `apply_ground_lowered_to_occupants` | **KEEP** | |
| `climb_work` helper | **KEEP** | Symbol may later serve continuous PE |
| `ENTITY_RADIUS_FACE_SWEEP` | **DEPRECATE-as-flag / MOVE-to-future** | Remains NOT_IMPLEMENTED until post-G2C design |
| Centre `support_z` authority | **KEEP** through G2C contract | Aggregate support_z = later coupled slice |
| G2B ring classification | **KEEP** | Non-PE |
| Analytic n̂ force use | **DEPRECATE until G2D+** | Stay inactive |
| Dual PE (SES + g_t) | **DEPRECATE forever** | Forbidden |

---

## B7. PE authority migration states (design only)

```text
S0_CURRENT          ONE_PE = SES_DDA; NORMAL=NO; g_t=NO          ← now (post-G2B)
S1_CONTRACT         G2C docs+tests name KEEP/MOVE; runtime PE unchanged
S2_CLASSIFIER       Transition classifier emits SMOOTH vs STEP/LEDGE (still SES pays)
S3_CONTINUOUS_PE    SMOOTH class paid by continuous PE; SES PE disabled for that class only
S4_FACE_SWEEP_OPT   Optional radius face-sweep under same ONE_PE rule
S5_G2E_TANGENT      g_tangent allowed only when SMOOTH PE owner ≠ SES debit
```

Illegal transitions: `S0→S3` skipping contract; `S3` with SES MICRO still debiting same Δh; enabling g_t in S0–S2.

---

## B8. Future continuous PE + tangent gravity (architecture)

1. Continuous PE = path work against gravity along support manifold proxy: ideally `ΔPE = m g Δh_path` with `h` from CSG, **xor** ∫ (−m g ẑ)·v dt — pick one ledger.  
2. `g_tangent = g · (I − n̂n̂ᵀ) · (−ẑ)` only after static traction (done) + radius class (done) + PE split (G2C).  
3. Tick order remains: horizontal (forces + PE gate) → vertical → G2B class → contacts.  
4. Reservoir: same `mechanical_work_reservoir` for body; never invent a second height wallet.  
5. Objects: continuous PE must define object ledger (today FREE gate has no body reservoir) before object slope slide.

**Not in G2C implementation.**

---

## B9. Discrete steps / ledges gate design

- **Keep** SES LARGE_UPHILL / LARGE_DOWNHILL as discrete topology gates.  
- Classifier inputs: centre-path Δh, optional ring max gap (G2B diagnostics), future n_z.  
- Thresholds: remain tied to `MICRORELIEF_THRESHOLD` (0.12) unless a dedicated G2C numeric addendum is written **before** code.  
- Mutation support-rise reject stays SES.  
- G2B LOSS may clear grounded without paying PE (already).

---

## B10. Radius-aware future role vs G2B

| Concern | G2B (done) | Post-G2C |
|---|---|---|
| Ring samples | Classification / LOS | May feed face-sweep / aggregate policies |
| Authoritative support_z | **Centre** | Change only after PE split |
| Face-sweep PE | Forbidden | Allowed only under new ONE_PE owner |
| N(n_z) | Forbidden | G2D after radius confidence |
| Optical R | Never | Never |

```text
RADIUS_FACE_SWEEP_REQUIRED_AT = AFTER_G2C_CONTRACT_BEFORE_RADIUS_PE_OR_AGGREGATE_SUPPORT_Z
```

---

## B11. Dynamic mutations vs traversal

Already: column deltas atomic; CSG `note_authoritative_surface_mutation` bumps generation; G2B `note_surface_generation`; SES rejects free PE under occupants; G2B reclassifies without lift.

G2C must **KEEP** mutation free-PE reject under whatever PE owner is active. Traversal classifier must not treat experimenter scars as “smooth” without ledge rules.

---

## B12. Traction interaction

- G2A/FOST/BNLT remain force-side; gated by grounded ∧ G2B class ≠ LOSS/AIRBORNE.  
- After PE split: static cone still required before g_t (else creep).  
- Do not scale N by ring coverage in G2C.  
- Affinity cell remains centre/floor-cell unless a later footprint affinity slice.

---

## B13. G2D `N = m·g·n_z` before PE switch?

```text
G2D_BEFORE_PE_SWITCH = WITH_CONSTRAINTS
```

**Constraints:**
1. Allowed only as **diagnostic / Observer** or tightly clamped research flag **without** changing friction capacity in presets — **or**  
2. If N(n_z) affects traction: only after G2C classifier exists **and** SES still owns height PE (Variant D envelope) **and** n_z floor + radius class LOSS rules active.  
3. **Not** allowed to justify removing SES PE.  
4. Full trust in N(n_z) for slope forces still prefers post-face-sweep / aggregate policy.

Practical recommendation: **G2C contract → optional constrained G2D N(n_z) under SES PE → continuous PE → g_t**.

---

## B14. Aggregate normal options (no code)

| Option | Description | When |
|---|---|---|
| Centre n̂ only | Current CSG sample at CoM | Now (inactive forces) |
| Ring mean n̂ | Average unit normals | Diagnostic; G2D research |
| Area-weighted | Weights by supported samples | After G2B class trusted |
| Support-plane fit | Least-squares plane to supported ring | Needs PE split before driving z |
| Max-penalty | Reject if any sample cliff | Safety classifier |

```text
AGGREGATE_NORMAL_REQUIRED_AT = G2D_OR_LATER_FOR_FORCES__DIAGNOSTIC_OK_NOW
```

---

## B15. Contacts / acoustics

- Contacts stay xy radii + vertical interval filters (FGG).  
- G2B samples must not enter spatial index / contact acoustics.  
- LOSS / support refresh: no impact sound (proven).  
- Future slope slip acoustics = separate slice; not G2C.

---

## B16. Snapshot compatibility

- SES / CSG / G2B already omit dense rasters; missing keys = OFF.  
- G2C contract must add **optional** classifier fields with default-off restore.  
- Restore must not replay MICRO_UPHILL debits, LOSS events, or landings (G2B proven; SES must keep same discipline).  
- Tiktaalik / prior presets fingerprints frozen.

---

## B17. Cognition / prospective

Prospective composition / scenario competition today do **not** run a full SES+FGG+CSG+G2B shadow fork. No cheap continuous-PE prospective exists.

```text
PROSPECTIVE_G2C_SUPPORT = UNKNOWN_NO_FULL_SES_SHADOW__APPROX_LOCOMOTION_ONLY
```

Future rule: prospective must reuse the **same** ONE_PE flags; never a second SES.

---

## B18. Observer / Analyzer

Researcher-only: SES class, Δh, climb debit, G2B support_class, CSG h/n̂, future continuous-PE ledger flags.  
Banner must state PE authority explicitly after any split.  
FORBIDDEN_TOKENS: no agent-facing SLOPE/CLIFF/UPHILL/FULL_SUPPORT semantics.

---

## B19. Performance

- Centre DDA: O(crossings) per move (cheap).  
- G2B: 9× CSG samples / entity / tick (already).  
- Face-sweep: would be O(radius cells × path) — defer.  
- Continuous PE: prefer incremental Δh from CSG centres/patches; avoid dense raster.  
- Bound: no full-map rebuild on mutation (already).

---

## B20. Dependency verdict order

```text
G1 CSG                          DONE
G2A body static                 DONE
FOGF static twin                DONE
G2B radius Hybrid C⋆            DONE / CLOSURE PASS
G2C SES decomposition CONTRACT  ← NEXT (this arch; implement contract/tests only)
[optional] constrained G2D N(n_z) under SES PE (WITH_CONSTRAINTS)
G2C runtime classifier / PE migration states S2–S3
RADIUS face-sweep / aggregate support_z (only under new PE)
G2E g_tangent / slope sliding
```

```text
SES_DECOMPOSITION_REQUIRED = YES
G2C_REQUIRES_ONE_OR_TWO_SLICES = TWO
  (1) CONTRACT + frozen KEEP/MOVE tests
  (2) runtime classifier / PE migration for SMOOTH vs STEP
```

---

## B21. Recommended next slice (DO NOT implement)

| Field | Value |
|---|---|
| Slice | `G2C_SES_DECOMPOSITION_CONTRACT` |
| Preset | `ACANTHOSTEGA_PHASE_C_SES_DECOMPOSITION_CONTRACT` (default OFF) |
| Parent | `ACANTHOSTEGA_PHASE_C_RADIUS_AWARE_SUPPORT` |
| Mechanism | `ses_decomposition_contract` (flags/receipts only; **no PE law change**) |
| Profile | `SES_TOPOLOGY_VS_CONTINUOUS_PE_SPLIT_V1` |
| Implements | KEEP/MOVE/DEPRECATE map in capability flags; Analyzer section; tests that SES PE unchanged + taxonomy labels stable |
| Excludes | face-sweep, aggregate support_z, N(n_z) forces, g_tangent, slope sliding, SES energy rewrite, G2B physics edits |
| Success | prior presets/Tiktaalik FP unchanged; ONE_PE still SES_DDA; NORMAL=NO |

```text
RECOMMENDED_NEXT_SLICE = G2C_SES_DECOMPOSITION_CONTRACT
```

---

## Closing status block

```text
FRESHNESS_CHECK = PASS
G2B_REGRESSION_CLOSURE = PASS
G2B_PHYSICS_CHANGED = NO
G2B_CLOSURE = PASS

G2C_ARCHITECTURE_COMPLETE = YES
G2C_IMPLEMENTATION_STARTED = NO
TRANSITION_TAXONOMY_SELECTED = SES_TOPOLOGY_VS_CONTINUOUS_PE_SPLIT_V1
ONE_PE_AUTHORITY_CURRENT = SES_DDA
SES_DECOMPOSITION_REQUIRED = YES
G2C_REQUIRES_ONE_OR_TWO_SLICES = TWO
G2D_BEFORE_PE_SWITCH = WITH_CONSTRAINTS
RADIUS_FACE_SWEEP_REQUIRED_AT = AFTER_G2C_CONTRACT_BEFORE_RADIUS_PE_OR_AGGREGATE_SUPPORT_Z
AGGREGATE_NORMAL_REQUIRED_AT = G2D_OR_LATER_FOR_FORCES__DIAGNOSTIC_OK_NOW
PROSPECTIVE_G2C_SUPPORT = UNKNOWN_NO_FULL_SES_SHADOW__APPROX_LOCOMOTION_ONLY
RECOMMENDED_NEXT_SLICE = G2C_SES_DECOMPOSITION_CONTRACT

NORMAL_PHYSICAL_EFFECTS_ACTIVE = NO
TANGENT_GRAVITY_IMPLEMENTED = NO
SLOPE_SLIDING_IMPLEMENTED = NO
SCIENTIFIC_VALIDATION_RUN = NO
```

**HEAD** `5d0f14cd7968b4d5b190796a2494d348a0e10f48` · **branch** `main` · **pwd** `<repository-root>`  
No git commit/push. No G2C code landed.
