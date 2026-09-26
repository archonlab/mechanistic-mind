# Mechanism Control UI

## Authority

```
UI requested configuration
  → ResolvedMechanismConfig (backend)
  → pending / explicit Apply or LIVE intervention
  → runtime bind (set_mechanism / set_vision_radius)
  → run_preflight (CONFIGURED vs RUNTIME vs AVAILABLE [+ params])
  → READY | CONFIGURATION_MISMATCH
```

Frontend displays status; it is not scientific authority.

## Vision R1 / R2 / R3

| | |
|--|--|
| Default (new experiment) | **R3** |
| Public Beta cap | **R3** (`VISION_RADIUS_MAX=3`) |
| Meaning | Moore candidate neighborhood size only |
| LIVE API | `POST /api/vision/radius` `{radius:1\|2\|3}` |
| Apply API | `POST /api/experiment` with `vision_radius` |
| UI | Sensors → **VISION** strip (Enabled + R1/R2/R3 + Configured/Runtime/Status) |

LIVE radius changes update **both** resolved CONFIG params and runtime NFE.radius, then re-run preflight so READY means cfg R == rt R.

## Climate Ecology

Fresh-experiment default: **OFF**.

LIVE ecology presets may stamp `climate_ecology.enabled=True`. After LIVE ecology the session **re-applies resolved mechanism authority** (same as APPLY & RESET), so climate stays OFF unless the experimenter explicitly toggles it ON.

Historical MISMATCH (CONFIG OFF / RUNTIME ON) was a runtime/config sync bug, not intended baseline semantics.

## Control coverage regression

`tests/test_mechanism_control_ui_coverage.py` fails if an `EXPERIMENTER_CONFIGURABLE` mechanism loses its UI without an allowlisted `NOT_UI_EXPOSED_BY_DESIGN` reason.

## Artifacts

`results/mechanism_control_ui/`
