# Acanthostega Beta 4 — Dual FPV × Hearing lifecycle release-blocker repair

## Scope

Release-facing Observer lifecycle repair only: keep exact compact O4 Dual FPV for both agents continuously available while researcher Hearing playback runs.

No new sensory engines. No physics/cognition/protocol/fingerprint/evidence mutation. No Beta 4.1.

## Root cause

`eye_dock_dual_fpv` was enabled only when the Eye Vision subtab was active. Opening Hearing disabled the product, so live frames omitted `latest_exact_by_agent`. Mounted Vision cards fell back to selected-agent `latest` → one TRACE UNAVAILABLE.

## Repair

- Dual FPV interest is dock-open owned (Vision or Hearing).
- Client retains last-good per-agent exact traces across omission; never cross-copies agents.
- World-frame fragment cache keys include `eye_dock_dual_fpv`.
- Hearing local agent selector remains playback-local.

## Package

Sibling: `Release/MM-Acanthostega-Beta-4.0-FPV-Hearing/` (does not overwrite PSC-Hearing).

## Evidence

`results/beta4_dual_fpv_hearing_lifecycle_release_blocker_repair/`
