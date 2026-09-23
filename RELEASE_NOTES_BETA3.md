# MM 1.0 Tiktaalik — Public Beta 3 release notes

**Release name:** `MM-1.0-Tiktaalik-Public-Beta-3`

Tiktaalik Public Beta 3 is the current two-agent public cut of Mechanistic Mind
1.0. It packages the Observer, Scientific V3 evidence, Analyzer Next, Save &
Stop / restore, and the existing Beta 3 mechanism set. It does **not** introduce
Beta 4 mechanisms.

## Scientific disclaimer

Mechanistic Mind is an experimental artificial-life / mechanistic simulation
environment. Observed behavioral structure should be treated as experimental
evidence requiring controlled comparison and ablation, not as evidence of
human-like cognition or subjective experience.

Do not market observed behavior as proof of consciousness, intention,
recognition, communication, learning, or goal-directed seeking.

## What Beta 3 includes

- TwoAgentRuntime (two physical bodies / two cognitive agents)
- Articulated body and head
- Physical near-field vision
- Physical signaling (field deposits, not messages)
- Heterogeneous terrain / site mechanics
- Predictive mechanisms, predictive compression / equivalence / relevance
- Temporal prediction / prospection and prospective composition
- Prospective Scenario Competition (PSC), user-toggleable
- Scientific V3 evidence: Observation → Decision → Motor → Consequence
- Analyzer Next / bounded-memory analysis, TickStories, Behavioral Reconstruction
- Psy Observer Web
- Save & Stop / restore (streamed compact snapshot, atomic publish, async job)

## Recommended first-run workflow (PSC)

This is the recommended Beta 3 **baseline workflow**, not a claim that tick 1000
is a biologically privileged boundary.

1. Apply the **MM 1.0 — Tiktaalik Public Beta 3** experiment preset
   (two-agent; normal mechanisms on; PSC off; Climate Control off).
2. **Before Play**, go to **Experiment → Predictive** and select
   **OBSERVED_COMPOSITE**. Select this even though PSC itself starts disabled,
   so enabling PSC later does not require interrupting the biography merely to
   change motor-resolution.
3. Start with PSC **OFF**. Climate Control remains **OFF** unless you
   intentionally want a climate intervention experiment.
4. Allow about **1000 simulation ticks** of initial history with PSC disabled.
   Why PSC begins off: the recommended run first allows a history of physical /
   sensorimotor consequences to accumulate before prospective scenario
   competition is enabled.
5. At approximately tick 1000, enable Prospective Scenario Competition **without
   resetting** history, cognition, or body. Continue the same biography.

Low-level `CognitionConfig.psc_motor_resolution` remains `LOCO_FACTORIZED` for
scripts that construct cognition directly. The public Observer preset is the
recommended first-run configuration.

## Analyzer / evidence

Scientific V3 records Observation, Decision, Motor, and Consequence receipts.
Analyzer Next reconstructs TickStories and behavioral episodes from that
evidence. FULL coverage requires successful consumption of history, not merely
metadata that rows exist.
