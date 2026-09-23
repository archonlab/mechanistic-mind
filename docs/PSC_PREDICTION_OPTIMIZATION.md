# PSC prediction hot-path optimization

## Goal

Make the **same** `predict_one_step` cheaper — no semantic change.

## Call path

See `results/psc_prediction_optimization/call_path.md`.

## What actually costs time

On Tiktaalik 16×16 / 2 agents:

- ~50 `predict_one_step` calls/tick
- Store size typically **5–8** transitions (`MAX_TRANSITIONS=128` unused)
- Cost is dominated by **`_q` + SHA1 `_sig`** (exact key), not dense arithmetic
- Soft-match scan is secondary at this N
- ~20% of `runtime.step` wall; ~45% of `run_cognition_before_action`

**Classification:** mixed / bookkeeping-heavy — poor Numba target without changing key identity.

## What we implemented

| Change | Always on? | Notes |
|--------|------------|-------|
| Single quantize + compose `_ant_q` reuse | yes | removes duplicate `_q` in seed/expand |
| `mean_cons` / `reliability` row cache | yes | invalidated on learn |
| Action-indexed pack (`_psc_pack`) | `MM_PSC_BACKEND=packed\|numba` | versioned; bump on learn |
| Optional Numba soft-distance | `MM_PSC_BACKEND=numba` | falls back if unavailable / unsafe schema |
| Backend provenance in scientific meta | yes | not organism-visible |

## Measured outcome (quiet host)

| Backend | µs/call (MID) | Cognition t/s |
|---------|---------------|---------------|
| LEGACY | ~30–39 | ~76–84 |
| PACKED | ~31–40 | ~81 |
| NUMBA | n/a or ≤packed | (Numba not installed / no gain) |

**Packing alone does not beat legacy** on this workload (overhead ≈ benefit).  
**Numba:** optional prototype; **NOT_WORTH_DEFAULT**.

Default: `MM_PSC_BACKEND=legacy` (or unset).

Equivalence: **EXACT_MATCH** across legacy/packed/numba-fallback and multi-seed checkpoints.

## Amdahl / NEXT

After PSC micro-work, the large gap remains:

`cognition ~80 t/s` → `session-no-V2 ~35 t/s`

`session_followup_profile.json`: `accumulate_events` is the ranked session hot path after `scientific_step`.

**Recommended NEXT:** session event/motion bookkeeping optimization (not more PSC Numba).

## Env

```
MM_PSC_BACKEND=legacy   # default
MM_PSC_BACKEND=packed   # action-indexed soft match
MM_PSC_BACKEND=numba    # optional; falls back if Numba missing
```
