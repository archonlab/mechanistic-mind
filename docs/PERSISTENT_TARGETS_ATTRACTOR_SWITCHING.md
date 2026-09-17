# Persistent Targets & Attractor Switching

## Core idea

A target is not only a place.

A target may have hidden internal dynamics:

```text
same visible target
+
repeated action attempts
+
hidden target state
→ success / failure / delayed success / no success
```

The agent does not know:

- whether the target truly works;
- how many attempts remain before success;
- whether the target has broken;
- whether the target will later revive.

## v0.3.3 minimal ontology

### Objective world truth

`TARGET-ANVIL` contains hidden variables:

- `target_mode`
- `completion_threshold`
- `attempt_progress_gain`
- `latent_progress`
- `success_count`
- `switch_tick`

### Observable layer

The psyche sees only:

- local position
- visible object cue
- action availability
- experienced consequences after each `USE`

### Regimes

- `WORKING` — repeated use eventually succeeds.
- `BROKEN` — repeated use works at first, then the same target becomes unproductive after a hidden switch.
- `DEAD` — the target remains visible and usable but never produces success.
- `REVIVAL` — the target is initially unproductive and later begins to work.

## Why this matters

This lets the simulator ask:

```text
when does repeated action mean adaptive persistence?
and
when does the same visible pattern become a self-maintaining attractor?
```

External behavior may look identical:

```text
USE
USE
USE
USE
```

But hidden world dynamics can differ radically.

## Minimal mechanism

Each use of `TARGET-ANVIL` can:

- impose a small physiological cost;
- optionally add a small partial progress signal;
- increase hidden latent target progress if the target is currently operative;
- produce a completion event only after the threshold is crossed.

The same action pattern can therefore have different long-run value depending on the regime.

## Scientific boundary

v0.3.3 does not model human meaning, frustration, or symbolic commitment.

It only creates a minimal dynamical setting where persistence and attractor switching can be studied as interactions between:

- learned expected value
- uncertainty
- habit
- body regulation
- hidden target dynamics
