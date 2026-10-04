# Body/Object Contact Impulse — Calibration

Defaults: `approach_epsilon=1e-9`, `max_contact_impulse=2.0`, `penetration_slop=0.02`,
`max_position_correction=0.35`, `e_min=0.0`, `e_max=0.85`, `impulse_threshold=1e-12`,
body mass default `1.0`, object mass canonical `1.0`, neutral compliance `0.5` → `e=0.425`.

| scenario | approach | j | e | Δv_body | Δv_obj | reason | sound |
|---|---|---|---|---|---|---|---|
| equal mass head-on approach | yes | >0 | 0.425 | along -n | along +n | APPROACHING | False |
| separating | no | 0 | — | 0 | 0 | SEPARATING | False |
| resting / persist no approach | no | 0 | — | 0 | 0 | RESTING_NO_APPROACH | False |
| high compliance (0.75) | yes | lower e | 0.2125 | smaller bounce | | APPROACHING | False |
| low compliance (0.25) | yes | higher e | 0.6375 | larger bounce | | APPROACHING | False |
| invalid mass | — | 0 | — | 0 | 0 | INVALID_MASS | False |
| below threshold | tiny | 0 | — | 0 | 0 | BELOW_IMPULSE_THRESHOLD | False |
| max clamp | yes | =2.0 | | | | APPROACHING (clamped) | False |
| contact-fact-only preset | — | n/a | — | unchanged | unchanged | (no response module) | False |

SCIENTIFIC VALIDATION — NOT RUN (unit probes only; budget ≤250 ticks).
