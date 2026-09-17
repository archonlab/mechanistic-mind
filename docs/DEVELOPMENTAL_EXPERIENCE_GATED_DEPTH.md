# Experience-Gated Cognitive Depth (Update 2)

## Audit of Update 1

- Implemented: global `developmental_maturity` + `gate_factor` with tick bounds (min/target/max).
- Insertion: `DevelopmentalGateModule` (MEMORY), sensorimotor retrieve/proposals, organism prediction history scope, optional compression budget.
- Maturity was mixed: structural experience + time ceiling; **global**, not contextual.
- Retrieval bound via `retrieval_recent_limit` and learned-proposal caps.
- Conditions: DISABLED, DEVELOPMENTAL, ADULT_FROM_TICK_0.

## Generalization (this update)

- Preserve global metrics for observation/experiments.
- Add **local experience maturity** from bounded evidence relevant to the current cue bucket (plus weaker related-bucket transfer).
- Effective cognitive accessibility = min(global_ceiling, local_maturity) under EXPERIENCE_GATED/DEVELOPMENTAL.
- After early ceiling rises, novel contexts can locally reduce depth without resetting memory or the psyche.
- Continuous `cognitive_depth` in [0, 3] derived from effective gate.
- ADULT_FROM_TICK_0 remains a full-depth control.
- EXPERIENCE_GATED aliases the generalized developmental mode (DEVELOPMENTAL kept runnable).

## Forbidden (unchanged)

curiosity/novelty/exploration rewards, scripted exploration, semantic labels, psyche replacement, memory wipe on novelty.
