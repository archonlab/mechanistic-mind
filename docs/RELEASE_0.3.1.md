# Release 0.3.1

## Biological Time & Mass Risk

### Changed

- one default simulation tick now represents one simulated day;
- objective age is stored in days and presented in years;
- default adult-like organism starts at 70 kg and approximately 18 years;
- body mass is no longer coupled to generic positive energy outcomes;
- explicit `metabolic_energy_intake` and expenditure drive mass;
- progress has no direct body-mass effect;
- canonical OBJ-17 is explicit metabolic intake;
- daily mass gain/loss is rate-limited;
- smooth objective mass-risk functions were added below 45 kg and above 120 kg;
- mass risk affects physical physiology, not psyche labels.

### Mass-risk configuration

```text
safe operating region: 45–120 kg
low critical:           35 kg
high critical:          140 kg
hard simulator bounds:  25–180 kg
```

These values are project simulation parameters, not clinical thresholds.

### Scientific boundary

Agent observations still exclude:

```text
mass
age
risk scores
risk thresholds
metabolic balance
physiology formulas
```

### Acceptance

New acceptance verifies:

- 1 tick = 1 simulated day;
- 45–120 kg has zero configured mass risk;
- low/high risk rises smoothly outside that region;
- functional-energy improvement without food does not add mass;
- explicit metabolic intake changes mass relative to control;
- mass gain/loss rate clamps work;
- progress site has no metabolic intake;
- energy resource does have explicit metabolic intake;
- mass-risk/time fields remain Observer truth.

All previous Mechanistic Mind tests continue to pass.
