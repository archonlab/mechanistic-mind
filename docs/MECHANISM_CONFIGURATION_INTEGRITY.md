# Mechanism Configuration Integrity

## Principle

A checkbox is not scientific evidence that a mechanism existed.
A saved configuration is not scientific evidence that a mechanism existed.
A mechanism is considered active for a run only when the constructed runtime verifies it.

## Authority

Backend resolved configuration is the single authority:

```
requested / preset / explicit overrides / fresh defaults
  → RESOLVED MECHANISM CONFIG
  → stamp PhysicalSystemConfig
  → construct runtime
  → bind (set_mechanism + world installs)
  → PREFLIGHT (CONFIGURED vs RUNTIME vs AVAILABLE)
  → runtime_mechanism_manifest (once, before tick 1)
  → scientific run
```

Frontend displays status; it must not be the scientific authority.

## Fresh-experiment defaults

All **normal** current mechanisms **ON**, except:

| Mechanism | Default |
|-----------|---------|
| Climate Ecology (`spatiotemporal_climate_ecology`) | **OFF** |
| Experimental cognition adapters | **OFF** |

Includes **Physical Oscillatory Signaling** (`oscillatory_signaling`) ON.
Vision Moore radius default for new experiments: **R3**.

Resource Ecology A/B remain **ON** independently of Climate.

See `mechanism_configuration.fresh_experiment_default_map()` and `mechanism_catalog()`.

## Precedence

1. Explicit user / payload values  
2. Migrated defaults for missing newly introduced fields (when fresh defaults apply)  
3. Fresh NEW_EXPERIMENT defaults  

Legacy explicit OFF remains OFF.

## Preflight

Before tick 1 of every scientific run (`play` / `step`):

- Compare configured vs actual runtime for every mechanism
- Sensor availability = capability (zeros are valid)
- Action availability = registration (usage not required)
- Status `PREFLIGHT_FAILED` → refuse start; no scientific history

## Runtime mechanism manifest

Written once at successful preflight into scientific metadata.
Telemetry references the fingerprint; does not repeat the full manifest every tick.
LIVE interventions after t=1 are separate intervention records.

Manifest `params.motor_control_schema` is `COMPOSITE_MOTOR_V1` when
`cognition.composite_motor` is enabled (default). Preflight also verifies
composite motor routing availability (locomotion / neck / oscillator / PUSH
components when those mechanisms are ON; sensors must not occupy action space).

See `docs/COMPOSITE_MOTOR_CONTROL.md`.

## LIVE toggles

Still safe interventions: update runtime → re-verify → provenance.
UI must show MISMATCH if configured/runtime disagree.

## Original Vision bug

**Cause:** APPLY & RESET WORLD rebuilt BASELINE with vision package `mode=OFF` while the Observer UI kept a stale mechanisms list showing Vision ON. Only the LIVE OFF→ON path called `set_mechanism`, which forces `mode=EXPERIMENTAL` and installs `surface_response`.

**Fix:** Resolve + stamp + bind + preflight on every new runtime; refresh UI from runtime snapshot; distinguish CONFIGURED / RUNTIME / AVAILABLE.

## Module

`mechanistic_mind/physical_system/mechanism_configuration.py`
