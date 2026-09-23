# PSC MOTOR RESOLUTION — DEVELOPMENTAL FORK

Paired fork experiment: identical Phase-A history → LOCO_FACTORIZED vs OBSERVED_COMPOSITE.

## Protocol (pilot duration)

Documented **shorter** than full 1000+2000 for pilot validation:

- Phase A: **200** ticks, PSC OFF, SMC/HSS/embodied ON, mode LOCO_FACTORIZED
- Snapshot + fork identity check (both branches LOCO)
- Branch L: PSC ON, `LOCO_FACTORIZED`, **300** ticks
- Branch C: PSC ON, `OBSERVED_COMPOSITE`, **300** ticks

Full-length protocol: `MM_FORK_PHASE_A=1000 MM_FORK_BRANCH=2000`.

Pilot: `scripts/run_psc_motor_resolution_developmental_fork.py`

## Gates before battery

1. LOCO_FACTORIZED_EXACT_MATCH
2. OBSERVED_COMPOSITE_PRODUCTION_PATH_DEMONSTRATED
3. NO_CARTESIAN_INVENTION
4. FULL_COMPOSITE_WINNER_REACHES_PHYSICAL_MOTOR
5. FORK_IDENTITY_EXACT_MATCH
6. SCIENTIFIC_V3 mode on DecisionReceipt
7. CONFIG_HISTORY_RECORDS_MOTOR_RESOLUTION
8. Pilot first-divergence forensics

## Analysis distinction

- **PRE-DIVERGENCE**: same-state counterfactual (shared snapshot)
- **POST-DIVERGENCE**: trajectory comparison only — not same-state CF

## Claim boundary

Measures causal developmental consequences of motor resolution. Does **not** rank architectures or claim better/smarter behavior.

Artifacts: `results/psc_motor_resolution_developmental/`

## Pilot results (seeds 111, 17, 733)

- FORK_IDENTITY_EXACT_MATCH: true for all three
- All three pairs diverged
- Typical FIRST_PSC_DIFFERENCE_TICK: 201 (first PSC-on tick after Phase A=200)
- Seed 111: first locomotion difference at 201 (WAIT+freq vs MOVE:W)
- Seed 17: first composite-only difference at 201; physical at 209
- Seed 733: selection-source / side-channel difference; physical at 202

## Battery aggregate (10 seeds)

- pairs diverged: **10/10**
- median ticks to first PSC difference: **201**
- first locomotion difference: 7/10 seeds
- first composite-only: 2/10 seeds
- first differing motor dimensions (forensics): locomotion 7, freq 7, amp 2, neck 1, emit 1

No architecture ranking. PRE-DIVERGENCE = shared-snapshot CF; POST = trajectory only.
