# ACANTHOSTEGA · ORGANISM RECEPTOR GROUNDED 3D FPV V1

## Identity
- Schema: `ORGANISM_RECEPTOR_GROUNDED_3D_FPV_V1`
- Capability: `organism_receptor_grounded_3d_fpv`
- Profile: `EXACT_O4_RECEPTOR_CONTRIBUTION_FIRST_PERSON_RECONSTRUCTION_V1`
- Authority: `RESEARCHER_DISPLAY_OVER_AUTHORITATIVE_O4_RECEPTION`
- Classification: `BETA4_REQUIRED_OBSERVABILITY_NOT_NEW_SENSOR`

## Verdict
**A. FPV_PASS_EXACT_RECEPTOR_GROUNDED_RECONSTRUCTION**

## Design
1. Exact O4 accepted contributions (azimuth/elevation/distance/bands) → RECEPTOR FPV.
2. Phenotype/clip/6→3 survivors → COGNITION FPV (coarser; no discarded detail restored).
3. `latest_exact_trace` per agent survives bounded history eviction.
4. Missing trace ≠ darkness; true zero exact trace may be dark with label.
5. Never VW7 pixels / frontend raycast / light recompute.

## Next
P6 Analyzer optimization → P7 release equivalence gate.
