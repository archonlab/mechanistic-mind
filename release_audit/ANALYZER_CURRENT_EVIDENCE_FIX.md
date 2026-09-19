# Analyzer Current evidence-source fix

## Root cause
Analyze Current used live-frame Visual Forensics only (`opticalTickFromLiveFrame`),
while Run explicit analysis used `/api/analysis/evidence` → `scientific_rows`.

## Fix
- Analyze Current now loads the current-run evidence package (same path as explicit).
- Live-frame remains fallback only; historical metrics become NOT_AVAILABLE.
- refreshAux no longer continuously rebuilds analysis from live frames.

## Bundle
`web_dist` rebuilt → `index-AT9AOQ5R.js`

No scientific/runtime semantics changed.
