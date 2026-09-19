# LOCAL SENSORY HORIZON CONTRACT V01

**Status:** architecture / research contract only.  
**Experiment family:** LOCAL_PHYSICAL_COHERENCE_01  
**Does NOT implement:** semantic vision, eyes, FOV, day/night, illumination, visual memory.

## Spatial scale

Initial exteroceptive spatial horizon = **Moore neighborhood radius 1 cell**.

```
NW  N  NE
 W [X] E
SW  S  SE
```

The 8 immediately adjacent cells define the maximum initial **LOCAL SPATIAL HORIZON**.

## Physical scale hierarchy (intended)

| Role | Meaning |
|------|---------|
| LOCAL SENSORY HORIZON | ≈ 1 cell |
| ACTIVE MOVE | primary mechanism for deliberately changing local spatial context |
| ORDINARY WAIT | local drift / deformation / rotation / inertial continuation |
| RARE STRONG ENVIRONMENTAL TRANSPORT | allowed only under physically exceptional conditions — not normal background climate |

## Own-cell vs neighbor-cell

### OWN CELL / BODY-LOCAL

Physical quantities directly acting on or through the body may be sensed through **existing** physical channels where already implemented. Do not remove legitimate body-local signals.

### NEIGHBOR CELLS

Future exteroception must receive only **physically observable** signals that can propagate from those cells.

**Never** expose direct ground-truth properties to cognition, including:

- terrain potential / drag / gradient
- resource A/B ground truth
- ambient Fx/Fy
- temperature ground truth
- resource suitability
- labels: obstacle / food / safe / danger

### Intended future chain (not implemented here)

```
physical surface/object
  → observable physical signal
  → distance attenuation
  → orientation / field of view
  → sensor sensitivity
  → sensory fragment
  → cognition
```

## PASSIVE_LOCALITY principle

MOVE/WAIT path ratio is necessary but not sufficient. Ordinary environmental forces should primarily perturb a **resting** organism within its local neighborhood. Ordinary WAIT should not routinely replace the organism's entire 8-neighbor context.

`LOCAL_CONTEXT_REPLACEMENT` is a **geometric Observer metric** (not cognition): how rapidly body translation replaces the 3×3 neighborhood on the torus.

## Next experiments

- `ILLUMINATION_CYCLE_01`
- `PHYSICAL_PERCEPTION_01`
