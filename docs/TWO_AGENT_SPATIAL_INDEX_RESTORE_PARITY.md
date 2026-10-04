# TWO-AGENT SPATIAL INDEX RESTORE PARITY

This is a repair only: no new preset, mechanism, sensor, UI or physics.

Contract:

```text
snapshot at tick T → TwoAgentRuntime.restore → immediate read-only spatial queries
                   == the same queries on the original runtime at tick T      (no extra tick)
```

## 1. Audit (before the change)

| # | Question | Answer |
|---|---|---|
| 1 | Who owns the shared `PlanetState`? | `TwoAgentRuntime.world` is `slots[0].world`. Every slot's `.world` points to that one object. During restore, slot 1 deserializes its own copy of `agents[0].world`, which is then discarded (`ri.world = restored[0].world`). |
| 2 | Where do bodies enter the index during a normal tick? | Each slot's `finish_tick` reconciles with **its own body only** (the other body's ref is removed transiently). The container then runs `reconcile_contents(world, body_refs_for_runtime(self), reason="contact_and_manipulator")` with **all** bodies. End-of-tick invariant: every body once. |
| 3 | Where does the single-agent restore rebuild? | `PhysicalSystemRuntime.restore`: `rebuild_from_world(world, body_refs_for_runtime(runtime), reason="restore")`, then it restores the saved generation. |
| 4 | Where does the two-agent restore restore the slots? | `TwoAgentRuntime.restore` calls `PhysicalSystemRuntime.restore` per slot, then rebinds `slot.world`, sanitizes attachments with all slot ids, stamps the preset, ensures columns and sets the experimenter slot. |
| 5 | Why is body-0 present but body-1 missing? | The slot-0 restore rebuilds the **shared** world's index with `body_refs_for_runtime(slot0)`, which contains `body-0` only. The slot-1 restore rebuilds the index of its **discarded** world copy. Nothing rebuilds the shared index with all bodies until the first container reconcile of the next tick. |
| 6 | Is reconcile called before or after the second body is bound? | Before. The only rebuild happens inside the slot-0 restore, before slot 1 exists. |
| 7 | Which ref kinds exist? | `BODY`, `RESOURCE_OBJECT`, `SURFACE_DEPOSIT` (`_expected`). Surface columns are **not** index entities and are not materialized. |
| 8 | Is the index derived or authoritative? | Derived. The snapshot stores only `spatial_index_generation / schema / checksum` metadata; refs are always rebuilt from authoritative state. |
| 9 | Can a repeated rebuild duplicate refs? | No. `rebuild_from_world` starts a fresh index and `_place` replaces by key. |
| 10 | Does ObserverSession have the same defect? | Yes, through the same call. `ObserverSession.restore` → `TwoAgentRuntime.restore`, and `restore_committed_checkpoint` → `self.restore`. The experimenter capture/test replay (`experimenter_control.py`) also calls `TwoAgentRuntime.restore`. |

### Second defect with the same root cause (found in the audit)

The slot-0 `PhysicalSystemRuntime.restore` also ran `sanitize_attachments(shared_world, {"agent_0"})`.
Any object **held by agent_1** was turned into FREE_STATIC with no holder, which is a restore-induced
change of authoritative state (`audit_held_probe_before.txt`). The container's own sanitize with
all slot ids came too late. Root cause: a single-slot restore finalized the shared world before every
slot was bound.

## 2. Restore call chain

Before:

```text
TwoAgentRuntime.restore(payload)
  PhysicalSystemRuntime.restore(agents[0])                         (shared world W0)
      restore_planet_state → … → sanitize_attachments(W0, {"agent_0"})     ✗ drops agent_1's held object
      rebuild_from_world(W0, [body-0])                                      ✗ index lacks body-1
      ensure_surface_columns / LPS / PCA / FOK restore
  PhysicalSystemRuntime.restore(agents[1] + world copy W1)         (W1 discarded)
      sanitize_attachments(W1, …); rebuild_from_world(W1, …)
  slot.world = W0; sanitize_attachments(W0, {agent_0, agent_1}); stamp preset; ensure columns;
  experimenter slot; process order; _lps_bind()
→ index incomplete until the next tick's container reconcile
```

After:

```text
TwoAgentRuntime.restore(payload)
  PhysicalSystemRuntime.restore(agents[0], shared_world_member=True)   no shared-world finalization
  PhysicalSystemRuntime.restore(agents[1], shared_world_member=True)   (W1 discarded, not indexed)
  slot.world = W0; sanitize_attachments(W0, {all slot ids}); stamp preset; ensure columns;
  experimenter slot; process order
  rebuild_after_restore(W0, body_refs_for_runtime(rt), tick=T, config)   ONCE: all bodies + objects + deposits
  _lps_bind()
```

`shared_world_member` is keyword-only and defaults to False, so the single-agent restore
(ObserverSession single-agent schema, tests, tools) runs exactly as before.

