# SEARCH_COMPACT Architecture

## Principle

```
         SAME RUNTIME (physics / cognition / RNG / config / ticks)
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
       FULL_SCIENTIFIC          SEARCH_COMPACT
       full V2 notebook         bounded metrics +
                                rolling candidate windows
```

Execution mode (`LIVE`/`FAST`/`MAX`/`HEADLESS`) is **orthogonal**.

## API

`POST /api/control/evidence-mode` `{ "mode": "FULL_SCIENTIFIC" | "SEARCH_COMPACT" }`

Header: `evidence_mode`, optional `evidence_label: COMPACT EVIDENCE`.

## Modules

`mechanistic_mind/ui/psy_observer_web/search_compact/`

- `metrics.py` — bounded factual counters
- `controller.py` — rolling window + factual triggers + candidates
- `writer.py` — disk artifacts + `SearchWorkerResult`

## Analyzer / Forensics

| Mode | Compatibility |
|------|----------------|
| FULL_SCIENTIFIC | `ANALYZER_FULL_COMPATIBLE` |
| SEARCH_COMPACT default | `COMPACT_ONLY` |
| Candidate window | `CANDIDATE_WINDOW_COMPATIBLE` |

Never silently analyze missing evidence.

## Cognition boundary

Search metrics, triggers, candidates, worker ids **never** enter agent observation.

## Scheduler boundary

```
SEARCH SCHEDULER → N workers → SEARCH_COMPACT → SearchWorkerResult
```

Optional later: reproduce candidate under `FULL_SCIENTIFIC` using seed + config fingerprint.

See `results/search_compact/`.
