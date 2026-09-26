# Beta 3.1 PE sealed cold-chunk eviction forensic

Previous cold-archive evidence reused (`BETA31_PE_COLD_ARCHIVE = PARTIAL`). e02e833b untouched. No push.

## Question

After a forgotten PECA chunk is immutable, checksummed, and committed, does its float payload need to stay in process RAM?

## Mechanism (opt-in)

`set_cold_archive(True)` + `set_cold_eviction(True, root=...)`. Production default **both False**.

Lifecycle: `OPEN_RAM` → `SEALING` (n=256) → durable `chunk_NNNNNN.bin` + `committed.json` (fsync, `os.replace`, CRC32) → strip payload keys → `EVICTED_DISK`. Commit failure keeps RAM and does not acknowledge the chunk. No mmap.

Cognition never hydrates evicted chunks (`COGNITION_DISK_READS = 0` through 10k). Analyzer `reconstruct=False` yields one summary row per evicted chunk; `reconstruct=True` loads one file inside `forensic_disk_reads()`.

Checkpoint JSON stores descriptors for evicted chunks and arrays only for the **open** chunk. Restore does not read `.bin` files.

## Matched seed 575 (TwoAgent, R3, RICH, CORRELATED, OCCLUSION, PE/TPS/TPE)

| Mode | RSS t1000 | MB/1000 (t0–t1000) | RssAnon t1000 |
| --- | --- | --- | --- |
| Hybrid G | 501.4 | 456.8 | 481.3 |
| Cold RAM (no evict) | 512.0 | 467.4 | 491.9 |
| **Cold disk evict** | **363.8** | **319.4** | **343.8** |

Evict t1000: 13432 forgotten classes, 50 committed chunks, **160 MB disk**, **8.8 MB archive RAM** (almost all the open chunk). RssFile stayed ~20 MB.

Local RSS slopes (evict): t250→1000 **244**; t1000→2000 **109**; t2000→5000 **35**; t3000→5000 **13.7**; t5000→10000 **9.5**.

`RAM_BEHAVIOR = DECELERATING` (not a hard plateau). Disk remains linear (~190–200 MB / 1000 ticks).

## Aged / 10k

| Tick | RSS | RssAnon | Disk |
| --- | --- | --- | --- |
| 5000 | 579.1 | 559.0 | 945 MB |
| 10000 | 624.9 | 604.8 | 1907 MB |

Archive RAM at 10k still ~10 MB. Forgotten payload is on disk. Hybrid-G family at 10k would have been ~4.5+ GB RSS.

Fresh restore at t500: old process 247 MB vs fresh 239 MB (only **8 MB** allocator reset). Remaining RSS is live working set (ACTIVE + open chunks + other runtime), not a huge high-water artifact.

`malloc_trim` diagnostic on a tiny store-only loop: **13.9 MB**. Not production.

## Equivalence / safety

Cognition hybrid vs evict 100 ticks **EXACT**. JSON restore + 100 ticks **EXACT**. Crash injects (partial write / index-before-evict) **PASS**. Shadow 325 **0 mismatches**. Sealed payload keys absent after eviction.

Aged ≥5k **checkpoint was not run** (t80 checkpoint path was exercised).

## Production decision

Do **not** default eviction yet: open-chunk checkpoints still serialize current arrays (35 MB JSON at t80, +151 MB peak RSS while dumping); aged checkpoint untested; 40k unmeasured.

`SUBPROCESS_WRITER = REJECTED_NOT_NEEDED` (main-process encode did not dominate RSS once payloads left RAM).

## Verdict

`BETA31_PE_COLD_EVICTION = PASS` for the eviction hypothesis: sealed history can leave anonymous RAM and RSS no longer tracks forgotten-class payload linearly. Public Beta 3.1 remains blocked until defaulting, aged checkpoint, and a 40k budget are reviewed.