## 3. Rebuild point and policy

`spatial_contents.rebuild_after_restore(world, bodies, *, tick, config)`:
* no-op when the multi-content index is inactive (Tiktaalik, pre-index Acanthostega);
* `rebuild_from_world(..., reason="restore")` from authoritative state;
* restores the saved `spatial_index_generation`. This is the existing single-agent policy.

The checksum is recomputed from the rebuilt index (the existing policy; no validation existed). For a
consistent snapshot it equals the saved checksum. The rebuild does not advance the tick, integrate
anything, run cognition or physics, or emit receipts. It appends one derived
`SPATIAL_CONTENTS_INDEX_REBUILT/restore` record to the non-serialized `spatial_index_history`, as the
single-agent restore always has. The body ids come from `body_refs_for_runtime(rt)`, which respects the
experimenter slot, so a 3-body shared world is complete as well.

## 4. Refs, held and free objects

* Every body is indexed once at `world_cell(x, y)`, with WRAP applied by `wrap_coord`.
* Every ResourceObject is indexed once. **Held-object contract (unchanged):** a HELD object is an
  ordinary index entity at its authoritative world pose, which equals the holder's effector pose after
  the last world step. It is never duplicated as free, and its holder/hand now survive the restore.
* A `FREE_MOVING` object is indexed at its snapshot pose. Its velocity is preserved, it is not
  integrated during the rebuild, and it first moves on the next world tick by exactly one
  damp-then-drift step.
* Surface deposits are indexed as before. Columns are not index entities.

## 5. Diagnostic (researcher/debug-only, read-only)

`spatial_index_consistency(world, bodies)` and `TwoAgentRuntime.spatial_index_consistency()` return
`spatial_index_consistent_with_authoritative_state`, `missing_refs`, `duplicate_refs`, `stale_refs`,
`wrong_cell_refs`, `wrong_revision_refs`, `by_entity_without_cell_ref`, `checksum` and
`expected_checksum`. It writes no events, performs no repair and never mutates state. It is not run
per tick and not wired into cognition. The existing `validate_against_world` is **not** read-only (it
appends a MISMATCH event), which is why a separate function was added.

## 6. Verification

* Tests: `tests/test_two_agent_spatial_index_restore_parity.py` (spec items 1–24 plus the diagnostic).
  FOK test 35 now compares body refs immediately after load.
* `results/two_agent_spatial_index_restore_parity/parity_verification.json`: pre-fix emulation vs the
  repaired path, the ObserverSession RESTORE frame, and a 3-body experimenter restore.
* Preservation: LPS preservation probe diff; Audio A, Audio B and FOK calibration / restore
  verification reruns (identical).

### Test results (exact counts; logs in `results/two_agent_spatial_index_restore_parity/test_logs/`, summary in `gates.json`)

* New tests: **20 passed / 0 failed**. Under the pre-fix emulation plugin: 15 failed / 5 passed (they detect the defect).
* FOK test 35 (updated): **1 passed**.
* Targeted regression (45 files, 6 shards): **553 passed / 11 failed**. All 11 are outside the known list and fail identically under the pre-fix emulation.
* Full suite (322 files, 10 shards): **2656 passed / 65 failed / 29 skipped**. The 65 failures are the 6 known pre-existing ones plus 59 others, and all 59 fail identically under the pre-fix emulation. `unexplained_failures = []`.
* `tests/test_observer_compact_run_setup.py` (tkinter) hung in its third test and was killed. It is not in the totals above. Run separately under `timeout`, it gave 2 passed and a hang (EXIT 124), and it hangs the same way under the pre-fix emulation.
* Additional findings: 11 stale failures outside the known list in the targeted run, and a hung Tk test in the full run.

## 7. Limitations and findings (not changed here)

* **Fresh construction** (`TwoAgentRuntime.__init__`) has the same gap: body-1 is missing until the
  first container reconcile. It is a construction lifecycle issue, not restore. Fixing it would shift
  generation counters of every two-agent run, so it was left for a separate, explicit decision.
* **`experimenter_spawn`** (live runtime) lacks the new body until the next tick. A restore of that
  runtime is complete.
* **`TwoAgentRuntime.restore` resets `process_order`** to `(0, 1, …)` regardless of the snapshot. This
  is pre-existing. Free-object trajectories are order-independent; this was not changed.
* **Ref metadata `pose_tick`** is not serialized and is set to T on rebuild. It is excluded from the
  checksum and from the parity comparisons. Kind, id, cell and state revision are compared.
* **Restore writes a Column-Transfer `SURFACE_COLUMN_TRANSFER_RESTORE_VERIFIED`** entry into
  `surface_columns.history`. This is pre-existing policy and unchanged.

## 8. Next stage (not implemented)

OBJECT GEOMETRY + BODY/OBJECT CONTACT FACT: only the physical fact of geometric contact, with no
impulse response and no sound.
