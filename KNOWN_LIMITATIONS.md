# Known limitations — MM 1.0 Tiktaalik Public Beta 3.1

These are limitations of the current tree. They are not claims about organisms.

## Beta 3.1 (verified against current source)

- Scientific V3 motor receipts do **not** expose `domain_sources` (that field
  exists on runtime composite motor output, not the V3 motor JSONL schema).
- Analyzer cannot fully distinguish `RETAINED_PREDICTION` vs
  `ENDOGENOUS_VARIATION` for factorized side channels.
- Analyzer composite formatting may omit `NECK_HOLD` even though the Observer
  HUD displays it (Analyzer often treats HOLD as non-event).
- Legacy instrumental EMIT bridge remains separate/partial (`instrumental_emit_bridge`
  is not OSC). OSC is physical oscillatory signaling.
- `NECK_HOLD` retained-match dominance remains current `_pick_supported`
  behavior. This release does not retune that selector.
- Intermittent WORLD display flash remains unisolated and is not established as
  a physics issue.
- Default single-agent `GET /api/model` currently returns HTTP 500 because
  `PhysicalSystemRuntime` lacks `mechanism_snapshot`. This is pre-existing.
  SPA, health, experiment, TIKTAALIK_BETA31 Apply, two-agent runtime, and
  release smoke paths work. It is not repaired in this release.
- Observer **Vision** settings may reset or return to a different / default
  configuration during some configuration and reset workflows. This is a known
  UI/workflow limitation, planned for a future version. It is not repaired in
  this cut. After Apply / Reset, re-check the Vision tab (enabled, range,
  surface discrimination, optical mapping, Spatial Vision, FOV / effective
  status) before a long run. See the README pre-run checklist.

Frozen Public Beta 3 limitations below still apply unless listed as resolved.

## Disk space and evidence volume

Long FULL SCI (Scientific V3) runs can generate large JSONL evidence streams
(`scientific_decisions.jsonl` is typically the largest). Monitor available disk
space during extended experiments and archive or remove obsolete runs when
appropriate.

This release does **not** add an automatic destructive cleanup policy.

## Abandoned live staging (`.live-*`)

While a session is running, Scientific V3 and V2 writers may stage under
`results/psychology_observer/psy_observer_web/.live-<run_id>/`.

Successful Save & Stop publishes into `psyweb-<run_id>/` and then removes that
`.live-*` directory. If the Observer process is killed, the machine loses power,
or Save & Stop fails, a `.live-*` directory can remain. Those directories can be
large. They are not deleted automatically except after a successful publish.

`.tmp-*` directories are staging for atomic snapshot publication. Failed saves
should remove them; an unexpected kill can leave an empty or partial `.tmp-*`.

`results/analysis_jobs/` holds Analyzer subprocess output. It is not pruned by
the Observer.

## Analyzer compact TickStories

Analyzer Next TickStories scale with analyzed tick count × agent count. Memory
is bounded relative to loading full DecisionReceipt JSON, but wall time and
on-disk Analyzer artifacts still grow with the analyzed span.

HTTP Analyzer results remain compact summaries. The Observer does **not** return
raw multi-GB scientific JSONL through the analysis API.

## Historical terrain reconstruction

Per-tick terrain / site reconstruction in Analyzer reports is limited. Season and
geology are **not recorded per tick** in the current Scientific V3 package
(`season_geology_reference = NOT_RECORDED_PER_TICK`). Do not treat missing
historical terrain fields as zero terrain.

## Human overlays vs agent-accessible perception

World / terrain / FOV / signal overlays shown to a human observer are Observer
visualization. They are not agent-accessible merely because a human can see them.
Agent-accessible evidence is what appears in ObservationReceipts / accessible
observation components.

## Behavioral Reconstruction language

Behavioral Reconstruction reports recorded evidence and explicitly labeled
**derived** associations (approach / withdrawal candidates, geometric relations,
motor reversals, sensorimotor trend-reversal candidates). It does **not**
establish recognition, communication, intention, wanting, deliberate navigation,
or learning.

Physical signaling is field physics, not communication.
Distance reduction is not seeking.
Terrain-assisted displacement is not intentional terrain exploitation.

## Analyze Current near the evidence frontier

Paused Analyze Current can report fewer complete O→D→M→C chains than TickStories
when ObservationReceipts (and sometimes DecisionReceipts) are not yet durable at
the last ticks of the cutoff, while spine / motor / consequence IDs already
exist. A documented case: cutoff 5299 produced 10600 TickStories and 10568
complete chains; the 32 incomplete stories clustered on ticks 5284–5299
(`missing_observation`, some also `missing_decision`). Those ticks later existed
in the published archive after the run continued. Incomplete chains are
**not** filled in to force 100%.

## Legacy movement summaries

If pose/tick history is reconstructed but path metrics were not ingested, the
Analyzer reports **NOT AVAILABLE** rather than a misleading numeric zero for
distance / path length / unique cells.

## Save & Stop

Save & Stop is asynchronous. Failure should leave live simulation state
available for retry. Recoverable disk-full (ENOSPC) is tested by fault injection,
not by filling the real disk.

## Platform verification

Linux Observer bootstrap/launch is the environment used for this public packaging
validation. macOS and Windows launchers are shipped and statically audited;
they were not natively executed in this packaging environment.
