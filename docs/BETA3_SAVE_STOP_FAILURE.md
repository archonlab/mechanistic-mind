# Beta 3 Save/Stop failure (tick ~10231)

**Do not delete.** Live evidence and the incomplete tmp dir are retained.

## Layers (this incident)

| Layer | Result |
|---|---|
| **SAVE** | **FAILED / incomplete.** No `run.json`. No `physical_system_snapshot.json`. `os.replace`/`os.rename` of tmp→run dir never ran. |
| **FINALIZE** | **STARTED then killed.** Scientific writer was closed (`scientific_meta.json` `closed_at` 2026-09-22T21:00:34Z, `last_tick_written`: **10231**). Snapshot serialize never finished. |
| **HTTP** | **NO RESPONSE.** `POST /api/control/stop` `{save:true}` never logged `200`. Browser: `TypeError: NetworkError when attempting to fetch resource.` |
| **RUNTIME** | **DEAD.** uvicorn PID **179327** SIGKILL **OOM** at 23:03:38 local. RSS ~14.6 GB (`anon-rss:14565804kB`), VM ~18.5 GB. Process left **zombie**; parent launcher 179305 still alive; port **8768** closed. |
| **UI** | **MISCLASSIFIED.** Catch mapped NetworkError to SAVE_FAILED + STOP_REJECTED. Overlay FINALIZING / t10231 / 0 t/s. Second Save & Stop also NetworkError (server gone). |

This is **not** the previous `TypeError: '<' not supported between instances of 'int' and 'NoneType'`. No traceback with that message on this attempt.

## Request

- Browser: Save & Stop → `POST /api/control/stop` JSON `{save: true, reason: "USER_STOP_SAVED"}`
- Preceded by `GET /api/control/stop-info` **200** (dialog)
- Method: POST, **synchronous** until handler returns (no bytes until snapshot+frame JSON ready)

## Disk (untouched)

- Live: `results/psychology_observer/psy_observer_web/.live-psyweb-20260922T192322.056455Z-f9b24837/` (~677 MB jsonl, still present)
- Incomplete tmp: `results/psychology_observer/psy_observer_web/.tmp-psyweb-20260922T192322.056455Z-f9b24837-10db01/` (**empty**; created then process died before first `_json_dump`)
- No `*.part` files
- No published `psyweb-20260922T192322.056455Z-f9b24837/` run directory

## Why RAM exploded

`write_finalized_run` did `runtime.snapshot()` (copy of aged TwoAgent cognition) then `json.dumps(json_safe(payload))` (second tree + one giant string) while the live runtime stayed resident. Forensic RSS mid-run was ~3.5 GB; 3× copies → OOM ~14 GB. Kernel kill → TCP reset → Firefox NetworkError.

## Fixes landed after forensics

- Stream `json.dump` (no full string); in-place `json_prepare` instead of copying every dict
- Do not `json.loads` the snapshot file for post-write validation
- Save & Stop `wait:false` + `GET /api/control/save-job` poll
- FINALIZING cannot stick: failure → SAVE_FAILED; dead worker → SAVE_FAILED
- UI HTTP_FAILED vs SAVE_FAILED banners
