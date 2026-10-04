# ACANTHOSTEGA_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE_ARCHITECTURE

**Architecture audit only.** `IMPLEMENTATION_STARTED = NO`.  
Does **not** implement contact fact, impulse, rebound, sound, presets, runtime, tests, or frontend.

## Freshness

| Field | Value |
|-------|-------|
| cwd | `<repository-root>` |
| branch | `main` |
| HEAD | `5d0f14cd7968b4d5b190796a2494d348a0e10f48` |
| dirty tree | ~293 paths preserved (no reset/stash/commit/push) |
| live Observer / live run | not mutated |
| parent tip | `ACANTHOSTEGA_BETA4_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT` |

Code is authoritative over older Free-Space Z docs where they predate V1A rest-gate closure. V1A rest gate and clamp classification are verified present in current `flat_ground_gravity.py` / `free_space_state_and_pe_authority_contract.py`.

## Parent V1A verification

| Claim | Status |
|-------|--------|
| Support-state authority + PE mutual exclusion | YES |
| Supported-rest gravity skip | YES |
| FGG unsupported semi-implicit z | YES |
| Body / experimenter / FREE objects | YES |
| Support-loss / release / newborn / excavation stamps | YES |
| Current inelastic clamp classified | YES (`CURRENT_INELASTIC_CLAMP_DISSIPATION`) |
| Landing contact fact / compliance impulse / rebound / vertical sound | NO |

## Executive verdict

```text
VERDICT = A_COMBINED_CONTACT_RESPONSE_WITH_INTERNAL_PLAN_FACT_COMMIT
BLOCKER = NONE
RECOMMENDED_NEXT_SLICE = VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE_V1
```

**Why not fact-only first:** receipts expose `z_before`/`vz_before` and post-clamp state, but **not** authoritative pre-clamp `z1`/`vz1`/TOI/penetration. A researcher “contact fact” stamped after clamp would be misleading. The first shippable tip must **own** plan→fact→response→commit and **replace** the clamp when ON.

**Why not three slices:** V1 response is inelastic (e=0); splitting correction from impulse adds packaging without physics.

**Why acoustics separate:** persistent support must stay silent; emission needs thresholds and LPS wiring after a trustworthy dissipation ledger exists.

## Current landing (Q1–Q2)

Today, unsupported entities integrate with FGG semi-implicit Euler against `support_z=h(x,y)`. Intersection uses post-step compare. Clamp mutates **`z` and `vz` inside `integrate_vertical_entity`** (≈ L620–628): `z1=support_z`, `vz1=0`, then entity fields. `landed` is a boolean inside `VERTICAL_PHYSICAL_STEP` / Free-Space `TERRAIN_INTERSECT` — **not** a contact episode. No sound.

Evidence: `results/.../CURRENT_LANDING_PATH.md`.

## Geometry / TOI (Q8–Q9)

```text
CONTACT_GEOMETRY = Z_SEGMENT_AT_COMMITTED_XY
CONTACT_POINT = (x, y, support_z) at base/feet
TOI = linear z0→z1 vs support_z
TUNNELLING = max_vz + post-step clamp
WRAP = existing xy wrap before height sample
OPTICAL_RADIUS = forbidden
SUBSTEPS = not required for V1
```

Horizontal ledge tunnelling during FOK/SES remains an explicit V1 limitation (face sweep ≠ vertical landing TOI).

## Contact normal (Q10)

```text
LANDING_NORMAL_AUTHORITY = VERTICAL_PLUS_Z_V1
ANALYTIC_CSG_NORMAL = DIAGNOSTIC_ONLY
```

Does not activate continuous-normal physics or change grounded locomotion / SES PE.

## Episode model (Q6–Q7)

```text
CONTACT_EPISODE_KEY = "{entity_kind}:{entity_id}|terrain"
PHASES = BEGIN | PERSIST | END
SUPPORTED ⟂ VERTICAL_TERRAIN_CONTACT  (related, separate)
Supported rest = PERSIST (no repeated BEGIN; no impulse; no sound)
```

Cell not in key. Re-contact → new episode id. Restore does not replay BEGIN.

## Entity scope (Q23)

Shared kernel: ordinary bodies, both TwoAgent bodies, experimenter, FREE_STATIC/FREE_MOVING, released and newborns after eligibility.  
`HELD_OBJECT_INDEPENDENT_LANDING = NO`. Shared FREE objects once per world tick.

## Mass / compliance / restitution (Q11–Q15)

| Item | Decision |
|------|----------|
| Terrain mass | infinite / immovable |
| Body mass | `config.body.mass` |
| Held load | include when EHL ON (ledger honesty); else body-only |
| Object mass | `ResourceObject.mass` |
| Invalid mass | skip response + anomaly |
| Terrain compliance | **none** — do not fabricate |
| Body compliance | **none** |
| Object compliance | material when passive props ON (later) |
| Restitution | **e=0 V1** |
| Initial response | inelastic infinite-mass normal |
| Rebound | defer |

