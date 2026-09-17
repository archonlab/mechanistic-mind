# Developmental Experience Acquisition

Experimental mechanism: bounded early cognitive access to accumulated experience.
Not an optimization feature. Not childhood psychology.

## Architecture insertion (minimal)

1. `mechanistic_mind/psyche/developmental.py` — config, maturity metrics, gate factor, observer snapshot.
2. `DevelopmentalGateModule` (psyche stage MEMORY) — updates gate from ordinary memory stores; writes `memory.developmental` (ground-truth diagnostics) and `working.developmental_gate` for later modules.
3. `sensorimotor.generate_proposals` / `retrieve_evidence` — optional gate scales learned-proposal slots and recent-fragment retrieval horizon. Memory formation unchanged.
4. `OrganismPredictionModule` — when gate present, discounts long-horizon history models / old episodes proportionally (same psyche).
5. `ExperienceCompressionMechanism` — optional `CompressionConfig.developmental`; scales effective retrieval budget / sample trust under DEVELOPMENTAL; ADULT_FROM_TICK_0 and disabled leave prior behavior.
6. Experiment `experiments/run_developmental_experience_v01.py` — DEVELOPMENTAL vs ADULT_FROM_TICK_0.

## What is NOT added

curiosity/novelty/exploration reward, scripted exploration, semantic labels, psyche replacement, memory reset, tick-only adulthood.

## Conditions

- `DISABLED` — gate unused; prior architecture.
- `DEVELOPMENTAL` — gating enabled from tick 1.
- `ADULT_FROM_TICK_0` — mature access immediately with empty history (control).
