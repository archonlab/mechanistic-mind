# MM 1.0 Tiktaalik — Public Beta 3.1 release notes

**Release name:** `MM-1.0-Tiktaalik-Public-Beta-3.1`  
**Tag candidate:** `v1.0.0-tiktaalik-public-beta-3.1`

Tiktaalik Public Beta 3.1 is the current two-agent public cut of Mechanistic Mind
1.0. Frozen Public Beta 3 remains an untouched prior package. Beta 3.1 does
**not** introduce Beta 4 mechanisms.

## Scientific disclaimer

Mechanistic Mind is an experimental artificial-life / mechanistic simulation
environment. Observed behavioral structure should be treated as experimental
evidence requiring controlled comparison and ablation, not as evidence of
human-like cognition or subjective experience.

Do not market observed behavior as proof of consciousness, intention,
recognition, communication, language, attention, learning, intelligence,
social understanding, or goal-directed seeking.

## What Beta 3.1 adds relative to Public Beta 3

- Canonical public experiment preset **TIKTAALIK_BETA31** (two-agent, factorized
  composite motor as the public default motor-resolution, experimental 4.26–4.28
  contextual/prospective organism layer on, PSC and Climate Control off unless
  the user enables them).
- Restored historical predictive control for **factorized** motor side channels
  (NECK, OSC, PUSH) so retained / historically supported composite components
  can be applied together with locomotion.
- Cognition production wiring closure for the sensorimotor-consequence /
  historical-selection / contextual stack already present in the Beta 3.1
  mechanism set.
- Physical oscillatory signaling (OSC): emission and reception as field physics,
  not messages and not communication.
- Surface / spatial vision work included in this cut (Observer vision controls
  and near-field optical mapping already in the Beta 3.1 tree).
- Observer **composite motor action display** (current-frame final applied
  composite, including NECK / OSC / PUSH tokens when present).
- Observer **RECENT** side-channel HUD: ~1 s wall-clock visibility of recently
  applied non-neutral NECK / OSC / PUSH components, distinct from the current
  primary badge.
- Performance / memory work already completed for long Observer runs in this
  tree (bounded Analyzer, PE history / cold archive, crash-safe checkpointing
  where packaged).
- Persistence / restore smoke coverage used as a release gate, not a claim of
  perfect long-biography bit-identity in every UI mode.
- Mechanism-integrity validation of the canonical Beta 3.1 configuration.

Beta 3 contents remain: TwoAgentRuntime, articulated body/head, near-field
vision, physical signaling (field deposits), terrain / site mechanics,
predictive mechanisms, PSC (user-toggleable), Scientific V3, Analyzer Next,
Psy Observer Web, Save & Stop / restore.

## Recommended first-run workflow (Beta 3.1)

1. Apply **MM 1.0 — Tiktaalik Beta 3.1** (`TIKTAALIK_BETA31`) with
   **Apply & Reset World** before Play (two-agent runtime).
2. Leave PSC **OFF** and Climate Control **OFF** for the baseline biography.
3. Public preset motor-resolution is **LOCO_FACTORIZED** (factorized composite).
   Do not silently substitute a different resolution unless you intend that
   experiment.
4. Play. Footer **primary** badge is the current published composite motor.
   **RECENT** lists recently applied NECK / OSC / PUSH components for about one
   second of wall-clock time; it is not the current motor.

The frozen Public Beta 3 workflow (OBSERVED_COMPOSITE + PSC enable ~tick 1000)
remains documented in `RELEASE_NOTES_BETA3.md` for that package.

## Analyzer / evidence

Scientific V3 records Observation, Decision, Motor, and Consequence receipts.
Analyzer Next reconstructs TickStories from that evidence. FULL coverage
requires successful consumption of history, not merely metadata that rows exist.

See `KNOWN_LIMITATIONS.md` for Analyzer / V3 gaps that remain in this cut,
including missing V3 `domain_sources`, Analyzer HOLD / RETAINED vs variation
gaps, the partial instrumental EMIT bridge, `NECK_HOLD` `_pick_supported`
behavior, WORLD display flash, and default single-agent `GET /api/model` HTTP
500 (`PhysicalSystemRuntime` has no `mechanism_snapshot`).
