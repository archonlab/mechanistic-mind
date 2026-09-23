# Beta 3 bounded Analyzer

Objective: **same scientific information and reconstruction semantics**, with **bounded working memory**.

Longer runs should increase wall time and on-disk artifact size, not Observer RSS proportional to the full DecisionReceipt corpus.

## Old memory architecture

`GET /api/analysis/evidence` ran **inside the Observer uvicorn process**:

1. `iter_jsonl` materialized `scientific_timeline.jsonl` and `scientific_events.jsonl` as Python lists.
2. `RunEvidence.__init__` materialized every observation, **decision**, motor, consequence, and spine row.
3. `TickStory` kept references to full receipts (~32 KB mean decision lines).
4. `RelationshipGraph` stored a node per observation component per tick.
5. HTTP returned `scientific_rows` + `events` + reconstruction payload.

Dominant term: 1.90 GB decisions JSON → ~10–20 GB Python → OOM killer (PID RSS 15.4 GB).

## New memory architecture

```
JSONL (disk, unchanged)
  → one sequential compact scan (keep IDs, motor components, accessible prefixes, pose deltas)
  → compact TickStory list (no full PSC/SMC maps)
  → compact timeline/events joins (signal/contact only)
  → incremental episode machines over compact stories
  → SMC/HSS/etc. stream full decisions one line at a time (aggregates only retained)
  → artifacts JSONL/JSON on disk (not the live run dir)
  → HTTP summary + artifact paths
```

Isolation: `POST /api/analysis/jobs` starts `python -m mechanistic_mind.scientific_v3.analyzer_next.job` as a **subprocess**. Observer does not parse GB-scale receipts. Job failure cannot mutate the paused runtime. Progress: `progress.json` phases QUEUED/READING/RECONSTRUCTING/EPISODES/AGGREGATING/WRITING/COMPLETE/FAILED/CANCELLED.

Losslessness:

- Source JSONL is never truncated, renamed, or rewritten.
- Compact receipts keep fields used by O→D→M→C, episodes, joins, motor, pose, signals, vision flags.
- Full DecisionReceipt maps remain on disk; Analyzer does not discard them from the archive.
- Relationship **counts** remain complete; resident graph is a sample (export already capped).

## Trajectory × geometry

`analysis_derived_trajectory.jsonl` per agent per tick (where recorded):

position, velocity, selected action, motor components, head orientation, signal emit/receive, other-agent distance, other-agent visible, PSC path/source/candidate id, `TERRAIN_ASSISTED_DISPLACEMENT` **candidate** (pose_delta vs locomotion axis; not intent).

`season_geology_reference`: **NOT_RECORDED_PER_TICK**.

Historical terrain: generator is seed-based (`terrain_seed`, `TERRAIN_GENERATOR_VERSION`). Per-tick height maps are **not** in scientific_timeline. Climate/season can be reconstructed from world seed + tick + ecology config if those configs are known. Overlaying the **final** terrain field on an old trajectory is valid only if the mesh did not evolve; seasonal T is time-varying. Status: **PARTIAL**.

## Semantic oracle

`tests/test_beta3_bounded_analyzer.py`: lazy vs materialize `reconstruction_summary` counts; two `build_behavioral_reconstruction` passes match tick/ODMC/episode/join counts; job writes outside source dir; HTTP summary omits bulk rows.
