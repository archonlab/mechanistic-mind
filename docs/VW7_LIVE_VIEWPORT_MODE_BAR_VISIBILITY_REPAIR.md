# VW7_LIVE_VIEWPORT_MODE_BAR_VISIBILITY_REPAIR

## Summary

The VW7 MAP / VOLUME controls already existed in source, bundle, and DOM, but `.sim-map-host` absolute-fill CSS painted the WorldMap canvas over the mode bar. This repair introduces a dedicated `.world-viewport-content-host` so absolute fill applies only below a flex `none` mode bar.

## Changes

- `web/psy-observer/src/chrome/WorldPane.tsx` — wrap map/volume in `world-viewport-content-host`; keep single `volumeWorkspace` authority; aria-pressed on buttons.
- `web/psy-observer/src/styles/app.css` — flex column outer pane; absolute fill scoped to content host.
- `web/psy-observer/src/chrome/WorldPane.entrypoint.test.ts` — layout separation + RUN/INSPECT wiring assertions.
- Rebuild `mechanistic_mind/ui/psy_observer_web/web_dist` → `index-iN-BjcUn.js` / `index-CwkRjY8O.css`.

## Non-changes

No VW1–VW6 physics, no second 3D view, no new preset/mechanism, no simulation campaign.

## Evidence

See `results/vw7_live_viewport_mode_bar_visibility_repair/`.

## Next seam

`FIRST_HABITABLE_VOLUMETRIC_RUN_V1` (not started here).
