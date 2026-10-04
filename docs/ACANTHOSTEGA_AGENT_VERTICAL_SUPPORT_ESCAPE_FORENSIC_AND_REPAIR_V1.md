# ACANTHOSTEGA_AGENT_VERTICAL_SUPPORT_ESCAPE_FORENSIC_AND_REPAIR_V1

## Verdict
Production physics bug: V1B `SES_BELOW_SUPPORT_NO_FREE_LIFT` made unsupported below-support recovery unreachable, allowing unbounded negative Z after open-bottom empty VW1 free-fall (or any below-support pose) even when authoritative support exists.

## Repair
In `plan_landing`, unsupported deep/falling start-penetration recovers via `START_PENETRATION`. Shallow non-approaching SES free-lift lock remains. Empty VW1 open bottom preserved (no hidden floor).

## Evidence
See `results/acanthostega_agent_vertical_support_escape_forensic_and_repair_v1/`.

## Scientific status
S2/S4 packages show object (and some S4 body) vertical escape. Do not rewrite packages. S5/S6 vertical-sensitive claims require impact resolution before trusting prior closure. Not Beta 4.1.

## Public model
Selector unchanged (2 public entries). Bugfix preserving Beta 4 authority; landing classifier only.
