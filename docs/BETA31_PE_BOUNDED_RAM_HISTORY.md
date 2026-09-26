# Beta 3.1 bounded-RAM PE history

Operational RAM should approach a slowly growing working set: **ACTIVE PE (cap 32)** plus the current **open cold chunk**. Scientific forgotten history grows as checksummed PECA files.

```
ACTIVE classes
    → forget → append OPEN_RAM chunk (256 records)
        → seal → fsync write chunk_*.bin + committed.json
            → evict float/mask/aux arrays from the process
```

## What stays in RAM

- ACTIVE member graphs (unchanged)
- One unsealed SOA chunk per PE store (outer, temporal.inner, populated TPE inners)
- Interned schema/action tables (tiny)
- Per-evicted-chunk descriptors (path, crc, n, id/tick range) — on the order of **~10 KB / 1000 classes**, **~3.7 descriptor objects / 1000 classes**

## What must not stay in RAM

Sealed committed float64 payloads. After eviction those keys are gone from `store["_pe_cold"]["chunks"][i]`. Reload is explicit, chunk-scoped, and forbidden on the cognition path.

## Observed working set (seed 575, two agents)

Anonymous RSS decelerates to ~9–14 MB / 1000 ticks by 5k–10k while disk grows ~0.19 GB / 1000 ticks. RssFile does not accumulate (no mmap). A 10k process was **625 MB** RSS with **1.9 GB** archive on disk.

40k is **not** claimed safe from this alone (projection from the aged slope is ~1 GB RSS / ~7 GB disk, unmeasured).

## Checkpoint contract

Checkpoint metadata references `archive_id`, `committed[]`, and the open chunk. It must not rewrite sealed `.bin` files. Restore must not hydrate those files. Current implementation follows that for evicted chunks; the open chunk is still JSON-encoded.
