# PSC Motor Resolution — Observer UI exposure

UI/integration only. Backend production modes unchanged.

## Location

- **MM Control → Experiment → Predictive / PSC**
  - PROSPECTIVE SCENARIO COMPETITION ON/OFF
  - **PSC MOTOR RESOLUTION** segmented control
  - Related: SENSORIMOTOR CONSEQUENCE MODEL, HISTORICAL SENSORIMOTOR SELECTION
- Also compact control on **Runtime mechanisms** card
- MECHANISMS panel shows mode line (not ON/OFF): `PSC MOTOR RESOLUTION` + label

## Backend

- `GET` / `POST` `/api/config/psc-motor-resolution` body `{ "mode": "LOCO_FACTORIZED" | "OBSERVED_COMPOSITE" }`
- Authoritative state from cognition config / GET
- Hot-toggle: history_reset=NO, smc_reset=NO, body_reset=NO, cognition_reset=NO
- `/api/mechanisms` includes `psc_motor_resolution` field
- EMBODIED PREDICTION diagnostic: `PRODUCTION MODE` + optional SHADOW block

## Defaults / Reset

- Fresh experiment / `apply_experiment`: **LOCO_FACTORIZED**
- OBSERVED_COMPOSITE remains EXPERIMENTAL and is never default
- Motor resolution is independent of PSC enabled state (READY when PSC OFF, ACTIVE when ON)

## Visibility

- Control stays visible under OBSERVER detail **MINIMAL / NORMAL / FULL**
- Detail presets may defer diagnostics only

## Verification artifacts

`results/psc_motor_resolution_ui/` screenshots + `tests/test_psc_motor_resolution_observer_ui.py`

Served Observer (this verify run): `http://127.0.0.1:8770`
