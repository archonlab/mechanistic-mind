# TWO-AGENT SPATIAL INDEX RUNTIME LIFECYCLE PARITY

Repair only: no new preset, mechanism, object contact, geometry, impulse, gravity, or acoustics.

Contract:

```text
construct runtime        → shared derived index complete before runtime is exposed
spawn experimenter body  → index complete before success is returned
despawn experimenter body→ stale refs absent before success is returned
```

No extra scientific tick.

## 1. Audit (factual call chains)

### Constructor / `reset`

```text
TwoAgentRuntime.__init__ → reset()
  for i, start in starts:
    PhysicalSystemRuntime(seed, config)           # slot i creates its own PlanetState
      spawn_preset_resource_objects
      rebuild_from_world(world_i, [body-i], reason="initialization")   # only THIS body
    if i > 0:
      slot.world = slots[0].world                 # discards world_i (+ its index)
  self.world = slots[0].world                     # shared world keeps slot0's incomplete index
  ensure_surface_columns_for_runtime(...)         # deposits may appear AFTER slot0 rebuild
  rebuild_after_authoritative_entity_change(      # NEW once
      world, body_refs_for_runtime(self),
      reason="construction", generation_policy="fresh")
  _lps_bind()
→ runtime exposed with both bodies + objects + deposits
```

Root cause (constructor): slot0 builds the shared index with `body_refs_for_runtime(slot0)` = `[body-0]` only. Slot1's PSR rebuilds a throwaway world that is discarded. Until the first container `reconcile_contents(..., body_refs_for_runtime(TwoAgentRuntime))`, body-1 is missing.

### Experimenter spawn

```text
spawn_experimenter_body(rt, x, y, …)
  reject if already spawned / not TwoAgentRuntime / no slots
  PhysicalSystemRuntime(...)                      # builds throwaway world+index
  exp.world = rt.world                            # shared world unchanged so far
  set pose; append slot; set experimenter_slot
  rebuild_after_authoritative_entity_change(      # NEW once on success
      reason="experimenter_spawn", generation_policy="bump")
  return accepted
```

Authoritative body storage: `rt.slots[experimenter_slot].body` with undercover ids from `slot_agent_body_ids`. Rejected spawn paths return before rebuild → index unchanged. Re-spawn contract unchanged: `SPAWN_REJECTED:ALREADY_SPAWNED`.

### Experimenter despawn

```text
remove_experimenter_body(rt, controller)
  require experimenter is last slot
  slots.pop(); clear experimenter_slot / stats / process_order
  rebuild_after_authoritative_entity_change(      # NEW once on success
      reason="experimenter_despawn", generation_policy="bump")
  return accepted
```

### Restore (unchanged seam)

`TwoAgentRuntime.restore` still calls `rebuild_after_restore` once (now a thin wrapper over the shared helper with `reason="restore"`, `generation_policy="preserve"`).

## 2. Lifecycle rebuild seam

`spatial_contents.rebuild_after_authoritative_entity_change(world, bodies, *, tick, config, reason, generation_policy)`:

| policy | use | generation |
|---|---|---|
| `fresh` | construction | zero then rebuild → derived generation `1` |
| `preserve` | restore | keep saved `spatial_index_generation` |
| `bump` | spawn / despawn | normal `rebuild_from_world` (+1) |

Always: one full rebuild from authoritative `_expected` (bodies + ResourceObjects + deposits). No scientific tick, cognition, integration, contact, observation, acoustic event, or Analyzer scientific row. Appends one derived `SPATIAL_CONTENTS_INDEX_REBUILT/<reason>` to non-serialized `spatial_index_history` (existing metadata channel).

`spatial_index_generation` / checksum / rebuild history are **derived cache/index semantics**, not scientific model generation. Scientific/runtime tick is untouched.

## 3. Transient per-slot window

Within `_step_once`, each slot `finish_tick` reconciles with **its own body only**, transiently removing the other body's ref. Container then `reconcile_contents(..., body_refs_for_runtime(self), reason="contact_and_manipulator")`.

Scientific readers in the current pipeline:

* `observations()` runs **before** any `finish_tick` (full index from previous end-of-tick / construction).
* Soft contact / push use **body poses**, not the spatial index.
* Contact acoustics / LPS / manipulator container pass use `body_refs_for_runtime` **after** (or independently of) the per-slot window; container reconcile restores full index before later consumers that care about the shared index.

**Verdict: `NOT_OBSERVABLE_IN_CURRENT_TICK_PIPELINE`.** No tick-pipeline rewrite in this stage.

## 4. Immediate visibility

After construct / successful spawn / despawn, before `step()`:

* `spatial_index_consistency()` passes
* both (or remaining) body refs present exactly once
* ResourceObjects / deposits preserved
* Observer/researcher reads see a consistent derived index

Held / FREE_MOVING objects: rebuild does not integrate; holder/hand/pose/velocity/composition unchanged.

## 5. Tests

`tests/test_two_agent_spatial_index_lifecycle_parity.py` — constructor, spawn, despawn, generation, restore smoke, transient instrumentation, first-tick equivalence.

Restore suite `tests/test_two_agent_spatial_index_restore_parity.py` remains green.

## 6. Next safe seam

`OBJECT GEOMETRY + BODY/OBJECT CONTACT FACT` (geometry-only researcher contact fact; no impulse / bounce / damage / sound / auto composition).
