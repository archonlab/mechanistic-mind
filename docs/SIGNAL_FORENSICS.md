# Signal Forensics (Observer-only)

Physical signal history analysis for Mechanistic Mind / Tiktaalik.
Informal nickname “Tiktaalik Translator” means **physical signal forensics**, not language translation.

## Scientific purpose

Reconstruct **physical signal episodes** from the authoritative scientific evidence package:

- emission → shared field contribution → reception (where provenance supports it)
- contact-triggered vs non-contact field interaction
- temporal relations among first cross-agent contribution, first optical body exposure, first contact
- PRE/POST measurable deltas with matched no/low-signal controls

## Explicit non-claims

| Claim | Status |
|-------|--------|
| Physical signal = message | **FALSE** — not established |
| Emission = intentional emission | **FALSE** |
| Reception = interpretation | **FALSE** |
| Temporal association = causal link | **FALSE** |
| Physical interaction = communication | **FALSE** |
| Reception → cognition | **NOT_ESTABLISHED** unless a controlled analysis proves more |

No MESSAGE / LANGUAGE / MEANING / INTENT / SENDER–RECEIVER psychological roles enter cognition.

## Oscillatory physical signaling (alongside FIELD_A/B)

Fresh runs may also include banded `OSC_BANDS` with agent-accessible `osc_l_*` / `osc_r_*`.
Analyzer section: `summarize_oscillatory_signaling` — physical patterns only
(`SPECTROTEMPORAL_PATTERN_*`). Reception→meaning remains **NOT_ESTABLISHED**.
Legacy FIELD_A/B evidence remains separately analyzable.
See `docs/PHYSICAL_OSCILLATORY_SIGNALING.md`.

## Evidence authority

| Path | Role |
|------|------|
| `ObserverSession.scientific_evidence()` | **Authoritative** current-run package (same as Analyzer / Visual Forensics) |
| LIVE signal buffer (`signal_context_interpretation`) | Bounded **current window only** — not historical authority |
| seed-17 published run | **REFERENCE FIXTURE** — demos / regression only |

Signal Forensics must **not** maintain a competing historical authority.

Desired routing:

```
CURRENT RUN → SCIENTIFIC EVIDENCE PACKAGE → Analyzer
                                          → Signal Forensics
```

## Current-run routing

- Primary API: `GET /api/signal-context/current` → `signal_forensics_current_run`
- Uses `scientific_evidence(cutoff_tick=…)` rows + events
- Labels `analysis_source: CURRENT_RUN`
- Displays cutoff tick, telemetry schema (`V1_FULL` / `V2_TIERED`), coverage, RUNNING/FINAL
- User-triggered only — **not** attached to ordinary LIVE Observer refresh

Reference path (optional):

- `GET /api/signal-context/run/{run_id}?reference=true`
- UI button: **REFERENCE FIXTURE: seed-17**
- Labels `analysis_source: REFERENCE_FIXTURE`

## LIVE vs historical

| Stream | Meaning |
|--------|---------|
| LIVE episodes | Episodes currently in the bounded Observer buffer |
| Historical episodes | Episodes reconstructed from scientific history through cutoff |

`LIVE episodes: 0` **never** implies `historical episodes: 0`.

## Episode definition

Unchanged from `group_signal_episodes`: contiguous reception clusters per receiver/channel from `PHYSICAL_SIGNAL_*` events (plus related scenario events where present). Peak magnitude, attribution, cross-agent contribution fraction, and trigger composition (`body_motion` / `body_contact`) come from event evidence.

## Causal provenance

| Edge | Classification |
|------|----------------|
| emission → field contribution → reception (parent emission ids) | **CAUSALLY_LINKED** when `contributing_emissions_this_tick` supports it |
| reception → later cognition / action | **NOT_ESTABLISHED** (temporal association only unless matched-control analysis strengthens a candidate) |

## Matched association semantics

**Label:** `CANDIDATE ASSOCIATION` (not causal proof).

- **Controls:** `find_matched_controls` — same receiver fingerprint (region cell, action, action_source, contact, speed/work bins); exclude ±30 ticks around the episode; prefer no/low signal ticks.
- **Score:** region +2; action / action_source / contact / speed_bin +1 each; GOOD when score ≥ 4.
- **Verdict:** episode PRE→POST deltas compared to control rates; `MATCHED_ASSOCIATION` means statistical candidate only.

## Pattern semantics

`cluster_patterns`: reproducible PRE + SIGNAL channel/cross-agent/contact structure with similar POST deltas across ≥3 episodes.

**Not** words, symbols, messages, or meanings. Zero patterns ⇒ show zero.

## Coverage

Follows Analyzer package coverage when available: `FULL` / `CONTIGUOUS` / `SPARSE` / `PARTIAL` / `UNAVAILABLE`.
Truncation of rows/events for performance marks coverage `SPARSE`. Absence of structure under incomplete coverage is not evidence of absence.

## V1 / V2 support

| Schema | Support |
|--------|---------|
| `V1_FULL` | Supported (full tick rows + events) |
| `V2_TIERED` | Supported — signal events preserved by V2 compactors; optical via `vision_optical` |

Equivalence gates: episode count, first cross-agent / optical / contact ticks, channel classification where V2 preserves the fields.

## Optical / contact authorities

| Measurement | Authority |
|-------------|-----------|
| First body optical exposure | `vision_optical.body_exposure` (same as Visual Forensics) |
| First physical contact | scientific timeline `contact` |
| Inter-agent distance | WRAP_PERIODIC minimum-image from body `(x,y)` when available |

Approach / retreat metrics are **geometry only** (APPROACH / RETREAT / NO_CLEAR_CHANGE) — not attraction or social intent.

## Performance / memory

- Analysis may be O(N) **when explicitly invoked**.
- Must **not** recompute full history on every LIVE refresh.
- Reuses Analyzer’s evidence package load; does not invent a second full-history copy beyond the package already materialized for the request.
- Optional caps: `max_timeline_rows`, `max_events` (document SPARSE if truncated).
- Future Analyzer streaming is out of scope; do not worsen memory by duplicating packages.

## Limitations

- Reception → cognition remains NOT_ESTABLISHED by default.
- Matched associations are candidates, not causal proof.
- Patterns are statistical recurrence only.
- Distance / approach metrics require trajectory rows; unavailable when missing.
- Reference fixture remains for regression; never masquerades as current run.

## Tests / artifacts

- `tests/test_signal_forensics_current_run.py`
- `results/signal_forensics/current_run_integration/`
