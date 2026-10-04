# ACANTHOSTEGA_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE_V1

## Identity

| Field | Value |
|-------|-------|
| Public preset | `ACANTHOSTEGA_BETA4_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE` |
| Parent | `ACANTHOSTEGA_BETA4_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT` |
| Mechanism | `vertical_terrain_landing_contact_response` |
| Profile | `VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE_V1` |
| Receipt | `VERTICAL_TERRAIN_LANDING_V1` |
| Architecture stage | `FREE_SPACE_V1B_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE` |
| Model line | `ACANTHOSTEGA` |

## Seam

When ON, FGG `integrate_vertical_entity` **bypasses** the legacy inelastic clamp and runs:

`plan → contact fact → inelastic response (e=0) → atomic commit`

When OFF (parent V1A): legacy clamp unchanged. Never both.

## Geometry

- `Z_SEGMENT_AT_COMMITTED_XY`
- Contact point `(x, y, support_z)` base/feet
- Normal `(0,0,+1)`
- Linear TOI; optical radius unused
- Limitation: support sampled at committed xy (not swept `h(x(t),y(t))`)

## Episodes

Key `{entity_kind}:{entity_id}|terrain` — BEGIN / PERSIST / END.  
Rest = PERSIST (no impulse). Re-contact after END → new episode id.

## Response

- Terrain infinite mass; `j = -m_eff · vz`; `vz→0`; `z→support_z`
- Horizontal velocity unchanged
- Held load counted once when EHL ON
- No rebound; no impact sound
- Dissipated KE ledgered for later acoustics

## Next

`VERTICAL_IMPACT_ACOUSTIC_EMISSION_V1`
