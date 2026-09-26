# Beta 3.1 — 40k server death forensic

**Run:** `.live-psyweb-20260923T180243.860310Z-e02e833b` (seed 575, TwoAgentRuntime)  
**Do not mutate this directory.** Compact copies live under `results/beta31_40k_server_death_forensic/`.  
**Do not merge** dead ticks after a checkpoint with a restored branch.

## Process death

| Field | Evidence |
|---|---|
| PID | 14381 `python` |
| Time | 2026-09-24 00:34:55 (kernel) |
| Mode | **OOM_KILL** |
| anon-rss | 19120832 kB ≈ 18.2 GB |
| total-vm | 20900152 kB |
| cgroup | `session-3.scope` / containerd |
| ENOSPC | **NO** (no kernel ENOSPC; later disk still had free space) |
| Live dir mtime | 2026-09-24 00:34:30 — matches OOM window |

`PROCESS_DEATH_MODE = OOM_KILL`  
`ROOT_CAUSE_CONFIDENCE = STRONG`  
Kernel: `Out of memory: Killed process 14381 (python)`. That is **not** inferred from the historical Analyzer 15.4 GB incident (PID 269596, 2026-09-23 06:52).

Current `.psy_observer/instance.json` is a **new** Observer after the crash. It is not the dead fish.

### Evidence channels (not one story)

- **KERNEL:** global OOM, pid 14381 python, oom_reaper.  
- **SYSTEMD:** journald memory-pressure flush after kill; not a unit restart of a dedicated Observer service.  
- **OBSERVER:** UI `STOP: REJECTED · HTTP_FAILED · NetworkError` because the fetch target died. Last durable scientific writes ~t40163–40166.  
- **FILESYSTEM:** JSONL closed with final newlines; no ENOSPC / I/O error in the window.

## Surviving corpus

Live runtime is **not** recoverable. Scientific V3 **is**.

| File | Size | Lines | First tick | Last tick |
|---|---|---|---|---|
| scientific_decisions.jsonl | 2.65 GB | 80328 | 0 | 40163 |
| scientific_observations.jsonl | 148 MB class | 80328 | 0 | ~40163 |
| scientific_spine.jsonl | ~40 MB | 80328 | 0 | 40163 |
| scientific_events.jsonl | 135 MB | 349616 | 1 | 40166 |
| scientific_checkpoints.jsonl | 42 KB | 4 | 10000 | 40000 |

`scientific_checkpoints.jsonl` is **geometry forensic**, not crash-restore.

Frontier: last complete O→D→M→C tick **40163**. Meta/events slightly ahead (40164–40166) is an incomplete crash frontier. Analyzer 1.2 compact reconstruction: **80328 / 80328** complete ODMC, tick range `[0, 40163]`, two bodies. Treat as **CRASH-TERMINATED NATURALISTIC CORPUS**.

`ANALYZER_INVOLVED_IN_40K_DEATH = UNKNOWN` (lean **NO**): no analysis job artifacts in the live dir; death aligns with RUNNING append. Dead process image was not sampled.

## Memory vs disk

- RSS ≈ **465 MB / 1000 ticks** if growth was roughly linear to 18.2 GB at t40165.  
- SMC occupancy at last decisions: **256/256 cap** (bounded).  
- Observer full WORLD frames: retain 1 (prior fix).  
- V3 disk ≈ **79.7 MB / 1000 ticks**, **3.13 GB at ~40k**. Projection: 10k ≈ 0.78 GB, 100k ≈ 7.8 GB. Disk is **not** the death mode.  
- **UNBOUNDED_RAM_OWNER_FOUND = INCONCLUSIVE.** JSONL growth is disk, not proof of a Python leak. Allocator / PE / cognition object graph was not live-sampled.

A new unattended 40k on the same machine will likely OOM again unless RSS growth is identified or the machine has much more RAM.

## Gates

Checkpoint infrastructure is implemented separately (`docs/BETA31_CRASH_SAFE_CHECKPOINTING.md`).  
**Do not publish Beta 3.1. Do not push. Do not start another unattended 40k.** Wait for review.
