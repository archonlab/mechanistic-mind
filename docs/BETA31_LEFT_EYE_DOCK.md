# Beta 3.1 left Tiktaalik Eye dock

Observer UI only. Canonical sampler, cognition, and scientific evidence are unchanged.

## Layout

```
[nav rail] [TIKTAALIK EYE DOCK] [WORLD] [right Inspector / Sensors]
```

The nav rail is unchanged. WORLD is always the center map. Opening the Eye dock reduces **width**, not height.

States: CLOSED (~22 px EYE handle) · NORMAL (~400 px) · WIDE (~600 px). Drag the right edge of the dock to resize (320–680 px). Preference key `mm.observer.eyeDock` in localStorage.

Removed: giant bottom Eye overlay; WORLD-as-Eye-tab.

Dock toolbar: TIKTAALIK EYE · A0 · A1 · SPLIT · SENSOR SPACE · FPV · Preview OFF|SNAPSHOT|2 FPS|5 FPS|PER_TICK · FPV OPTICAL FIELD | CONTRIBUTION.

SPLIT stacks AGENT 0 then AGENT 1 vertically. Dock body scrolls; WORLD does not scroll because Eye content is large.

SENSOR SPACE: LEGACY LEFT/FORWARD/RIGHT; spatial modes A0–A4 (exo + compact C0/C1/C2). SAMPLE DEBUG is a collapsible details block (RESEARCHER-ONLY · NOT AGENT-ACCESSIBLE AS STRUCTURED FIELDS).

## Demand-driven capture

`TiktaalikEyePanel` mounts only when the dock is not CLOSED. Unmount POSTs `{rate: OFF, fpv: false}`. Preview OFF does not request FPV receipts. Spatial Vision itself stays a mechanism control on Sensors.

## Files

- `web/psy-observer/src/components/TiktaalikEyeDock.tsx`
- `web/psy-observer/src/components/TiktaalikEyePanel.tsx`
- `web/psy-observer/src/components/TiktaalikFpvField.tsx`
- `web/psy-observer/src/chrome/WorldPane.tsx` (bottom panel already gone)
- `web/psy-observer/src/App.tsx` (dock after ControlDevice)
- `web/psy-observer/src/observer/stores.ts`
- `web/psy-observer/src/styles/app.css`
- `mechanistic_mind/ui/psy_observer_web/tiktaalik_eye.py` (compact spatial surface bins in the **diagnostic** payload only)
- `tests/test_beta31_left_eye_dock.py`

web_dist rebuilt: `assets/index-C_aeySaX.js`.

## Validation

Fresh Observer **:8782** (not the live :8768 experiment). Live :8768 stayed RUNNING (tick advanced ~6500→7600 during this work).

Browser: CLOSED handle → NORMAL/WIDE → A0/A1/SPLIT → SENSOR SPACE/FPV → OPTICAL FIELD → 2 FPS. SPLIT showed two FPV grids with **×** occlusion markers and **A0–A4**. Right Sensors remained open (OCCLUSION, R=3). CLOSE restored the EYE handle; `/api/observer/tiktaalik-eye` on :8782 became `rate=OFF, fpv=false`. :8768 Eye status stayed `2FPS`/`fpv=true`.

Pytest: CLOSED vs OPEN and Preview OFF vs 2FPS keep observations/actions/poses/metrics identical.

Screenshot tool failed (no image bytes); interaction snapshot is the visual evidence.
