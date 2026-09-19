# Vision UI packaging fix

## Root cause: B

Development and Public Beta **source** already contained LIVE R1/R2/R3 controls
(`NearFieldSensorPanel.tsx` + `App.tsx` wiring) and backend `/api/vision/radius`.
The packaged **web_dist** was stale (pre-radius-UI build) and lacked the buttons
and `/api/vision/radius` client call.

## Fix

- `vite build` from frozen lab `web/psy-observer`
- Replaced `web_dist` only (new `index-DitmQLzW.js` / `index-DYHGhhw9.css`)
- No scientific/runtime semantics changed; no R4

## UI location

Sensors → Vision → Authority (LIVE), between Illumination cycle and FOV /
Candidates (Moore) readouts:

- R=1 · max 8 cells
- R=2 · max 24 cells
- R=3 · max 48 cells
