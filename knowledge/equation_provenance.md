# Equation provenance

- X absolute mode: `X' = clip(0.70 X + 0.25 (B - 0.5), -1, 1)`; source `mechanistic_mind/body/physical_transduction.py`; audited in 4.64 artifacts.
- Passive field coupling: `fatigue += 0.0002*T`; `hydration += -0.0001*H`; source `mechanistic_mind/world_engine/background_fields.py`; tested at 4.63 and audited in 4.64 artifacts.
- Physical threshold: 0.60 in 4.61/4.62 reports; live maxima R0 0.0659, R1 0.4629, R3 0.4622 in 4.62.

For historical equations not recoverable from versioned source/result artifacts, use `HISTORICAL_EQUATION_NOT_RECOVERABLE`; current code is not silently projected backward.
