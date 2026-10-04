# Acanthostega Beta 4 — PSC schedule + Eye Hearing release repair

## Scope

Release-facing repair only: PSC schedule visibility/authoritative Apply of MANUAL, TwoAgent readback of activation receipts, and Eye dock Hearing researcher-playback simplification.

No physics, cognition, organism hearing, or scientific evidence mutation. No Beta 4.1.

## PSC

- Canonical default remains OFF @ tick 0 with auto-enable @ 1000 and Observed Composite.
- Runtime `_maybe_auto_enable_psc` unchanged.
- `psc_off_ticks_status` now resolves slot-0 authority on TwoAgentRuntime.
- Experiment PSC panel shows **CURRENT RUNTIME** first from the live overlay (ON/OFF, enabled-at tick, transition count, armed/withhold). **NEXT RUN** is labelled draft (initial OFF / auto-enable / motor resolution) and never implies that the current run is OFF. Apply-time values are **APPLIED CONFIGURATION · initial / frozen**. OBSERVED_COMPOSITE is experimental motor status, not PSC ON/OFF.
- `merge_canonical` accepts explicit `psc_off_ticks: null` as MANUAL.

## Eye Hearing

- Compact Eye primary: Listen World / Listen Agent / Volume.
- Terminology: PLAYBACK LIVE|STOPPED, TRUE ZERO, UNAVAILABLE.
- Mutual exclusion of World vs Agent playback preserved and disclosed.
- Master volume is user preference only.
- Closing Eye Hearing suspends researcher playback; engines stay mounted for keepalive.
- Dual exact FPV delivery remains dock-owned during Hearing (see Dual FPV × Hearing lifecycle repair).
