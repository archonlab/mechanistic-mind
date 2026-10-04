# Acanthostega Beta 4.0 — Analyzer progress, heartbeat, frozen snapshot

## Capability

Visible, reconnectable, snapshot-bounded Analyzer progress (`ANALYZER_JOB_PROGRESS_V1`) over frozen existing evidence (`ANALYZER_EVIDENCE_SNAPSHOT_V1`).

## User-facing

- Prominent WORKING / COMPLETED / FAILED / CANCELLED state
- Phase N/M, processed/total, elapsed, heartbeat age, rate
- Frozen snapshot tick boundary (runtime may continue without growing the denominator)
- Compact expandable operational Analysis log (not scientific evidence)
- Cooperative Cancel analysis
- Revisit / refresh reconnects the same job id

## Authority

Analyzer remains read-only. It does not pause/advance/reset/apply the simulation, mutate saved evidence, replay physics/cognition, or create scientific samples.

## Sibling package

`Release/MM-Acanthostega-Beta-4.0-Analyzer-Progress/` (does not overwrite FPV-Hearing).
