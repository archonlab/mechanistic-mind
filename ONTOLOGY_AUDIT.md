# Ontology Audit — v0.3.4

## Scope

The audit covers executable simulator and agent source in `mechanistic_mind/`,
`worlds/`, `observer_launcher.py`, and `configs/`. Historical documentation is
not mechanically renamed or treated as executable ontology.

## Result

There is no primitive concept of shelter, building, settlement, recipe,
crafting, or craft in the executable ontology. A case-insensitive search of
the audited paths returns no matches:

```bash
rg -n -i 'shelter|building|settlement|recipe|crafting|craft' \
  mechanistic_mind worlds observer_launcher.py configs
```

The v0.3.4 mechanics are lower-level:

- objects have positions, mass, mobility, perceptual cues, and a numeric
  directional-attenuation coefficient;
- bodies have generic persistent numeric load channels;
- object effects may be gated by numeric body-state bounds;
- local directional exposure is calculated from object positions on a ray;
- the agent can request generic `TAKE`, `MOVE`, and `RELEASE` actions;
- predictive learning stores observed action n-grams of length two and three.

No object is labelled as a construction component in agent-accessible data.
No arrangement is classified, rewarded, completed, or named. No desired
configuration, action template, completion detector, or reconstruction policy
exists.

## Knowledge boundary

The initial psyche contains an empty `action_history_models` mapping. Object
condition rules, internal load truth, mass, attenuation coefficients, and local
exposure receipts are excluded from agent observation. Therefore the agent
does not start knowing that object-effect combinations exist.

## Lexical caveat

This audit document and release documentation necessarily mention prohibited
high-level words to state their absence. Tests also use those strings as a
negative observation check. Such mentions are assertions about the ontology,
not executable concepts available to the world or agent.
