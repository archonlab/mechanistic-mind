# Beta 3.1 Observer frame memory fix

Demand-driven public WORLD frames + compact per-tick history. Scientific ticks, cognition, V3, vision, and RNG are unchanged.

**Live PID 368895 was not modified or restarted.**

## Root cause

Every `step()` / slow-sim capture built a full `live_frame` (world Python float lists), `json.dumps` (~0.96 MB), and retained up to **512** copies on `_buffer`. That dominated reproduction RSS (~5500 MB/1000 ticks vs ~990 with frames suppressed).

## Architecture after

```
scientific tick → compact_history_from_runtime (tick, action, pose, contact)
               → V3/V2 writers (unchanged)
publication wanted? (eager subscriber or websocket clients; never HEADLESS)
    → live_frame once
    → json.dumps once
    → _published_json + websocket envelope
    → retain 1 full frame
```

| | Before | After |
| --- | --- | --- |
| Full WORLD frames retained | 512 | **1** |
| Compact history | derived from full frames | per-tick scalars, no grids |
| Play without UI clients | still captured at ui_hz | **no live_frame** |
| HEADLESS | could still pay capture on step | **0 builds** in window |
| WS clients | shared last_text; extra dumps possible | one dumps; last_text cleared when clients=0 |

## Measurements (reproduction, not PID 368895)

Young eager WORLD: **319 MB/1000 ticks** (was 5500).  
Aged (ticks 281–361, client): **131 MB/1000 ticks** (live historical 614).  
HEADLESS window: **0** extra live_frame builds, **168 MB/1000 ticks**.  
`malloc_trim` diagnostic after aged pause: **11 MB** (churn removed; not the production fix).

Deterministic 40-tick LIVE vs LIVE and LIVE vs HEADLESS science: **identical**.

## Tests

`tests/test_beta31_observer_frame_memory_fix.py` plus updated scientific-history / async-capture expectations.

## Inspect

Clicking a timeline tick that is not the latest WORLD frame still returns `NOT AVAILABLE` (same as ticks that had already fallen out of the old 512 ring). Action/pose history remains on `/api/timeline`. Full WORLD playback of the past is **scientific_timeline.jsonl / Analyze**, not the RAM ring.
