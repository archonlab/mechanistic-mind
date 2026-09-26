# Signal Forensics V2 × Composite Motor Forensics

**Marker:** `SIGNAL_COMPOSITE_FORENSICS_ACCEPTED`

## Authority

`ANALYZE CURRENT RUN` uses the same scientific evidence package as Analyzer:

- `scientific_meta.json`
- `scientific_timeline.jsonl`
- `scientific_events.jsonl`

Reference fixture (seed-17) is a **separate explicit button** only.

## Composite motor

When `action_source` contains `COMPOSITE` (or `motor_output` is present):

- schema = `COMPOSITE_MOTOR_V1` (authoritative)
- factorized domains reconstructed from legacy action + effector events
- control counts ≠ active effector ticks

Legacy single-slot runs remain `LEGACY_SINGLE_SLOT` without reinterpretation.

## Oscillatory episodes

Reconstructed from `osc_emit_active` / `osc_emit_remaining` transitions:

`EMISSION_START → ACTIVE_EMISSION → EMISSION_END`

Patterns: `OSC_PATTERN_001` … (no CALL/WORD/GREETING).

## Module

`mechanistic_mind/ui/psy_observer_web/signal_context/composite_signal_forensics.py`
