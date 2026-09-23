# Ordinary Observer SCIENTIFIC_V3: SMC + O′ Historical Selection evidence

**Date:** 2026-09-21

## Previous gap

Ordinary SCIENTIFIC_V3 DecisionReceipts already embedded a compact
`sensorimotor_consequence` block on every decision, but Analyzer Next looked for a
separate `sensorimotor_consequence_model` payload that was never populated →
**ACTION-CONDITIONED SENSORIMOTOR MODEL: NOT_RECORDED**.

O′→history→PSC bridge meta lived only in cognition `last_selection`
(`o_prime_history_bridge`, `o_prime_history_candidates`) and was **not** copied into
DecisionReceipt → **HISTORICAL SENSORIMOTOR SELECTION: NOT_RECORDED**.

Dedicated harnesses under `results/mm_o_prime_history_bridge/` already demonstrated
the mechanisms; this work only preserves authoritative runtime evidence on ordinary
Observer runs.

## Authoritative sources

| Fact | Source |
|------|--------|
| SMC query / predictions / update | `cognition.last_selection.sensorimotor_*` |
| O′ bridge meta + candidates | `cognition.last_selection.o_prime_history_*` |
| Persistence | `build_decision_receipt` → `scientific_decisions.jsonl` |
| Analyzer | `smc_hss_from_decisions.aggregate_*` from decisions |

## Schemas (additive on DecisionReceipt)

- `sensorimotor_consequence` — enriched with `predicted_delta`, compact `last_update`
- `historical_sensorimotor_selection` — enabled, withheld/shuffle, candidate list
  (locomotion, history_status/support, predicted_fields, available_to_psc)

No GT peer distance/bearing, reward, seeking, or Analyzer labels.

## Subscription independence

Tier 0. Recorded under OBSERVER MINIMAL/NORMAL/FULL. Panel DEFERRED must not omit
these fields from DecisionReceipts.

## PSC configuration history

World fingerprint did not include cognition mechanisms, so PSC hot-toggles were
dropped when `fp_before == fp_after`. Fix: explicit `category=mechanism` changes
still record WORLD_INTERVENTION / configuration-history events.

Reference run `.live-psyweb-20260921T090822…`: first `SCENARIO_COMPETITION` at tick
383 without a PSC mechanism event (historical gap). Climate toggles were recorded.

## Analyzer

Sections consume aggregated DecisionReceipts. Funnel stage
`psc_ranking_changed_by_history_evidence` stays **NOT_RECORDED** unless an
authoritative ranking-delta field exists (do not synthesize).

## Determinism

Receipt builders are observational; cognition EXACT_MATCH preserved in tests.

## Smoke

`results/observer_performance/smc_hss_smoke/` — seed 17, PSC OFF→ON hot toggle,
MINIMAL UI detail, FULL_SCIENTIFIC evidence: SMC RECORDED, HSS RECORDED,
O→D→M→C complete.
