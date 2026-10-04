# ACANTHOSTEGA_VERTICAL_IMPACT_ACOUSTIC_EMISSION_V1

## Identity

| Field | Value |
|-------|-------|
| Public preset | `ACANTHOSTEGA_BETA4_VERTICAL_IMPACT_ACOUSTIC_EMISSION` |
| Parent | `ACANTHOSTEGA_BETA4_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE` |
| Mechanism | `vertical_impact_acoustic_emission` |
| Profile | `VERTICAL_IMPACT_ACOUSTIC_EMISSION_V1` |
| Receipt | `VERTICAL_IMPACT_ACOUSTIC_EMISSION` |
| Architecture stage | `FREE_SPACE_V1C_VERTICAL_IMPACT_ACOUSTICS` |
| Model line | `ACANTHOSTEGA` |

## Causal chain

```
unsupported fall
→ vertical terrain contact fact (V1B)
→ inelastic landing response (committed)
→ measured dissipated vertical KE
→ physical acoustic emission (this slice)
→ existing LPS propagation
→ ordinary organism auditory bands
```

## Authoritative source

Only a **committed** V1B landing response with:

- `response_applied`
- approaching impact
- `impulse_magnitude > impulse_epsilon` (default `0.04`)
- `dissipated_energy > energy_epsilon` (default `1e-12`)
- finite positive effective mass
- valid contact point
- response key not already processed

Contact fact alone, PERSIST, END, correction-only, restore replay, support refresh,
newborn/release transition, invalid mass/energy, and below-threshold events produce
explicit researcher SILENT outcomes.

## Energy

```
E_diss = authoritative landing response dissipated_energy
E_emit = clamp(acoustic_coupling * E_diss, 0, max_emitted_energy)
```

Defaults (aligned with body/object impact acoustics dissipation path):

- `acoustic_coupling = 1.0`
- `max_emitted_energy = 2.5`

No second KE/work debit. No agent credit. No global conservation claim.

## Spectrum / source

- `UNIFORM_BROADBAND_V1` via shared `broadband_bands`
- Source position = landing `contact_point` `(x, y, support_z)`; z in provenance
- Deterministic source id `vti:{response_key}:{tick}`
- LPS remains horizontal xy transport (limitation documented)

## Tick seam

FGG propose → V1B plan/fact/response/commit → **V1C consume** → other contact/acoustic producers → LPS `step_end_of_tick` ×1

## Non-goals

No human playback, semantic SFX, material timbre, rebound, landing-physics changes,
3D acoustics, or Observer speaker output.

## Next

`RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION_V1`
