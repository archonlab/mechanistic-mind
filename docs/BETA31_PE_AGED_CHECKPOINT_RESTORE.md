# Beta 3.1 PE aged checkpoint / restore

Seed 575, Tiktaalik Two-Agent, production-candidate cold eviction (PECA v1, chunk 256, no mmap). Fresh-process restore. No push.

## Architecture reused

Checkpoint JSON is operational state plus chunk descriptors. OPEN_RAM payloads are PECA sidecars under `runtime_checkpoints/current/pe_open/`. Sealed PECA files stay in the live archive root; checkpoint does not copy or rewrite them.

## Aged ≥5k (same process)

| Metric | Value |
| --- | --- |
| Tick | 5000 |
| Pre-checkpoint RSS | 578.605 MB |
| RssAnon | 558.512 MB |
| RssFile | 20.094 MB |
| Archive disk | 944.906 MB |
| Sealed/committed chunks | 296 |
| Cold records | 76478 |
| Resident index | 8.742 MB |
| OPEN_RAM bytes | 8.136 MB |
| Checkpoint wall | 6.716 s |
| Snapshot JSON | 48.068 MB |
| Open sidecar files / bytes | 6 / 8.371 MB |
| JSON `"floats":` copy | **NO** |
| Peak RSS during checkpoint | 584.918 MB |
| Peak delta | **+6.313 MB** |
| Cognition disk reads | 0 |

## Fresh-process restore

| Metric | Value |
| --- | --- |
| Restore RSS | 244.820 MB |
| Restore RssAnon | 225.090 MB |
| Restore RssFile | 19.730 MB |
| Actions/obs/body/PE/archive identity vs `fp_pre` | match |
| Continuation 1 / 10 / 100 ticks vs in-memory branch | **EXACT** |
| Cognition disk reads after restore+continue | 0 |
| New chunks append; old `committed.json` prefixes preserved | yes (`branch.restored`) |

`AGED_CHECKPOINT_RESTORE = PASS`  
`AGED_CHECKPOINT_CONTINUATION = EXACT`

## 10k checkpoint / restore

| Metric | Value |
| --- | --- |
| Tick | 10000 |
| Pre-checkpoint RSS | 614.930 MB |
| Peak delta | **+0.468 MB** |
| Snapshot JSON | 49.369 MB |
| Open sidecars | 6 / 8.549 MB |
| Fresh restore RSS | 250.680 MB |
| Continuation 100 ticks | **EXACT** |

`TEN_K_CHECKPOINT_RESTORE = PASS`  
`TEN_K_CONTINUATION = EXACT`
