# Session hot-path optimization

## Finding (methodology)

The historical **~80 t/s bare cognition → ~35 t/s Session** gap was largely an
**apples-to-oranges** comparison:

| Config | Actions | Typical `runtime.step` |
|--------|--------:|------------------------:|
| Bare `tiktaalik_config` TwoAgentRuntime | 5 loco | ~80 t/s |
| `ObserverSession.apply_experiment` (fresh mechanisms) | ~14 (neck/push/OSC) | ~37 t/s |

Fair Session overhead is measured against **Session's own** `runtime.step`.

## PERFORMANCE PROFILE CONFIGURATION MISMATCH DISCOVERED

Session TPS numbers depend on which mechanisms were actually constructed.
A cross-tab Apply/Reset bug could leave experimental cognition OFF while the
UI implied otherwise. Keep these rates as configuration-specific. Not the
canonical Beta 3.1 optimization baseline unless the run matches `TIKTAALIK_BETA31`.
Artifacts not deleted.

## What Session was paying beyond `runtime.step`

1. `accumulate_events` — collect/enrich/sort/dedup structured events (~1–2 ms)
2. `_record_motion_locked` — even in HEADLESS, was running LIVE forensic observers
   (action_realization / work_ecology / locomotor_economy) + trajectory/telemetry rings (~3+ ms)
3. Scientific V2 append when enabled (~smaller)

Scientific V2 **already** builds AR/WE/LE from the slot at write time; Session
accumulators were Observer presentation.

## Optimizations (this task)

1. **HEADLESS purity:** skip LIVE rings + AR/WE/LE observers per tick.
2. **Tick-scoped event drain:** `collect_observer_events_for_tick` — same enrich/sort
   contract restricted to the current tick (no full-history reprocess).

## Non-goals / rejected

- Narrowing PSC `branch_actions` to locomotion only (science change)
- Dropping structured events
- Rewriting Scientific V2 format
- Further PSC Numba work

## NEXT

**SEARCH_COMPACT** evidence tier for Search workers (optional full V2).

See `results/session_hotpath/SUMMARY.md`.
