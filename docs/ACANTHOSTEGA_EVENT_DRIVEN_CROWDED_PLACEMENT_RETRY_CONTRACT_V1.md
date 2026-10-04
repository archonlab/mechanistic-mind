# ACANTHOSTEGA_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT_V1

## Verdict

`NO_NEW_RUNTIME_MECHANISM_REQUIRED` for placement physics.
This slice formalizes existing SETMR → WMT → DTIP crowded rejection as an
explicit, testable, restorable, researcher-visible contract.

## Names

| Role | Value |
|------|--------|
| Preset | `ACANTHOSTEGA_BETA4_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT` |
| Parent | `ACANTHOSTEGA_BETA4_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION` |
| Mechanism | `event_driven_crowded_placement_retry_contract` |
| Profile | `EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT_V1` |
| Receipt family | `CROWDED_PLACEMENT_RETRY` |
| Dedup key version | `CROWDED_RETRY_DEDUP_V1` |

## Cumulative chain

```text
BNLT → RCSS → ALTVSF → EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
```

## Physical behavior (unchanged)

```text
eligible physical exertion
→ SETMR accumulation
→ threshold
→ RCSS gate
→ WMT provisional + DTIP K=16
→ all candidates blocked → UNSAFE_OBJECT_PLACEMENT
→ no terrain mutation / no object / no ID
→ SETMR work retained
→ NO background retry
→ later NEW eligible exertion may retry once
```

## Contract rules

- `RETRY_TRIGGER = RETRY_ONLY_ON_NEW_ELIGIBLE_PHYSICAL_EXERTION_EVENT`
- `MAX_RETRIES_PER_EVENT = 1`
- `AUTOMATIC_BACKGROUND_RETRY = NO`
- `SETMR_WORK_RETAINED_ON_PLACEMENT_REJECT = YES`
- `PENDING_DETACHED_MATERIAL = NO`
- K=16 frozen; missing far-SW `(-0.70,-0.70)` unchanged (placement-geometry debt)
- Conflict geometry `XY_DISK_OVERLAP_MARGIN_0.95_FULL_OBJECT_SCAN` unchanged (O(K×N) debt)

## Dedup key

```text
CROWDED_RETRY_DEDUP_V1|{tick}|{cx}|{cy}|{body_id}|{effector_id}|{physical_source_kind}|{attempt_seq}
```

## Next roadmap seam

`DETACHED_MATERIAL_SIZE_GEOMETRY_ARCHITECTURE`

`FREE_SPACE_V1_REQUIRED_NOW = NO`
