# SELECTED_ORGANISM_AUDITORY_BOUNDARY_RECEIPT_V1

Observational same-tick receipt freezing A5 `osc_l/r` from the cognition-bound observation.

- Schema: `SELECTED_ORGANISM_AUDITORY_BOUNDARY_RECEIPT_V1`
- Profile: `ORGANISM_AUDITORY_BOUNDARY_A5_V1`
- Boundary: `A5_OSC_LR_ACCESSIBLE_OBSERVATION_PRE_COGNITION`
- Capture seam: `PhysicalSystemRuntime.begin_tick` after `last_agent_observation = obs`
- History capacity: **128** FIFO total
- Does not re-run LPS/phenotype; does not alter observation/cognition
- Researcher metadata private; osc numerics remain legitimate agent input
