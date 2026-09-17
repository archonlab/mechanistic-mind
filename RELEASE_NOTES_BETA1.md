# Release Notes — Mechanistic Mind 1.0 Tiktaalik Beta 1

## Summary

First public Beta of **Mechanistic Mind 1.0 — Tiktaalik**, with **Psy Observer Web** as the primary observation interface.

## Capabilities (factual)

### Physical runtime
- Integrated planet/body loop with morphology, orientation, deformation
- Deformation work against a finite mechanical work reservoir
- Complementary environmental resources A/B and conversion accounting
- Endogenous motor drive and separate discrete action channel
- Explicit structured events for inspection

### Cognition (when enabled)
- Bounded prediction and compression stores
- Prospective scenario competition → selected action → physical bridge
- Honest NOT AVAILABLE / experimental labeling in the Observer

### Psy Observer Web
- Tabs: WORLD, AGENT, MIND, TIMELINE, EXPERIMENT, DATA, ANALYZE RESULTS, OVERVIEW
- Modes: LIVE, INSPECT, REPLAY
- Causal inspection (why this action / why it moved / shape change)
- Timeline with agent attribution
- Physical signal forensics (emit/receive; UNKNOWN/MIXED; not communication)
- Analyze Results summaries and Overview run catalog (local)
- Observer speed decoupling / MAX wall-clock mode (scientific ticks not skipped)
- Cross-platform launchers with **first-run bootstrap** of `.venv_psy_web` from `requirements-observer.txt` (Linux **NATIVE TESTED — PASS**; macOS **NATIVE TESTED — PASS**; Windows **STATICALLY VERIFIED — NOT YET NATIVELY TESTED**)

### Multi-agent
- `TwoAgentRuntime` experimental mode
- Independent agent inspection without peer mind fallback

## Classification

| Class | Examples |
|-------|----------|
| **CANONICAL** | Promoted integrated physical gears; Tiktaalik default path |
| **EXPERIMENTAL** | Physical signal fields; optional mechanism toggles |
| **NOT YET INTEGRATED** | Full Analyzer product surface; COMPARE RUNS |
| **DEFERRED** | WORLD INTERPRETER; Beta 2 UI/analysis expansions |

## Non-claims

This release does **not** claim consciousness, understanding, emotion, language, intentional communication, or AGI.

## Compatibility notes

- System Python ≥ 3.11 on PATH (used to create `.venv_psy_web` on first launch)
- First launch needs network once (`pip install -r requirements-observer.txt`); later launches reuse the environment
- Observer runtime deps: FastAPI / uvicorn / numpy (and peers listed in `requirements-observer.txt`)
- Production SPA shipped in `web_dist`; Node/npm not required for normal use; rebuild via `web/psy-observer` when changing the frontend

## Upgrade / next

Beta 2 work is explicitly deferred. Do not treat this notes file as a roadmap commitment.
