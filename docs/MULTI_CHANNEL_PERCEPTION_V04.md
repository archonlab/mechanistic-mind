# Update 4 — Multi-Channel Physical Perception × Activity–Recovery

## Architecture (minimal)

New module: `mechanistic_mind/world_engine/perception.py`

Channels (agent-facing numeric packets only):

1. `DISTANT_STRUCTURAL` — partial geometry proxies; **feature count drops with distance** (not only amplitude).
2. `PASSIVE_WAVE` — object `emission` configs; amplitude/frequency/bearing; no labels.
3. `ACTIVE_RETURN` — result of agent `EMIT`; returns strip `_observer_object_id` before cognition.
4. `NEAR_CONTACT` — existing near vision + contact receipt bits (no shape/color/cue).

Mode switch: `WorldEngineConfig.perception_mode` = `CONTACT_ONLY` | `MULTI_CHANNEL`.

`EMIT` action: available when `emit_enabled`; tiny energy/fatigue cost; no intrinsic reward.

Activity–recovery: `BodyConfig.recovery_dynamics_enabled` (default **False**). When on, activity accumulates `activity_load`; WAIT/inactivity permits bounded fatigue recovery scaled by load. No WAIT reward.

## Known prior leakage (documented, not silently rewritten)

- `visible_objects[].id` and action kinds `USE/TAKE/PUSH:<id>` still reach cognition (pre-existing affordance API).
- New channel packets forbid id / cue_signature / shape / color.

## Observer

Panels 6–9: Cognitive Depth, Autonomous World, Perception (agent input), Activity/Recovery.
Launch flags: `--perception-mode contact-only|multi-channel`, `--recovery-dynamics`.

## Experiments

`experiments/run_multi_channel_perception_v04.py` → `results/update4_multi_channel_v04/summary.json`
