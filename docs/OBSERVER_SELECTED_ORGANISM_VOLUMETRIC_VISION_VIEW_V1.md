# OBSERVER_SELECTED_ORGANISM_VOLUMETRIC_VISION_VIEW_V1

**Schema:** `SELECTED_ORGANISM_VOLUMETRIC_VISION_VIEW_V1`  
**Capability:** `selected_organism_volumetric_vision_view`  
**Profile:** `VW6_PHYSICAL_GEOMETRY_TO_ORGANISM_VISUAL_INPUT_AUDIT_V1`  
**Authority:** `RESEARCHER_VISUALIZATION_OVER_EXISTING_VW6_PERCEPTION`

## Goal

Researcher visualization of the exact VW6 organism visual sampling path in the left VISION workspace. Not a camera, not renderer pixels, not mind reading.

## Causal path visualized

physical XYZ → selected organism eye pose → horizontal/vertical relative geometry → VW1 occupancy LOS → receptor/phenotype → cognition-accessible visual values

## Capture seam

Scientific `agent_observation()` arms a capture context; `sample_near_field` (after VW6 annotate + assemble) appends at most one researcher trace per agent perception tick into a bounded FIFO (capacity 128). Observer polling does not arm the context and does not duplicate traces.

## UI

Left VISION dock modes (default RECEPTOR):

- **RECEPTOR VIEW** — existing SENSOR SPACE / FPV
- **VOLUMETRIC VIEW** — azimuth × elevation diagnostic plot from exact VW6 samples
- **CAUSAL SPLIT** — geometry + cognition-accessible values + expandable provenance

## Preservation

No change to VW6 numerics, cognition visual schema, public selector (Tiktaalik Beta 3.1 + Acanthostega Beta 4.0), VW1–VW7 physics, Tiktaalik, or HEARING keep-alive.

## Next seam

`FIRST_HABITABLE_VOLUMETRIC_RUN_V1` — not begun.
