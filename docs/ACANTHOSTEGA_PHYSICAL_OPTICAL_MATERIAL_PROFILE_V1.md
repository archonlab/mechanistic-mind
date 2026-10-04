# ACANTHOSTEGA — PHYSICAL OPTICAL MATERIAL PROFILE V1 (O1)

**Status:** implemented (behaviorally dormant without light consumer)  
**Parent architecture:** `docs/ACANTHOSTEGA_PHYSICAL_OPTICAL_MATERIAL_PROPERTIES_AND_SENSORY_TIME_ALIGNMENT_ARCHITECTURE.md`  
**Public model:** cumulative Acanthostega Beta 4.0 (Tiktaalik unchanged; selector still two entries)

## What O1 is
Versioned anonymous spectral reflectance attached to material **components**, mixed by conserved quantities:

`R_mix[b] = Σ(q_i × R_i[b]) / Σ(q_i)` for `optical_band_0…5`.

Authority: `PHYSICAL_MATERIAL_PROPERTY_NON_SI_NO_LIGHT_TRANSPORT`.

## What O1 is not
Not Observer RGB, not `optical_response`, not `illumination_intensity`, not light sources/transport, not organism vision, not SI radiometry, not exposed-surface shading (O2), not receptor integration (O4).

## Module
`mechanistic_mind/physical_system/physical_optical_material_profile.py`

## Integration
- Enabled in `acanthostega_beta4_config()` via `set_physical_optical_material_profile(cfg, True)`
- Config field on `PhysicalSystemConfig`; snapshot/restore carry registry version
- Mechanism map + catalog; researcher serialize on ROs, deposits, VW1 column inspector
- Analyzer: `material_summary.physical_optical_material_profile` coverage (no “organism saw” claim)
- Cognition: FORBIDDEN_TOKENS extended; exo numerics unchanged

## Component limitation
`component_0` / `component_a` / `component_b` share neutral R=`0.5×6` because optical distinctions are not scientifically established.

## Next seam
**O2 — EXPOSED_SURFACE_OPTICAL_INTERACTION_AUTHORITY_V1**
