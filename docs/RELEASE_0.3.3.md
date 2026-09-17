# Release 0.3.3

## Persistent Targets & Attractor Switching

This release adds a new canonical world:

```text
persistent-targets
```

The new world introduces hidden target dynamics.

A visible target can remain in the same location while its objective regime differs:

- genuinely productive;
- broken after earlier success;
- never productive;
- revived after an unproductive phase.

## Added world

`PersistentTargetsWorld`

Available CLI conditions:

- `WORKING`
- `BROKEN`
- `DEAD`
- `REVIVAL`

Launcher example:

```bash
python observer_launcher.py \
  --world persistent-targets \
  --mechanism psyche-v03 \
  --persistent-condition BROKEN \
  --ticks 120 \
  --seed 17
```

## Key mechanism

`TARGET-ANVIL` has hidden internal state:

```text
latent_progress
completion_threshold
attempt_count
success_count
target_mode
switch_tick
```

The psyche does not observe these directly.

It only observes the experienced effects of repeated `USE:TARGET-ANVIL`.

## Research use

This world supports experiments on:

- adaptive persistence;
- delayed payoff learning;
- attractor locking after environmental change;
- abandonment and switching;
- differences between external repetition and hidden productivity.

## Claim boundary

This release establishes only a toy mechanism class for repeated-target dynamics.

It does not establish a human model of perseverance, obsession, boredom, or frustration.
