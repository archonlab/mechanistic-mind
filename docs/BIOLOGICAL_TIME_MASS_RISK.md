# Biological Time & Mass Risk v0.3.1

## Problem corrected

The v0.3 Body Engine allowed positive `energy_delta` to contribute indirectly
to mass change.

That mixed together two different things:

```text
functional state improvement
metabolic energy intake
```

A useful, pleasant, successful, or restorative outcome must not automatically
increase body mass.

v0.3.1 removes that coupling.

## Time contract

Default:

```text
tick_duration_days = 1.0
days_per_year = 365.2425
```

Objective Body Truth tracks:

```text
age_days
simulated_days
life_day
age_years
```

`age_years` is derived for presentation.

## Mass causal model

Mass changes only through:

```text
metabolic_energy_intake
-
metabolic_energy_expenditure
```

Expenditure currently includes:

```text
basal metabolic expenditure
movement-related expenditure
explicit external/exogenous expenditure
```

Functional variables such as `energy_reserve` remain separate.

A resource may therefore:

```text
increase energy_reserve
without increasing mass
```

unless it also carries explicit `metabolic_energy_intake`.

## Canonical objects

### OBJ-04 Recovery Site

Can improve functional state and fatigue.

It does not provide metabolic intake.

### OBJ-17 Energy Resource

Provides:

```text
energy_delta
metabolic_energy_intake
```

and can therefore affect long-term body mass.

### OBJ-23 Hydration Resource

Provides hydration/recovery effects.

No direct mass-energy input.

### OBJ-31 Progress Site

Provides objective world progress and physical cost.

It has no metabolic intake and no direct mass effect.

## Risk function

The configured zero-risk operating region is:

```text
45 kg <= mass <= 120 kg
```

Low-mass risk transitions smoothly from:

```text
45 kg → risk 0
35 kg → risk 1
```

High-mass risk transitions smoothly from:

```text
120 kg → risk 0
140 kg → risk 1
```

The implementation uses a smoothstep curve instead of a binary threshold.

## Risk consequences

Risk is objective physiology, not a psychological variable.

Current candidate effects include:

```text
risk ↑
→ fatigue accumulation ↑
→ slow damage accumulation ↑
→ recovery efficiency ↓
→ movement effort ↑
```

Low-mass risk additionally increases passive energy drain.

These are candidate toy mechanisms and should later be experimentally replaced
or calibrated rather than treated as established human physiology.

## Agent knowledge boundary

The agent cannot observe:

```text
mass_kg
age
low_mass_risk
high_mass_risk
physiological_mass_risk
metabolic balance
safe-mass boundaries
```

The Observer can.

The psyche receives downstream experienced signals only.

## Rate limits

Mass cannot jump arbitrarily fast:

```text
max gain = +0.05 kg/day
max loss = -0.08 kg/day
```

This is a numerical/physiological guard for the toy model.

## Testable questions

v0.3.1 enables experiments such as:

```text
same psyche + food nearby
vs
same psyche + food far away
```

and asks whether different energy balance histories produce different mass,
movement costs, learned strategies, and behavioral attractors without adding a
rule such as:

```text
if overweight:
    move_less()
```
