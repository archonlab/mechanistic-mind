# OBSERVE V2

**Marker:** `OBSERVE_V2_ACCEPTED` (presentation / evidence-routing only)

## Principle

> Make the organism readable without changing the organism.

Observe answers **now / recent / available evidence**.  
Analyzer / Signal Forensics answer **full-run reconstruction**.

## Old Observe audit

- Observe device tool was a launcher embedding legacy TIMELINE / MIND / DATA panels.
- Primary history was a **Recorded Frames** wall (`tN` cards).
- SIGNAL filter treated `SIGNAL|FIELD_*` as one bucket → OSC under-emphasized.
- `events` / `timeline` React buffers were **not** cleared on reset/generation change (stale risk).
- Composite motor / effectors / passive sensors existed on the Inspector card but not as Observe’s default surface.

## New architecture

```
OBSERVE
├── CURRENT STATE   (live bounded frame → motor / effectors / passive / body)
├── RECENT EVENTS   (bounded structured timeline, compressed)
└── RAW EVIDENCE    (exact frames/events; collapsed by default)
```

### Modules

| Module | Role |
|--------|------|
| `observe/currentState.ts` | Extract CURRENT STATE from `motor_control` + `physical` + observation |
| `observe/recentEvents.ts` | Structured events + OSC span compression + caps |
| `observe/eventCategory.ts` | Mechanism-aware OSC vs LEGACY_FIELD routing |
| `observe/bufferIdentity.ts` | run_id / generation / agent invalidation |
| `components/ObserveV2Panel.tsx` | UI shell |

### Buffer ownership

- Live aux lists remain capped by `liveBounds.ts` (`LIVE_FE_EVENTS_DISPLAY_MAX=500`, timeline 400).
- On **reset / apply / restart**: clear `events`, `timeline`, `selectedEvent`.
- On **run_id or generation change**: clear live Observe buffers.
- On **agent switch**: clear selected event; CURRENT STATE re-projects immediately.

### Signal routing

- `OSCILLATORY` ← `OSC_*` / oscillatory types
- `LEGACY FIELD` ← `PHYSICAL_SIGNAL_*` / `FIELD_*`
- `ALL SIGNALS` = union
- Never relabel OSC as FIELD_A/B or vice versa

### Compatibility

- `COMPOSITE_MOTOR_V1`: factorized motor output authoritative
- `LEGACY_SINGLE_SLOT`: canonical action; composite fields `NOT AVAILABLE`
- Missing historical values → **NOT AVAILABLE** (not 0)

### Performance

- No full scientific history scan on live refresh
- Recent cards capped (100 / 500 / ALL LOADED≤2000)
- Raw frames only when explicitly opened

### Scientific non-interference

No edits to runtime, cognition, PSC, physics, OSC propagation, motor selection, or forensics reconstruction semantics. Fingerprint: **EXACT_MATCH**.