## Response / correction (Q16–Q17)

Formalize option A:

- Approach: `vz_rel_n < −ε` toward terrain (+Z normal).
- Correct z to contact (`max_correction` = penetration this step; hard cap = `|max_vz|·dt` scale).
- Set vz=0; one response per entity/tick; dedupe by episode+tick.
- No second vertical integration; no horizontal velocity change from landing.
- KE never created by correction; no agent credit; no global conservation claim.

## Support / traction (Q19–Q22)

After commit at rest: `grounded=True`, V1A `SUPPORTED`, next tick rest-gate skips gravity, ground traction eligible via `grounded`.  
Support loss / excavation: existing V1A stamps; END episode without fabricating impact. Re-contact → new BEGIN.

## Energy / acoustics (Q18)

Expose KE before/after and dissipated energy for later `VERTICAL_IMPACT_ACOUSTIC_EMISSION_V1`. Persistent PERSIST silent. Sound not in this slice.

## Tick / clamp migration (Q3–Q5)

```text
PRE_CLAMP_EVIDENCE_AVAILABLE = PARTIAL
PLAN_FACT_RESPONSE_COMMIT_REFACTOR_REQUIRED = YES  (internal to first tip)
CONTACT_AND_RESPONSE_ONE_SLICE_SAFE = YES
OLD_CLAMP_AND_NEW_RESPONSE_BOTH_RUN = NO
```

Parent V1A retains clamp. Child replaces clamp when ON.

## Multi-contact / spatial (Q24–Q25)

Terrain vertical first; existing XY entity chains keep order; coupled 3D **NOT RESOLVED**.  
2D index remains; one spatial reconcile sufficient; entity/entity z narrow-phase still V2 debt / limitation.

## Snapshot / cognition / Observer (Q26–Q28, Q31)

See `SNAPSHOT_COGNITION_OBSERVER_CONTRACT.md`.  
`PROSPECTIVE_VERTICAL_LANDING_SUPPORT = NOT_ESTABLISHED`.  
Pit/elevation/fall visualization **after** landing acoustics + release/excavation integration.

## Performance

Bound: height queries (1–few per falling entity/tick), episode map, response dedupe ring, history cap aligned with nearby mechanisms. Explicit anomaly on query-cap exceed. TwoAgent must not double-process free objects.

## Slice graph

```text
V1A (done)
  → VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE_V1   ← next implement
  → VERTICAL_IMPACT_ACOUSTIC_EMISSION_V1
  → RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION_V1
  → OBSERVER_ELEVATION_EXCAVATION_FREE_SPACE_VISUALIZATION
```

Optional later: restitution/rebound; entity/entity z; Analyzer progress bar (separate UI debt).

## Required answers (compact)

1. Landing today = FGG integrate + inelastic clamp + classify; no episode/sound.  
2. Clamp mutates z/vz in `integrate_vertical_entity` before entity assign.  
3. Pre-clamp geometry only partially reconstructible — not enough for fact-only tip.  
4. Yes — plan/fact/response/commit required inside first tip.  
5. Fact+response as **one** first preset; sound separate.  
6. `{entity_kind}:{entity_id}|terrain`.  
7. Supported rest = PERSIST, not repeated BEGIN.  
8. Linear TOI on z-segment at committed xy.  
9. max_vz + post-step clamp; horizontal ledge tunnelling limited.  
10. Vertical +Z.  
11. Body config / object mass; terrain ∞.  
12. Yes when EHL ON (recommended).  
13. None.  
14. e=0.  
15. Inelastic.  
16. Snap z to support_z; penetration = overshoot.  
17. Correction cannot increase KE; ledger max(0,ΔKE).  
18. Dissipated vertical KE (+classified overshoot) for later acoustics.  
19. Post-response rest at support.  
20. Next tick via V1A rest gate.  
21. When grounded/SUPPORTED after commit.  
22. V1A LOS stamps + episode END; re-contact new BEGIN.  
23. Shared body kernel; free objects once; experimenter=body.  
24. Yes (2D reconcile).  
25. Yes for V1 with explicit z-separation limitation.  
26. Episodes, dedupe, last response, V1A state, config.  
27. All landing researcher tokens/fields.  
28. NOT_ESTABLISHED.  
29. Combined CONTACT_RESPONSE_V1.  
30. Acoustics → release/excavation harden → Observer pit/fall viz.  
31. After acoustics and release/excavation integration.

## Evidence pack

`results/acanthostega_vertical_terrain_landing_architecture/`

## Preservation

No runtime/preset/registry/serialize/test/frontend/`web_dist` edits in this task.  
`FREE_SPACE_V1A_CHANGED = NO`, Tiktaalik/Phase C/Beta4 untouched, live run untouched.
