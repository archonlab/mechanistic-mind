# Release 0.3.2

## Obstacle Learning & Value Ecology

### Added to World Engine

- `ObjectiveObstacle`
- perceptual obstacle cues
- traversable hazards
- hidden obstacle body effects
- obstacle contact probability
- obstacle terrain cost
- `SET_OBSTACLE_ACTIVE` exogenous event
- object cue signatures
- object cue salience
- object cooldown
- optional maximum-use capacity

### Added to psyche implementations

Still the same candidate foundation roles, with richer implementations:

- attention includes visible obstacles;
- spatial memory stores obstacle cues;
- learning stores object-cue and obstacle-cue consequence models;
- prediction can generalize value across object cues;
- direct object experience overrides cue-only prediction;
- prediction can value routes through known space;
- exploration uses expected value when choosing among novel moves.

No new personality/avoidance/fear state was added.

### Important fix

Regulatory valuation now consumes the actually learned interoceptive-change
keys.

This fixes a v0.3.x mismatch where learned `energy_signal` / `fatigue_signal`
effects could be ignored because valuation searched only for suffixed
`*_delta` keys.

### Canonical world

`worlds/obstacle_value_world_v032.py`

Includes:

- a home/resource site,
- a genuinely useful training goal,
- a high-value far goal,
- a lower-value alternative,
- a traversable obstacle on a short route,
- a look-alike decoy spawned after cue learning.

### Diagnostic result

Safe direct-route history:

```text
MOVE:3,2 selected
```

Harmful direct-route history:

```text
MOVE:2,1 detour selected
```

Learned value cue:

```text
novel look-alike changes exploration direction
```

Free-life decoy:

```text
predicted progress = 0.55
actual progress    = 0.0
```

### Acceptance

All legacy tests plus v0.3.2 tests pass.

The new tests cover:

- hidden obstacle truth,
- first-contact physical damage,
- obstacle-cue learning,
- learned detour selection,
- sham visual cue control,
- cue-based false value expectation,
- correction after direct experience,
- cue-guided exploration,
- cooldown semantics,
- exogenous decoy appearance,
- obstacle removal with stale memory.
