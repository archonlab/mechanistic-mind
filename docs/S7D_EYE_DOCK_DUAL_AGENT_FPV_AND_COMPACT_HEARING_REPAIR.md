# S7D Eye Dock Dual-Agent FPV and Compact Hearing Repair

**Seam:** `S7D_EYE_DOCK_DUAL_AGENT_FPV_AND_COMPACT_HEARING_REPAIR`  
**Schema:** `OBSERVER_EYE_DOCK_DUAL_AGENT_SENSORY_MONITOR_V1`  
**Authority:** Researcher display over existing per-agent O4/O5 and audio state.

## Summary

The auxiliary Eye dock beside World now presents simultaneous compact FPV for active agents using exact existing O4 `latest_by_agent` traces, with settings and progressive disclosure below. Hearing is settings-first with collapsed scientific detail. Central FPV Vision destination remains the deep-inspection authority.

## Delivery

- Backend: `observer_payload(..., include_latest_by_agent=)` publishes `latest_exact_by_agent` (read-only copies).
- Gating: Observer product `eye_dock_dual_fpv` — enabled while the Eye dock is open (Vision or Hearing); not Vision-subtab-gated. Hearing playback must not narrow Dual FPV delivery. See `docs/ACANTHOSTEGA_BETA4_DUAL_FPV_HEARING_LIFECYCLE_RELEASE_BLOCKER_REPAIR.md`.
- Frontend: `EyeDockVisionWorkspace` dual cards; `OrganismReceptorGroundedFpvPanel` `chrome=compact` + `externalTrace`.
- Selected agent: passive updates never change selection; card click / Open detailed FPV use shared authority.
- Hearing: compact hierarchy; LPS ≠ OATT; single engine keep-alive.

## Non-goals

No Beta 4.1, no second perception/audio engine, no FPV projection change, no public-model default change, no S6 mutation.
