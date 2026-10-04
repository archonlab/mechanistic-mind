# ACANTHOSTEGA — EXPOSED SURFACE OPTICAL INTERACTION AUTHORITY V1 (O2)

**Status:** implemented (behaviorally dormant without light consumer)  
**Parent:** O1 material optical profile + VW1 occupancy  
**Public model:** cumulative Acanthostega Beta 4.0 metadata; selector unchanged (2 entries)

## Purpose
Deterministic read-only derivation:

```
VW1 occupied intervals → occupied/free boundary → exposed facet
  → centre + outward normal + area → composition → O1 profile link
```

## Module
`mechanistic_mind/physical_system/exposed_surface_optical_interaction_authority.py`

## Queries
- `query_exposed_facets_global`
- `query_exposed_facets_region`
- `query_exposed_facets_candidates`
- Cache keyed by VW1 digest + PSC geology token + O1 registry version + shape
- Invalidated on VW1 column set/clear

## Non-goals (this slice)
Light sources/transport, shading, organism reception, VW7-as-authority, dense voxels, object/body meshes, cognition exposure.

## Next seam
**O3 — ABSTRACT_SPECTRAL_LIGHT_SOURCE_AND_DIRECT_TRANSPORT_V1**
